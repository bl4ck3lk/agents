# Cloud Deployment Guide

This guide covers deploying Agents to cloud platforms.

## Architecture Options

### Option 1: Vercel (Frontend) + Railway/Render (Backend)

Best for: Small to medium deployments, quick setup

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Vercel     │────▶│   Railway    │────▶│   Supabase   │
│   Frontend   │     │   Backend    │     │   PostgreSQL │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                     ┌──────▼──────┐
                     │ Cloudflare  │
                     │     R2      │
                     └─────────────┘
```

### Option 2: AWS (Full Stack)

Best for: Large deployments, full control

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ CloudFront   │────▶│     ECS      │────▶│     RDS      │
│   + S3       │     │   Fargate    │     │   PostgreSQL │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                     ┌──────▼──────┐
                     │     S3      │
                     │   Storage   │
                     └─────────────┘
```

---

## Option 1: Vercel + Railway

### Frontend on Vercel

1. **Connect Repository**
   ```bash
   cd web
   vercel link
   ```

2. **Configure Environment Variables**
   In Vercel Dashboard → Settings → Environment Variables:
   ```
   NEXT_PUBLIC_API_URL=https://your-api.railway.app
   ```

3. **Deploy**
   ```bash
   vercel deploy --prod
   ```

### Backend on Railway

1. **Create Project**
   - Go to [railway.app](https://railway.app)
   - Connect GitHub repository
   - Select the repo

2. **Configure Service**
   - Root Directory: `/`
   - Build Command: `pip install -e .`
   - Start Command: `agents-api`

3. **Add PostgreSQL**
   - Click "New" → "Database" → "PostgreSQL"
   - Railway auto-injects `DATABASE_URL`

4. **Add Environment Variables**
   ```
   SECRET_KEY=<generated>
   ENCRYPTION_KEY=<generated>
   S3_ENDPOINT_URL=https://your-bucket.s3.amazonaws.com
   AWS_ACCESS_KEY_ID=<key>
   AWS_SECRET_ACCESS_KEY=<secret>
   S3_BUCKET_NAME=agents
   CORS_ORIGINS=https://your-app.vercel.app
   ```

5. **Deploy**
   - Railway auto-deploys on push

### Storage with Cloudflare R2

1. **Create R2 Bucket**
   - Cloudflare Dashboard → R2 → Create bucket
   - Name: `agents`

2. **Get API Credentials**
   - R2 → Manage R2 API Tokens
   - Create API token with read/write

3. **Configure**
   ```
   S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
   AWS_ACCESS_KEY_ID=<r2-access-key>
   AWS_SECRET_ACCESS_KEY=<r2-secret-key>
   S3_BUCKET_NAME=agents
   ```

---

## Option 2: AWS Full Stack

### Prerequisites

- AWS Account
- AWS CLI configured
- Terraform (optional, for IaC)

### Step 1: RDS PostgreSQL

```bash
# Create RDS instance
aws rds create-db-instance \
    --db-instance-identifier agents-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --engine-version 16 \
    --master-username admin \
    --master-user-password <password> \
    --allocated-storage 20 \
    --vpc-security-group-ids <sg-id>
```

### Step 2: S3 Bucket

```bash
# Create bucket
aws s3 mb s3://agents-storage-<unique-suffix>

# Configure CORS
aws s3api put-bucket-cors --bucket agents-storage-<suffix> --cors-configuration '{
    "CORSRules": [{
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["GET", "PUT", "POST"],
        "AllowedOrigins": ["https://your-domain.com"],
        "MaxAgeSeconds": 3000
    }]
}'
```

### Step 3: ECR Repository

```bash
# Create repository
aws ecr create-repository --repository-name agents-api

# Login
aws ecr get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t agents-api .
docker tag agents-api:latest <account>.dkr.ecr.us-east-1.amazonaws.com/agents-api:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/agents-api:latest
```

### Step 4: ECS Fargate

Create `task-definition.json`:

```json
{
    "family": "agents-api",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "512",
    "memory": "1024",
    "executionRoleArn": "arn:aws:iam::<account>:role/ecsTaskExecutionRole",
    "containerDefinitions": [{
        "name": "api",
        "image": "<account>.dkr.ecr.us-east-1.amazonaws.com/agents-api:latest",
        "portMappings": [{
            "containerPort": 8000,
            "protocol": "tcp"
        }],
        "environment": [
            {"name": "DATABASE_URL", "value": "postgresql+asyncpg://..."},
            {"name": "S3_ENDPOINT_URL", "value": "https://s3.us-east-1.amazonaws.com"},
            {"name": "S3_BUCKET_NAME", "value": "agents-storage-xxx"},
            {"name": "CORS_ORIGINS", "value": "https://your-domain.com"}
        ],
        "secrets": [
            {"name": "SECRET_KEY", "valueFrom": "arn:aws:secretsmanager:..."},
            {"name": "ENCRYPTION_KEY", "valueFrom": "arn:aws:secretsmanager:..."},
            {"name": "AWS_ACCESS_KEY_ID", "valueFrom": "arn:aws:secretsmanager:..."},
            {"name": "AWS_SECRET_ACCESS_KEY", "valueFrom": "arn:aws:secretsmanager:..."}
        ],
        "logConfiguration": {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group": "/ecs/agents-api",
                "awslogs-region": "us-east-1",
                "awslogs-stream-prefix": "ecs"
            }
        }
    }]
}
```

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://task-definition.json

# Create service
aws ecs create-service \
    --cluster agents-cluster \
    --service-name agents-api \
    --task-definition agents-api \
    --desired-count 2 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

### Step 5: Application Load Balancer

```bash
# Create ALB
aws elbv2 create-load-balancer \
    --name agents-alb \
    --subnets subnet-xxx subnet-yyy \
    --security-groups sg-xxx

# Create target group
aws elbv2 create-target-group \
    --name agents-api-tg \
    --protocol HTTP \
    --port 8000 \
    --vpc-id vpc-xxx \
    --target-type ip \
    --health-check-path /health

# Create listener (HTTPS)
aws elbv2 create-listener \
    --load-balancer-arn arn:aws:elasticloadbalancing:... \
    --protocol HTTPS \
    --port 443 \
    --certificates CertificateArn=arn:aws:acm:... \
    --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:...
```

### Step 6: CloudFront + S3 (Frontend)

```bash
# Build frontend
cd web
npm run build
npm run export  # Creates 'out' directory

# Sync to S3
aws s3 sync out/ s3://agents-frontend-xxx --delete

# Create CloudFront distribution
aws cloudfront create-distribution \
    --origin-domain-name agents-frontend-xxx.s3.amazonaws.com \
    --default-root-object index.html
```

---

## Database Migrations

After deploying, run migrations:

### Railway/Render

```bash
# SSH into container or use railway CLI
railway run alembic upgrade head
```

### AWS ECS

```bash
# Run one-off task
aws ecs run-task \
    --cluster agents-cluster \
    --task-definition agents-api \
    --network-configuration ... \
    --overrides '{"containerOverrides":[{"name":"api","command":["alembic","upgrade","head"]}]}'
```

---

## Monitoring

### Sentry

1. Create Sentry project
2. Add DSN to environment variables:
   ```
   SENTRY_DSN=https://xxx@o123.ingest.sentry.io/456
   ENVIRONMENT=production
   ```

### CloudWatch (AWS)

Logs are automatically sent to CloudWatch. Create alarms:

```bash
aws cloudwatch put-metric-alarm \
    --alarm-name agents-api-errors \
    --metric-name 5XXError \
    --namespace AWS/ApplicationELB \
    --statistic Sum \
    --period 300 \
    --threshold 10 \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1
```

---

## Cost Optimization

### Railway

- Use smaller instances during development
- Enable auto-sleep for non-production environments

### AWS

- Use Spot instances for workers
- Enable auto-scaling
- Use reserved instances for steady workloads
- Use S3 Intelligent-Tiering for storage

---

## Security Checklist

- [ ] Enable WAF on ALB/CloudFront
- [ ] Use secrets manager for credentials
- [ ] Enable VPC endpoints for AWS services
- [ ] Configure security groups (minimal access)
- [ ] Enable CloudTrail for audit logging
- [ ] Set up automated backups for RDS
- [ ] Enable encryption at rest for RDS and S3
- [ ] Use IAM roles instead of access keys where possible

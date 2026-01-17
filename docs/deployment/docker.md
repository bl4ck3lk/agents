# Docker Deployment Guide

This guide covers deploying Agents using Docker Compose.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- A server with at least 2GB RAM
- Domain name (for HTTPS)

## Quick Start

### 1. Clone and Configure

```bash
git clone <repo-url>
cd agents

# Create production environment file
cp .env.example .env.production
```

### 2. Configure Environment Variables

Edit `.env.production` with your production values:

```bash
# Database
POSTGRES_USER=agents
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=agents
DATABASE_URL=postgresql+asyncpg://agents:<password>@postgres:5432/agents

# Storage (use external S3 or internal MinIO)
S3_ENDPOINT_URL=http://minio:9000   # or https://s3.amazonaws.com
AWS_ACCESS_KEY_ID=<your-key>
AWS_SECRET_ACCESS_KEY=<your-secret>
S3_BUCKET_NAME=agents-production
AWS_REGION=us-east-1

# Security (generate with: make generate-secret)
SECRET_KEY=<generated-secret>
ENCRYPTION_KEY=<generated-encryption-key>

# MinIO (if using internal storage)
MINIO_ROOT_USER=<minio-user>
MINIO_ROOT_PASSWORD=<minio-password>

# CORS
CORS_ORIGINS=https://yourdomain.com

# Monitoring (optional but recommended)
SENTRY_DSN=<your-sentry-dsn>
```

### 3. Set Up SSL

Create nginx configuration:

```bash
mkdir -p nginx/ssl

# Option A: Using Let's Encrypt (recommended)
# Install certbot and run:
certbot certonly --standalone -d yourdomain.com

# Copy certificates
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem nginx/ssl/
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem nginx/ssl/
```

Create `nginx/nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    upstream api {
        server web-api:8000;
    }

    server {
        listen 80;
        server_name yourdomain.com;
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name yourdomain.com;

        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;

        # API routes
        location /api/ {
            proxy_pass http://api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /auth/ {
            proxy_pass http://api/auth/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location /docs {
            proxy_pass http://api/docs;
        }

        # Static frontend (if not using Vercel)
        location / {
            root /usr/share/nginx/html;
            try_files $uri $uri/ /index.html;
        }
    }
}
```

### 4. Build and Deploy

```bash
# Build images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d

# Run migrations
docker-compose exec web-api alembic upgrade head

# Check status
docker-compose ps
docker-compose logs -f
```

### 5. Verify Deployment

```bash
# Health check
curl https://yourdomain.com/api/health

# Expected response:
# {"status": "ok", "version": "0.2.0"}
```

## Scaling

### Scale Worker Processes

```bash
# Scale processing workers
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --scale processing-service=4
```

### Scale API Servers

For high-traffic deployments, run multiple API instances behind a load balancer:

```yaml
# docker-compose.prod.yml
services:
  web-api:
    deploy:
      replicas: 3
```

## Maintenance

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web-api
```

### Database Backup

```bash
# Backup
docker-compose exec postgres pg_dump -U agents agents > backup.sql

# Restore
cat backup.sql | docker-compose exec -T postgres psql -U agents agents
```

### Update Deployment

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Run any new migrations
docker-compose exec web-api alembic upgrade head
```

### SSL Certificate Renewal

```bash
# Renew Let's Encrypt certificates
certbot renew

# Copy new certificates
cp /etc/letsencrypt/live/yourdomain.com/*.pem nginx/ssl/

# Reload nginx
docker-compose exec nginx nginx -s reload
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs web-api

# Common issues:
# - DATABASE_URL incorrect
# - Missing environment variables
# - Port conflicts
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres psql -U agents -c "SELECT 1"
```

### Storage Issues

```bash
# Check MinIO is running
docker-compose ps minio

# Test connectivity
docker-compose exec web-api curl http://minio:9000/minio/health/live
```

## Security Checklist

- [ ] Use strong passwords for all services
- [ ] Enable SSL/TLS
- [ ] Configure firewall (only expose ports 80, 443)
- [ ] Set up automated backups
- [ ] Enable Sentry for error monitoring
- [ ] Configure rate limiting
- [ ] Review CORS origins
- [ ] Keep images updated

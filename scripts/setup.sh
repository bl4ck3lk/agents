#!/bin/bash
# Quick setup script for Agents development environment
# Usage: ./scripts/setup.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════╗"
echo "║     Agents Development Environment Setup    ║"
echo "╚════════════════════════════════════════════╝"
echo -e "${NC}"

# Check prerequisites
echo -e "${BLUE}Checking prerequisites...${NC}"

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $1 found"
        return 0
    else
        echo -e "  ${RED}✗${NC} $1 not found"
        return 1
    fi
}

MISSING=0
check_command python3 || MISSING=1
check_command docker || MISSING=1
check_command docker-compose || MISSING=1
check_command node || MISSING=1
check_command npm || MISSING=1

# Check for uv or pip
if command -v uv &> /dev/null; then
    echo -e "  ${GREEN}✓${NC} uv found (recommended)"
    INSTALLER="uv pip"
elif command -v pip &> /dev/null; then
    echo -e "  ${YELLOW}!${NC} pip found (uv recommended for faster installs)"
    INSTALLER="pip"
else
    echo -e "  ${RED}✗${NC} Neither uv nor pip found"
    MISSING=1
fi

if [ $MISSING -eq 1 ]; then
    echo ""
    echo -e "${RED}Missing prerequisites. Please install them and try again.${NC}"
    echo ""
    echo "Install instructions:"
    echo "  - Python 3.11+: https://www.python.org/downloads/"
    echo "  - Docker: https://docs.docker.com/get-docker/"
    echo "  - Node.js 18+: https://nodejs.org/"
    echo "  - uv (optional): curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo ""

# Create .env if not exists
if [ ! -f .env ]; then
    echo -e "${BLUE}Creating .env file...${NC}"
    cp .env.example .env

    # Generate secrets
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

    # Replace placeholders
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/your-secret-key-change-in-production/$SECRET_KEY/" .env
        sed -i '' "s/your-32-byte-encryption-key-here/$ENCRYPTION_KEY/" .env
    else
        # Linux
        sed -i "s/your-secret-key-change-in-production/$SECRET_KEY/" .env
        sed -i "s/your-32-byte-encryption-key-here/$ENCRYPTION_KEY/" .env
    fi

    echo -e "  ${GREEN}✓${NC} .env created with generated secrets"
else
    echo -e "${YELLOW}  .env already exists, skipping${NC}"
fi

echo ""

# Install Python dependencies
echo -e "${BLUE}Installing Python dependencies...${NC}"
$INSTALLER install -e ".[dev]"
echo -e "  ${GREEN}✓${NC} Python dependencies installed"

echo ""

# Install frontend dependencies
echo -e "${BLUE}Installing frontend dependencies...${NC}"
cd web
npm install
cd ..
echo -e "  ${GREEN}✓${NC} Frontend dependencies installed"

echo ""

# Start Docker services
echo -e "${BLUE}Starting Docker services...${NC}"
docker-compose up -d postgres minio redis

# Wait for PostgreSQL to be ready
echo -e "  Waiting for PostgreSQL..."
for i in {1..30}; do
    if docker-compose exec -T postgres pg_isready -U postgres &> /dev/null; then
        break
    fi
    sleep 1
done
echo -e "  ${GREEN}✓${NC} PostgreSQL is ready"

# Wait for MinIO
echo -e "  Waiting for MinIO..."
for i in {1..30}; do
    if curl -s http://localhost:9000/minio/health/live &> /dev/null; then
        break
    fi
    sleep 1
done
echo -e "  ${GREEN}✓${NC} MinIO is ready"

echo ""

# Run database migrations
echo -e "${BLUE}Running database migrations...${NC}"
alembic upgrade head
echo -e "  ${GREEN}✓${NC} Database migrations complete"

echo ""
echo -e "${GREEN}"
echo "╔════════════════════════════════════════════╗"
echo "║           Setup Complete!                   ║"
echo "╚════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo "Services running:"
echo "  - PostgreSQL: localhost:5432"
echo "  - MinIO:      localhost:9000 (console: localhost:9001)"
echo "  - Redis:      localhost:6379"
echo ""
echo "Next steps:"
echo ""
echo "  1. Start the API server:"
echo "     ${BLUE}make api${NC}"
echo ""
echo "  2. In another terminal, start the frontend:"
echo "     ${BLUE}make frontend${NC}"
echo ""
echo "  3. Open http://localhost:3000 in your browser"
echo ""
echo "  Or run both with: ${BLUE}make dev${NC}"
echo ""
echo "For more options, run: ${BLUE}make help${NC}"
echo ""

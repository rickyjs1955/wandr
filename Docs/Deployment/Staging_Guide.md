# Staging Environment Deployment Guide

**Version**: 1.0
**Last Updated**: 2025-10-31
**Target Phase**: Post-Subphase 1.5 (after Map Viewer & Pin Management UI complete)

---

## Overview

This guide provides step-by-step instructions for deploying the Spatial Intelligence Platform to a staging environment. The staging environment is intended for pre-production testing, QA, and demo purposes.

## Prerequisites

### Infrastructure Requirements

**Minimum Specifications:**
- **Compute**: 2 vCPUs, 4GB RAM
- **Storage**: 50GB SSD (expandable for video storage)
- **Network**: Public IP address, ports 80 and 443 accessible
- **OS**: Ubuntu 22.04 LTS or similar Linux distribution

**Recommended Cloud Providers:**
- AWS (EC2 + RDS + ElastiCache + S3)
- Google Cloud Platform (Compute Engine + Cloud SQL + Memorystore + Cloud Storage)
- DigitalOcean (Droplet + Managed Database + Spaces)
- Azure (VM + Database for PostgreSQL + Cache for Redis + Blob Storage)

### Required Software

- Docker 24.0+ and Docker Compose 2.0+
- Git
- SSL certificate (Let's Encrypt recommended for staging)

### Required Credentials

- Database password (PostgreSQL)
- Redis password
- Object storage credentials (MinIO/S3)
- SECRET_KEY for application security
- Domain name (or subdomain) for staging

---

## Deployment Steps

### 1. Provision Infrastructure

#### Option A: Single Server (Simple, Recommended for Staging)

```bash
# Example: AWS EC2 Instance
Instance Type: t3.medium (2 vCPU, 4GB RAM)
Storage: 50GB gp3 SSD
Security Group: Allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS)
```

#### Option B: Managed Services (Production-Like)

```bash
# Example: AWS Services
- EC2: t3.medium for application servers
- RDS PostgreSQL: db.t3.micro (Multi-AZ for HA)
- ElastiCache Redis: cache.t3.micro
- S3: Bucket for video storage
- Route 53: DNS management
- ALB: Application Load Balancer
```

### 2. Server Setup

SSH into your server and run initial setup:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.23.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Logout and login to apply docker group changes
exit
```

### 3. Clone Repository

```bash
# Clone the repository
git clone https://github.com/yourusername/wandr.git
cd wandr

# Checkout the desired branch/tag for staging
git checkout main  # or specific release tag
```

### 4. Configure Environment Variables

```bash
# Copy production environment template
cp .env.prod.example .env.prod

# Edit environment file with staging credentials
nano .env.prod
```

**Required Variables:**

```bash
# Application
ENVIRONMENT=staging
VERSION=1.0.0

# Security (CRITICAL: Generate strong random values)
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Database
POSTGRES_DB=spatial_intel_staging
POSTGRES_USER=spatial_user
POSTGRES_PASSWORD=<STRONG_PASSWORD_HERE>

# Redis
REDIS_PASSWORD=<STRONG_PASSWORD_HERE>

# MinIO/S3
MINIO_ROOT_USER=<STRONG_USERNAME_HERE>
MINIO_ROOT_PASSWORD=<STRONG_PASSWORD_HERE>

# CORS
CORS_ORIGINS=https://staging.yourdomain.com
```

**Generate strong passwords:**

```bash
# Generate random passwords
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))"
python3 -c "import secrets; print('REDIS_PASSWORD=' + secrets.token_urlsafe(24))"
python3 -c "import secrets; print('MINIO_ROOT_PASSWORD=' + secrets.token_urlsafe(24))"
```

### 5. Set Up SSL/TLS (HTTPS)

#### Option A: Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain SSL certificate
sudo certbot certonly --standalone -d staging.yourdomain.com

# Certificates will be stored at:
# /etc/letsencrypt/live/staging.yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/staging.yourdomain.com/privkey.pem
```

#### Option B: Self-Signed Certificate (Testing Only)

```bash
# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/nginx-selfsigned.key \
  -out /etc/ssl/certs/nginx-selfsigned.crt
```

### 6. Configure Nginx Reverse Proxy

Create nginx configuration:

```bash
sudo nano /etc/nginx/sites-available/wandr-staging
```

Add configuration:

```nginx
server {
    listen 80;
    server_name staging.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name staging.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/staging.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/staging.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Proxy to frontend
    location / {
        proxy_pass http://localhost:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Proxy to backend API
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/wandr-staging /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 7. Deploy Application

```bash
# Build and start services
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Check service status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 8. Run Database Migrations

```bash
# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Verify migration
docker-compose -f docker-compose.prod.yml exec backend alembic current
```

### 9. Create Initial Admin User (Optional)

```bash
# Access backend container
docker-compose -f docker-compose.prod.yml exec backend python

# Create admin user
from app.core.database import SessionLocal
from app.models.user import User
from app.services.auth_service import hash_password

db = SessionLocal()
admin_user = User(
    email="admin@yourdomain.com",
    username="admin",
    password_hash=hash_password("CHANGE_THIS_PASSWORD"),
    role="MALL_OPERATOR",
    is_active=True
)
db.add(admin_user)
db.commit()
exit()
```

### 10. Verify Deployment

```bash
# Test backend health
curl https://staging.yourdomain.com/api/v1/auth/health

# Test frontend
curl -I https://staging.yourdomain.com/

# Test full login flow
curl -X POST https://staging.yourdomain.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "CHANGE_THIS_PASSWORD"}'
```

---

## Monitoring & Maintenance

### Log Management

```bash
# View application logs
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f frontend

# View nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Backup Procedures

```bash
# Backup PostgreSQL database
docker-compose -f docker-compose.prod.yml exec postgres pg_dump -U spatial_user spatial_intel_staging > backup_$(date +%Y%m%d).sql

# Backup MinIO data
docker-compose -f docker-compose.prod.yml exec minio mc mirror /data /backup
```

### Updates and Rollbacks

```bash
# Pull latest code
git pull origin main

# Rebuild and restart services
docker-compose -f docker-compose.prod.yml up -d --build

# Rollback to previous version
git checkout <previous-commit-hash>
docker-compose -f docker-compose.prod.yml up -d --build
```

---

## Troubleshooting

### Services Not Starting

```bash
# Check service logs
docker-compose -f docker-compose.prod.yml logs backend
docker-compose -f docker-compose.prod.yml logs postgres
docker-compose -f docker-compose.prod.yml logs redis

# Check health status
docker-compose -f docker-compose.prod.yml ps
```

### Database Connection Errors

```bash
# Verify database is running
docker-compose -f docker-compose.prod.yml exec postgres pg_isready

# Check DATABASE_URL in .env.prod
cat .env.prod | grep DATABASE_URL

# Test connection manually
docker-compose -f docker-compose.prod.yml exec postgres psql -U spatial_user -d spatial_intel_staging
```

### SSL Certificate Issues

```bash
# Renew Let's Encrypt certificate
sudo certbot renew

# Test certificate
curl -vI https://staging.yourdomain.com
```

---

## Security Checklist

- [ ] All passwords are strong and unique
- [ ] SECRET_KEY is randomly generated
- [ ] SSL/TLS certificates are valid
- [ ] Firewall rules allow only necessary ports (80, 443, 22)
- [ ] Database is not exposed to public internet
- [ ] Redis requires authentication
- [ ] MinIO/S3 buckets have proper access controls
- [ ] Nginx security headers are enabled
- [ ] Docker containers run as non-root users
- [ ] Environment variables are not committed to git

---

## Next Steps

After successful staging deployment:

1. Test all features thoroughly (auth, map viewer, pin management)
2. Perform load testing if needed
3. Set up monitoring (Prometheus, Grafana, etc.)
4. Configure automated backups
5. Document any staging-specific configurations
6. Plan production deployment strategy

---

## Support

For issues or questions:
- Check application logs
- Review [Production Deployment Checklist](./Production_Checklist.md)
- Review [Environment Configuration Guide](./Environment_Config.md)
- Contact DevOps team

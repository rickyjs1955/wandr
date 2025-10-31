# Environment Configuration Guide

**Version**: 1.0
**Last Updated**: 2025-10-31
**Purpose**: Complete reference for all environment variables and configuration settings

---

## Overview

This document describes all environment variables used across the Spatial Intelligence Platform, their purposes, expected values, and security considerations.

---

## Environment Files

### Development: `.env`
Used for local development with docker-compose.yml

### Staging/Production: `.env.prod`
Used for staging and production deployments with docker-compose.prod.yml

### Example Files
- `.env.example` - Template for development environment
- `.env.prod.example` - Template for production environment

**IMPORTANT**: Never commit actual `.env` or `.env.prod` files to version control!

---

## Application Settings

### ENVIRONMENT
**Purpose**: Identifies the runtime environment
**Type**: String
**Required**: Yes
**Valid Values**: `development`, `staging`, `production`, `test`
**Default**: `development`

```bash
ENVIRONMENT=production
```

**Usage**:
- Affects logging verbosity
- Controls debug features
- Determines error page detail level

---

### VERSION
**Purpose**: Application version for deployment tracking
**Type**: String (Semantic Versioning)
**Required**: No
**Default**: `latest`

```bash
VERSION=1.0.0
```

**Usage**:
- Docker image tagging
- API version reporting
- Deployment tracking

---

### DEBUG
**Purpose**: Enable debug mode (NEVER in production!)
**Type**: Boolean
**Required**: No
**Default**: `false`

```bash
DEBUG=false  # MUST be false in production
```

**Security Warning**: Debug mode exposes sensitive information. Always set to `false` in production.

---

### LOG_LEVEL
**Purpose**: Controls application logging verbosity
**Type**: String
**Required**: No
**Valid Values**: `debug`, `info`, `warning`, `error`, `critical`
**Default**: `info`

```bash
# Development
LOG_LEVEL=debug

# Production
LOG_LEVEL=info
```

**Recommendations**:
- **Development**: `debug` for detailed logs
- **Staging**: `info` for troubleshooting
- **Production**: `warning` to reduce noise

---

## Security Configuration

### SECRET_KEY
**Purpose**: Cryptographic key for session signing and token generation
**Type**: String (256-bit recommended)
**Required**: **YES** (CRITICAL)
**Security**: **HIGHEST**

```bash
# Generate with:
python -c "import secrets; print(secrets.token_urlsafe(32))"

SECRET_KEY=A8JZ7KdF9mN2vX3cR6hY4qL5wE1tP0sG8uI
```

**Security Requirements**:
- **Minimum length**: 32 characters
- **Must be random**: Use cryptographically secure generator
- **Must be unique**: Different for each environment (dev, staging, prod)
- **Must be secret**: Never commit to version control
- **Rotate regularly**: Every 90 days recommended

**Consequences of Exposure**:
- Session hijacking possible
- Authentication bypass possible
- Data integrity compromised

---

## Database Configuration (PostgreSQL)

### DATABASE_URL
**Purpose**: Complete PostgreSQL connection string
**Type**: String (Connection URL format)
**Required**: **YES**
**Format**: `postgresql://{user}:{password}@{host}:{port}/{database}`

```bash
DATABASE_URL=postgresql://spatial_user:STRONG_PASSWORD@postgres:5432/spatial_intel
```

**Alternative**: Can be constructed from individual variables

---

### POSTGRES_DB
**Purpose**: Database name
**Type**: String
**Required**: **YES**
**Default**: `spatial_intel`

```bash
# Development
POSTGRES_DB=spatial_intel

# Staging
POSTGRES_DB=spatial_intel_staging

# Production
POSTGRES_DB=spatial_intel_prod
```

---

### POSTGRES_USER
**Purpose**: Database username
**Type**: String
**Required**: **YES**
**Default**: `spatial_user`

```bash
POSTGRES_USER=spatial_user
```

**Security**:
- Use different usernames per environment
- Grant minimal required permissions

---

### POSTGRES_PASSWORD
**Purpose**: Database password
**Type**: String
**Required**: **YES**
**Security**: **CRITICAL**

```bash
# Generate with:
python -c "import secrets; print(secrets.token_urlsafe(24))"

POSTGRES_PASSWORD=xK9mP2nQ5vL8wR4tY7jH3fD6gC1aZ0sE
```

**Security Requirements**:
- **Minimum length**: 16 characters (24+ recommended)
- **Complexity**: Mixed case, numbers, symbols
- **Unique**: Different for each environment
- **Never reuse**: Across projects or environments
- **Rotate**: Every 90 days

---

### DB_ECHO
**Purpose**: Enable SQLAlchemy query logging
**Type**: Boolean
**Required**: No
**Default**: `false`

```bash
# Development (helpful for debugging)
DB_ECHO=true

# Production (performance impact)
DB_ECHO=false
```

---

### DB_POOL_SIZE
**Purpose**: Number of database connections in pool
**Type**: Integer
**Required**: No
**Default**: `20`

```bash
# Development
DB_POOL_SIZE=5

# Production
DB_POOL_SIZE=20
```

**Tuning**:
- Formula: `(Number of CPU cores × 2) + 1`
- Monitor connection usage and adjust

---

### DB_MAX_OVERFLOW
**Purpose**: Max connections beyond pool size
**Type**: Integer
**Required**: No
**Default**: `10`

```bash
DB_MAX_OVERFLOW=10
```

---

## Redis Configuration

### REDIS_URL
**Purpose**: Complete Redis connection string
**Type**: String (Connection URL format)
**Required**: **YES**
**Format**: `redis://:{password}@{host}:{port}/{db}`

```bash
REDIS_URL=redis://:STRONG_PASSWORD@redis:6379/0
```

---

### REDIS_PASSWORD
**Purpose**: Redis authentication password
**Type**: String
**Required**: **YES** (for production)
**Security**: **HIGH**

```bash
# Generate with:
python -c "import secrets; print(secrets.token_urlsafe(24))"

REDIS_PASSWORD=pL3wQ9xR2mK5nJ8tV1cY7fH4gD0aS6bZ
```

**Security Requirements**:
- **Minimum length**: 16 characters
- **Required in production**: Never run Redis without auth
- **Unique**: Different from database password

---

## Object Storage (MinIO/S3)

### MINIO_ENDPOINT
**Purpose**: MinIO/S3 server endpoint
**Type**: String (host:port)
**Required**: **YES**

```bash
# Development (local MinIO)
MINIO_ENDPOINT=minio:9000

# Production (AWS S3)
MINIO_ENDPOINT=s3.amazonaws.com
```

---

### MINIO_ROOT_USER / MINIO_ACCESS_KEY
**Purpose**: Object storage access key ID
**Type**: String
**Required**: **YES**
**Security**: **HIGH**

```bash
MINIO_ROOT_USER=your_access_key
```

**Production Note**: Use AWS IAM roles instead of hardcoded keys when possible

---

### MINIO_ROOT_PASSWORD / MINIO_SECRET_KEY
**Purpose**: Object storage secret key
**Type**: String
**Required**: **YES**
**Security**: **CRITICAL**

```bash
# Generate with:
python -c "import secrets; print(secrets.token_urlsafe(32))"

MINIO_ROOT_PASSWORD=zR8qP5wL2mN9vX6cK3jY1fH4gD7aS0bT
```

**Security Requirements**:
- **Minimum length**: 24 characters
- **Complexity**: High entropy
- **Never expose**: To client-side code
- **Rotate**: Every 90 days

---

### MINIO_USE_SSL
**Purpose**: Enable HTTPS for object storage
**Type**: Boolean
**Required**: No
**Default**: `false`

```bash
# Development
MINIO_USE_SSL=false

# Production
MINIO_USE_SSL=true
```

---

## CORS Configuration

### CORS_ORIGINS
**Purpose**: Allowed origins for Cross-Origin Resource Sharing
**Type**: String (comma-separated list)
**Required**: **YES**
**Security**: **HIGH**

```bash
# Development (allow localhost)
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Production (specific domain only)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

**Security Requirements**:
- **Never use wildcard** (`*`) in production
- **Use HTTPS** in production
- **Specify exact domains**: No trailing slashes
- **Limit to minimum**: Only necessary origins

---

## Optional Configuration

### SESSION_EXPIRE_SECONDS
**Purpose**: Session expiration time in seconds
**Type**: Integer
**Required**: No
**Default**: `86400` (24 hours)

```bash
# 24 hours
SESSION_EXPIRE_SECONDS=86400

# 1 hour (high security)
SESSION_EXPIRE_SECONDS=3600
```

---

### MAX_UPLOAD_SIZE_MB
**Purpose**: Maximum video upload size in MB
**Type**: Integer
**Required**: No
**Default**: `2048` (2GB)

```bash
MAX_UPLOAD_SIZE_MB=2048
```

---

### VIDEO_STORAGE_BUCKET
**Purpose**: S3/MinIO bucket name for videos
**Type**: String
**Required**: No
**Default**: `spatial-intel-videos`

```bash
VIDEO_STORAGE_BUCKET=spatial-intel-videos-prod
```

---

### PROXY_GENERATION_ENABLED
**Purpose**: Enable video proxy generation (future use)
**Type**: Boolean
**Required**: No
**Default**: `false`

```bash
PROXY_GENERATION_ENABLED=true
```

---

## Environment-Specific Examples

### Development (.env)

```bash
# Application
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=debug

# Database
DATABASE_URL=postgresql://spatial_user:dev_password@postgres:5432/spatial_intel
POSTGRES_DB=spatial_intel
POSTGRES_USER=spatial_user
POSTGRES_PASSWORD=dev_password
DB_ECHO=true
DB_POOL_SIZE=5

# Redis
REDIS_URL=redis://:dev_redis_password@redis:6379/0
REDIS_PASSWORD=dev_redis_password

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123
MINIO_USE_SSL=false

# Security (use placeholder in dev)
SECRET_KEY=dev-secret-key-change-in-production

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

---

### Production (.env.prod)

```bash
# Application
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=warning
VERSION=1.0.0

# Database
DATABASE_URL=postgresql://spatial_prod:STRONG_DB_PASS@prod-db.internal:5432/spatial_intel_prod
POSTGRES_DB=spatial_intel_prod
POSTGRES_USER=spatial_prod
POSTGRES_PASSWORD=STRONG_DB_PASS
DB_ECHO=false
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://:STRONG_REDIS_PASS@prod-redis.internal:6379/0
REDIS_PASSWORD=STRONG_REDIS_PASS

# MinIO/S3
MINIO_ENDPOINT=s3.amazonaws.com
MINIO_ROOT_USER=AKIAIOSFODNN7EXAMPLE
MINIO_ROOT_PASSWORD=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
MINIO_USE_SSL=true

# Security
SECRET_KEY=GENERATE_WITH_SECRETS_MODULE_32_CHARS_MIN

# CORS
CORS_ORIGINS=https://yourdomain.com
```

---

## Secrets Management Best Practices

### DO NOT

❌ Commit `.env` or `.env.prod` files to git
❌ Use the same secrets across environments
❌ Share secrets via email or Slack
❌ Use weak or default passwords
❌ Expose secrets in client-side code
❌ Log secrets in application logs

### DO

✅ Use a secrets manager (AWS Secrets Manager, HashiCorp Vault)
✅ Generate strong, random secrets
✅ Rotate secrets regularly (90 days)
✅ Use different secrets per environment
✅ Audit secret access
✅ Encrypt secrets at rest and in transit

---

## Secret Generation Commands

```bash
# SECRET_KEY (32 bytes, URL-safe)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Database password (24 bytes)
python -c "import secrets; print(secrets.token_urlsafe(24))"

# Redis password (24 bytes)
python -c "import secrets; print(secrets.token_urlsafe(24))"

# MinIO password (32 bytes)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate all at once
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32)); print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24)); print('REDIS_PASSWORD=' + secrets.token_urlsafe(24)); print('MINIO_ROOT_PASSWORD=' + secrets.token_urlsafe(32))"
```

---

## Troubleshooting

### "Invalid DATABASE_URL" Error

Check format: `postgresql://user:password@host:port/database`
- Ensure no special characters in password are unescaped
- Verify host is reachable
- Confirm port is correct (default: 5432)

### "Redis connection refused"

- Verify Redis is running: `docker-compose ps`
- Check REDIS_URL format
- Ensure password is correct

### "CORS policy blocked" Error

- Verify CORS_ORIGINS includes the requesting origin
- Check for trailing slashes (should not have them)
- Ensure protocol matches (http vs https)

### "Signature verification failed"

- SECRET_KEY mismatch between app instances
- SECRET_KEY changed while sessions exist
- Solution: Clear sessions or restart with consistent SECRET_KEY

---

## Support

For questions about environment configuration:
- Review this document
- Check [Staging Deployment Guide](./Staging_Guide.md)
- Check [Production Deployment Checklist](./Production_Checklist.md)
- Contact DevOps team

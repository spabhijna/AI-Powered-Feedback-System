# Feedback System Deployment Guide

This guide explains how to deploy the AI-powered Feedback System using Docker and Docker Compose.

## 📋 Prerequisites

- **Docker** (version 20.10 or higher)
- **Docker Compose** (version 2.0 or higher)
- At least **2GB RAM** available for the container
- At least **3GB disk space** (for ML models and database)

To verify your installation:
```bash
docker --version
docker-compose --version
```

## 🚀 Quick Start

### 1. Clone and Navigate to Project

```bash
git clone <repository-url>
cd feedback_system
```

### 2. Configure Environment Variables

Copy the example environment file and customize as needed:

```bash
cp .env.example .env
```

Edit `.env` to set your configuration:

```bash
# PostgreSQL Database Configuration
POSTGRES_USER=feedback_user
POSTGRES_PASSWORD=your_secure_password_here
POSTGRES_DB=feedback_db
POSTGRES_PORT=5432

# Application Configuration
DATABASE_URL=postgresql://feedback_user:your_secure_password_here@postgres:5432/feedback_db
CORS_ORIGINS=*
API_HOST=0.0.0.0
API_PORT=8000

# Environment (development, production)
ENV=production
```

**Important**: Change the default passwords in production!

### 3. Build and Start Services

```bash
# Build the Docker image and start all services
docker-compose up -d

# View logs (optional)
docker-compose logs -f
```

**First-time startup takes 1-2 minutes** as ML models (~2GB) download from Hugging Face.

### 4. Verify Deployment

Check that services are running:

```bash
docker-compose ps
```

You should see both `feedback_app` and `feedback_postgres` containers running.

Test the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "environment": "production"
}
```

### 5. Access the Application

- **Dashboard**: http://localhost:8000/static/index.html
- **API Documentation**: http://localhost:8000/docs
- **API Base**: http://localhost:8000

## 🔧 Configuration Details

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `POSTGRES_USER` | PostgreSQL username | `feedback_user` | Yes |
| `POSTGRES_PASSWORD` | PostgreSQL password | `feedback_password` | Yes |
| `POSTGRES_DB` | Database name | `feedback_db` | Yes |
| `POSTGRES_PORT` | PostgreSQL port | `5432` | No |
| `DATABASE_URL` | Full database connection string | See `.env.example` | Yes |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `*` | No |
| `API_HOST` | API bind host | `0.0.0.0` | No |
| `API_PORT` | API port | `8000` | No |
| `ENV` | Environment name | `production` | No |

### CORS Configuration

For production, specify exact origins instead of `*`:

```bash
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

## 🛠️ Common Operations

### View Logs

```bash
# All services
docker-compose logs -f

# Just the app
docker-compose logs -f app

# Just the database
docker-compose logs -f postgres
```

### Stop Services

```bash
# Stop containers (keeps data)
docker-compose stop

# Stop and remove containers (keeps data in volumes)
docker-compose down

# Stop and remove everything including volumes (⚠️ deletes data)
docker-compose down -v
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart just the app
docker-compose restart app
```

### Rebuild After Code Changes

```bash
# Rebuild and restart
docker-compose up -d --build

# Force rebuild without cache
docker-compose build --no-cache
docker-compose up -d
```

### Access Container Shell

```bash
# App container
docker-compose exec app /bin/bash

# Database container
docker-compose exec postgres psql -U feedback_user -d feedback_db
```

## 💾 Data Management

### Database Backup

```bash
# Backup PostgreSQL database
docker-compose exec postgres pg_dump -U feedback_user feedback_db > backup.sql

# With timestamp
docker-compose exec postgres pg_dump -U feedback_user feedback_db > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Database Restore

```bash
# Restore from backup
cat backup.sql | docker-compose exec -T postgres psql -U feedback_user feedback_db
```

### Volume Management

Data is persisted in Docker volumes:

- `postgres_data`: PostgreSQL database files
- `huggingface_cache`: Downloaded ML models (~2GB)

List volumes:
```bash
docker volume ls | grep feedback
```

Inspect volume:
```bash
docker volume inspect feedback_system_postgres_data
```

## 🔍 Troubleshooting

### Container Won't Start

1. Check logs for errors:
   ```bash
   docker-compose logs app
   ```

2. Verify port 8000 is not already in use:
   ```bash
   lsof -i :8000
   ```

3. Check if containers are running:
   ```bash
   docker-compose ps
   ```

### Database Connection Issues

1. Verify PostgreSQL is healthy:
   ```bash
   docker-compose exec postgres pg_isready -U feedback_user
   ```

2. Check database URL in `.env` matches PostgreSQL credentials

3. Ensure `DATABASE_URL` uses `postgres` as hostname (not `localhost`)

### ML Models Not Loading

1. Check internet connectivity (models download on first run)

2. Verify sufficient disk space (need ~2GB):
   ```bash
   df -h
   ```

3. Check model cache volume:
   ```bash
   docker-compose exec app ls -lh /root/.cache/huggingface/
   ```

### Performance Issues

1. **High Memory Usage**: ML models require ~1.5GB RAM. Increase Docker memory limit if needed.

2. **Slow Startup**: First startup takes 1-2 minutes to download models. Subsequent starts are faster.

3. **Slow Processing**: Feedback processing takes ~2-3 seconds per item. Consider reducing workers if resource-constrained.

### Health Check Failing

```bash
# Check health endpoint
curl http://localhost:8000/health

# Check if database connection works
docker-compose exec app python -c "from tortoise import Tortoise; import asyncio; asyncio.run(Tortoise.init(db_url='$DATABASE_URL', modules={'models': ['app.models']}))"
```

## 🌐 Production Deployment

### Recommended Settings

1. **Change default passwords** in `.env`
2. **Set specific CORS origins** instead of `*`
3. **Use a reverse proxy** (nginx) for SSL/TLS
4. **Set up monitoring** (health checks, logs)
5. **Configure automatic backups** for database
6. **Use Docker secrets** for sensitive data

### Example nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Resource Requirements

**Minimum**:
- 2 GB RAM
- 2 CPU cores
- 3 GB disk space

**Recommended**:
- 4 GB RAM
- 4 CPU cores
- 10 GB disk space

### Scaling Considerations

Current setup is optimized for:
- <100 requests per minute
- <10,000 feedback items

For higher scale:
- Use multiple worker processes
- Consider separate model servers
- Use PostgreSQL connection pooling
- Implement caching layer (Redis)

## 📊 Monitoring

### Health Checks

Built-in health check endpoint: `/health`

Returns:
```json
{
  "status": "healthy",
  "database": "connected",
  "environment": "production"
}
```

### Logs

Application logs show:
- Startup events
- Model loading status
- Request processing
- Errors and warnings

```bash
docker-compose logs -f app
```

### Database Stats

```bash
# Connect to database
docker-compose exec postgres psql -U feedback_user feedback_db

# Check table size
SELECT pg_size_pretty(pg_total_relation_size('feedback'));

# Count feedback items
SELECT COUNT(*) FROM feedback;
```

## 🔐 Security Checklist

- [ ] Changed default PostgreSQL password
- [ ] Set specific CORS origins (not `*`)
- [ ] Using HTTPS in production (via reverse proxy)
- [ ] Regular database backups configured
- [ ] Monitoring and alerting set up
- [ ] Firewall rules configured
- [ ] Docker host secured and updated

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Tortoise ORM Documentation](https://tortoise.github.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## 🆘 Getting Help

If you encounter issues:

1. Check the logs: `docker-compose logs -f`
2. Verify configuration in `.env`
3. Review this troubleshooting guide
4. Check GitHub issues for similar problems
5. Open a new issue with logs and configuration

---

**Note**: This deployment uses Docker for portability and ease of setup. For large-scale production deployments, consider using Kubernetes or managed container services (ECS, GKE, AKS).

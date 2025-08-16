# Dental Backend Infrastructure

This directory contains the infrastructure configuration for the Dental Backend system, including Docker containers, environment management, and deployment configurations.

## 🏗️ Architecture Overview

The infrastructure consists of the following services:

- **API Service** (FastAPI) - REST API for handling requests
- **Worker Service** (Celery) - Background task processing
- **PostgreSQL** - Primary database with PostGIS extension
- **Redis** - Message broker and caching
- **MinIO** - S3-compatible object storage

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed
- At least 4GB of available RAM
- Ports 8000, 5432, 6379, 9000, 9001 available

### 1. Start All Services

```bash
# From the project root
make docker-build
make docker-run
```

Or manually:
```bash
cd infrastructure
docker-compose up -d
```

### 2. Verify Services

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f

# Test infrastructure
make test-infrastructure
```

### 3. Access Services

- **API Documentation**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/health
- **MinIO Console**: http://localhost:9001 (admin/minioadmin)
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## 🔧 Configuration

### Environment Variables

The system uses a comprehensive configuration system with Pydantic Settings:

- **Development**: Uses `.env` file (copy from `env.example`)
- **Production**: Uses environment variables
- **Configuration**: See `settings.yaml` for all available options

### Key Configuration Files

- `settings.yaml` - Configuration template
- `env.example` - Environment variables template
- `docker-compose.yml` - Service orchestration
- `Dockerfile.api` - API service container
- `Dockerfile.worker` - Worker service container

## 🐳 Docker Configuration

### Multi-Stage Builds

Both API and Worker services use multi-stage builds:

1. **Builder Stage**: Installs dependencies and builds packages
2. **Production Stage**: Creates minimal runtime image with non-root user

### Security Features

- Non-root user execution (UID/GID 1000)
- Minimal runtime dependencies
- Health checks for all services
- Proper file permissions

### Container Structure

```
/app/
├── services/
│   ├── api/          # API service code
│   └── worker/       # Worker service code
├── packages/
│   └── common/       # Shared utilities
├── logs/             # Application logs
└── tmp/              # Temporary files
```

## 📊 Service Dependencies

```
API Service
├── PostgreSQL (Database)
├── Redis (Caching)
└── MinIO (File Storage)

Worker Service
├── PostgreSQL (Database)
├── Redis (Message Broker)
└── MinIO (File Storage)
```

## 🔍 Monitoring and Debugging

### Health Checks

All services include health checks:

- **API**: `GET /health`
- **Worker**: Celery inspect ping
- **PostgreSQL**: `pg_isready`
- **Redis**: `redis-cli ping`
- **MinIO**: HTTP health endpoint

### Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f worker

# View logs with timestamps
docker-compose logs -f --timestamps
```

### Shell Access

```bash
# Access API container
make docker-shell

# Access worker container
make docker-worker-shell

# Or manually
docker-compose exec api /bin/bash
docker-compose exec worker /bin/bash
```

## 🧪 Testing Infrastructure

### Automated Tests

```bash
# Test all infrastructure components
make test-infrastructure

# Or run manually
python scripts/test_infrastructure.py
```

### Manual Testing

1. **API Health**: `curl http://localhost:8000/health`
2. **Database**: Connect with any PostgreSQL client
3. **Redis**: Use `redis-cli` or any Redis client
4. **MinIO**: Use AWS CLI or MinIO client

## 🔄 Development Workflow

### Local Development

```bash
# Start services
make docker-run

# View logs
make docker-logs

# Stop services
make docker-stop

# Clean up
make docker-clean
```

### Code Changes

The containers mount the source code as volumes, so changes are reflected immediately:

- API service: `services/api/` → `/app/services/api`
- Common package: `packages/common/` → `/app/packages/common`
- Worker service: `services/worker/` → `/app/services/worker`

### Hot Reload

The API service runs with `--reload` in development mode, so code changes trigger automatic restarts.

## 🚀 Production Deployment

### Environment Configuration

For production deployment:

1. Set `ENVIRONMENT=production`
2. Set `DEBUG=false`
3. Use environment variables for secrets
4. Configure proper SSL certificates
5. Set up monitoring and logging

### Security Considerations

- Change default passwords
- Use proper SSL/TLS
- Configure firewall rules
- Set up backup strategies
- Enable audit logging

### Scaling

- **API**: Scale horizontally with load balancer
- **Worker**: Scale based on queue depth
- **Database**: Use read replicas for read-heavy workloads
- **Redis**: Use Redis Cluster for high availability

## 🛠️ Troubleshooting

### Common Issues

1. **Port Conflicts**: Check if ports are already in use
2. **Permission Issues**: Ensure Docker has proper permissions
3. **Memory Issues**: Increase Docker memory allocation
4. **Network Issues**: Check Docker network configuration

### Debug Commands

```bash
# Check service status
docker-compose ps

# View detailed logs
docker-compose logs --tail=100 api

# Check resource usage
docker stats

# Inspect container
docker-compose exec api env
```

### Reset Environment

```bash
# Stop and remove everything
make docker-clean

# Rebuild from scratch
make docker-build
make docker-run
```

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [MinIO Documentation](https://docs.min.io/)

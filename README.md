# Dental Backend

A headless backend system for processing and analyzing 3D dental scan data, supporting multiple 3D file formats with HIPAA/GDPR compliance for healthcare data handling.

## 🚀 Features

- **Multi-format Support**: STL, PLY, OBJ, glTF/GLB file processing
- **3D Mesh Analysis**: Geometric analysis, quality assessment, and defect detection
- **HIPAA/GDPR Compliant**: Healthcare data protection standards
- **Headless Architecture**: API-first design with no GUI components
- **Background Processing**: Asynchronous job processing for heavy computations
- **Scalable**: Horizontal scaling for processing workloads

## 🏗️ Architecture

```
dental-backend/
├── services/
│   ├── api/          # FastAPI REST service
│   └── worker/       # Celery background worker
├── packages/
│   └── common/       # Shared utilities and models
├── infrastructure/   # Docker and deployment configs
├── models/          # ML models and configurations
└── scripts/         # Development and utility scripts
```

## 🛠️ Technology Stack

- **Runtime**: Python 3.10+
- **Framework**: FastAPI for API services
- **Database**: PostgreSQL with PostGIS for spatial data
- **Message Queue**: Redis/Celery for background processing
- **Storage**: S3-compatible object storage
- **3D Processing**: Trimesh, NumPy, SciPy
- **Monitoring**: Structured logging with structlog

## 📋 Prerequisites

- Python 3.10 or higher
- Docker and Docker Compose
- PostgreSQL (with PostGIS extension)
- Redis

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd dental-backend
```

### 2. Set Up Development Environment

```bash
# Run the setup script
python scripts/setup_dev_environment.py

# Or manually:
make dev-setup
make install
make build
```

### 3. Start Services

```bash
# Start all services with Docker Compose
make docker-run

# Or start individual services:
make run          # API service
make run-worker   # Background worker
```

### 4. Verify Installation

```bash
# Check API health
curl http://localhost:8000/health

# Test infrastructure
make test-infrastructure

# Run tests
make test

# Check code quality
make lint
```

## 📁 Project Structure

### Services

- **API Service** (`services/api/`): FastAPI REST endpoints for file upload, processing, and retrieval
- **Worker Service** (`services/worker/`): Celery background workers for mesh processing and analysis

### Packages

- **Common Package** (`packages/common/`): Shared models, utilities, and database configurations

### Infrastructure

- **Docker Compose** (`infrastructure/docker-compose.yml`): Local development environment
- **Dockerfiles** (`infrastructure/`): Container configurations for services

### Models

- **Trained Models** (`models/trained/`): Pre-trained ML models for analysis
- **Configurations** (`models/configs/`): Model configuration files
- **Scripts** (`models/scripts/`): Training and evaluation scripts

## 🔧 Development

### Code Quality

```bash
# Format code
make format

# Run fast linting (recommended for development)
make lint

# Run full linting (including type checking and security)
make lint-full

# Run fast pre-commit checks
make pre-commit-fast

# Run type checking only
mypy dental_backend/

# Run security checks only
bandit -r dental_backend/
```

### Testing

```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests
make test-integration

# Check test coverage
pytest --cov=dental_backend --cov-report=html
```

### Database

```bash
# Run migrations
make db-migrate

# Rollback migration
make db-rollback

# Reset database
make db-reset
```

## 🔒 Security & Compliance

### HIPAA Compliance

- End-to-end encryption for data in transit and at rest
- Comprehensive audit logging
- Access controls and authentication
- Data retention policies

### GDPR Compliance

- Data minimization principles
- Right to be forgotten implementation
- Data portability features
- Privacy by design architecture

## 📊 API Documentation

Once the API service is running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

## 🐳 Docker Deployment

### Production

```bash
# Build images
make docker-build

# Run services
make docker-run

# Stop services
make docker-stop
```

### Development

```bash
# Start development environment
docker-compose -f infrastructure/docker-compose.yml up -d

# View logs
docker-compose -f infrastructure/docker-compose.yml logs -f

# Stop services
docker-compose -f infrastructure/docker-compose.yml down
```

## 📈 Monitoring

### Health Checks

- **API Service**: `GET /health`
- **Worker Service**: Celery inspect ping
- **Database**: PostgreSQL connection check
- **Redis**: Connection ping

### Logging

Structured logging with JSON format for easy parsing and analysis:

```python
import structlog

logger = structlog.get_logger()
logger.info("Processing mesh file", file_path=path, format=format_type)
```

## 🤝 Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

### Development Workflow

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following the coding standards
4. Run tests and linting (`make pre-commit`)
5. Commit your changes (`git commit -m 'feat: add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support and questions:

- **Documentation**: Check the [docs/](docs/) directory
- **Issues**: Create an issue in the repository
- **Discussions**: Use GitHub Discussions for questions

## 🗺️ Roadmap

- [ ] Enhanced 3D mesh analysis algorithms
- [ ] Real-time processing capabilities
- [ ] Advanced ML model integration
- [ ] Multi-tenant architecture
- [ ] Advanced monitoring and alerting
- [ ] Performance optimization
- [ ] Additional file format support

---

**Note**: This is a healthcare application. Ensure all deployments meet your organization's security and compliance requirements.

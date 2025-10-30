# Spatial Intelligence Platform

A spatial intelligence platform that enables mall operators to track visitor journeys through outfit-based re-identification across multiple CCTV cameras.

## Project Overview

Transform how property owners understand and optimize visitor flow by combining computer vision, spatial mapping, and behavioral analytics. The platform tracks anonymous visitor journeys using outfit characteristics as identifiers, providing unprecedented insights into customer behavior patterns.

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15
- **Cache/Sessions**: Redis 7
- **Object Storage**: MinIO
- **ORM**: SQLAlchemy 2.0 with Alembic migrations
- **Testing**: Pytest with coverage

### Frontend
- **Framework**: React 18 with Vite
- **Styling**: TailwindCSS
- **Routing**: React Router
- **HTTP Client**: Axios
- **Mapping**: Leaflet with react-leaflet

### Infrastructure
- **Containerization**: Docker & Docker Compose
- **Code Quality**: Black, Flake8, Prettier, ESLint

## Getting Started

### Prerequisites

- Docker Desktop (recommended) OR:
  - Python 3.11+
  - Node.js 18+
  - PostgreSQL 15+
  - Redis 7+

### Quick Start with Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd wandr
   ```

2. **Set up environment variables**
   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   cp frontend/.env.example frontend/.env
   ```

3. **Start all services**
   ```bash
   docker-compose up -d
   ```

4. **Run database migrations**
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

5. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Documentation: http://localhost:8000/api/docs
   - MinIO Console: http://localhost:9001 (minioadmin / minioadmin123)

### Manual Setup (Without Docker)

#### Backend Setup

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your database and Redis connection strings
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start the development server**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

#### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```

4. **Start the development server**
   ```bash
   npm run dev
   ```

## Project Structure

```
wandr/
├── backend/
│   ├── app/
│   │   ├── api/           # API route handlers
│   │   ├── core/          # Core configuration and utilities
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── schemas/       # Pydantic schemas for validation
│   │   ├── services/      # Business logic services
│   │   ├── tests/         # Unit and integration tests
│   │   └── main.py        # FastAPI application entry point
│   ├── alembic/           # Database migrations
│   ├── requirements.txt   # Python dependencies
│   ├── Dockerfile         # Backend container configuration
│   └── .env.example       # Environment variable template
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── services/      # API service layer
│   │   ├── contexts/      # React contexts
│   │   ├── utils/         # Utility functions
│   │   └── App.jsx        # Main application component
│   ├── public/            # Static assets
│   ├── package.json       # Node dependencies
│   ├── Dockerfile         # Frontend container configuration
│   └── .env.example       # Environment variable template
├── Docs/                  # Project documentation
├── docker-compose.yml     # Multi-container orchestration
├── CLAUDE.md             # Project specification
└── README.md             # This file
```

## Development Workflow

### Running Tests

**Backend tests:**
```bash
cd backend
pytest                          # Run all tests
pytest --cov=app               # Run with coverage
pytest app/tests/test_auth.py  # Run specific test file
```

**Frontend tests:**
```bash
cd frontend
npm test                        # Run all tests
npm run test:coverage          # Run with coverage
```

### Code Quality

**Backend formatting and linting:**
```bash
cd backend
black app/                     # Format code
flake8 app/                    # Lint code
mypy app/                      # Type checking
```

**Frontend formatting and linting:**
```bash
cd frontend
npm run lint                   # ESLint
npm run format                 # Prettier
```

### Database Migrations

**Create a new migration:**
```bash
cd backend
alembic revision --autogenerate -m "Description of changes"
```

**Apply migrations:**
```bash
alembic upgrade head
```

**Rollback migration:**
```bash
alembic downgrade -1
```

## Environment Variables

### Backend (.env)
```
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@localhost:5432/spatial_intel
REDIS_URL=redis://localhost:6379/0
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
```

### Frontend (.env)
```
VITE_API_URL=http://localhost:8000
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
- OpenAPI JSON: http://localhost:8000/api/openapi.json

## Current Features (Phase 1)

- [x] Docker-based development environment
- [x] FastAPI backend with SQLAlchemy ORM
- [x] React frontend with TailwindCSS
- [x] PostgreSQL database with Alembic migrations
- [x] Redis session management
- [x] MinIO object storage
- [ ] Authentication system (in progress)
- [ ] Mall and map management (in progress)
- [ ] Camera pin management (in progress)
- [ ] Video upload and storage (in progress)

## Roadmap

### Phase 1: Foundation (Weeks 1-3) - IN PROGRESS
- Initial project setup with Docker
- Authentication and authorization
- Map management with GeoJSON
- Camera pin management
- Video upload infrastructure

### Phase 2: Video Management (Weeks 4-5)
- Video processing pipeline
- FFmpeg integration for proxy generation
- Background job queue with Celery

### Phase 3: Computer Vision - Part 1 (Weeks 6-7)
- Person detection integration
- Garment classification
- Visual embedding extraction
- Tracklet generation

### Phase 4: Computer Vision - Part 2 (Weeks 8-9)
- Within-camera tracking
- Outfit vector computation
- Single-camera testing

### Phase 5: Cross-Camera Re-ID (Weeks 10-11)
- Multi-signal scoring system
- Journey construction
- Confidence scoring

### Phases 6-9: Integration, Reporting, Testing, Documentation (Weeks 12-17)
- See [CLAUDE.md](CLAUDE.md) for complete roadmap

## Contributing

This is currently in active development. For contributions:

1. Follow the code style (Black for Python, Prettier for JavaScript)
2. Write tests for new features
3. Update documentation as needed
4. Ensure all tests pass before committing

## Troubleshooting

### Docker Issues

**Services won't start:**
```bash
docker-compose down -v  # Remove volumes
docker-compose up --build  # Rebuild and start
```

**Database connection issues:**
```bash
docker-compose logs postgres  # Check PostgreSQL logs
```

**MinIO access issues:**
```bash
docker-compose logs minio  # Check MinIO logs
```

### Backend Issues

**Import errors:**
```bash
pip install -r requirements.txt  # Reinstall dependencies
```

**Database migration errors:**
```bash
alembic downgrade -1  # Rollback one migration
alembic upgrade head  # Try again
```

### Frontend Issues

**Module not found:**
```bash
rm -rf node_modules package-lock.json
npm install  # Reinstall dependencies
```

**Build errors:**
```bash
npm run build  # Check for build-time errors
```

## License

[To be determined]

## Contact

For questions or support, please open an issue in the repository.

---

**Version**: 0.1.0 (Phase 1 - In Development)
**Last Updated**: 2025-10-30

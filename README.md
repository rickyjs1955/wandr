# Spatial Intelligence Platform

A spatial intelligence platform that enables mall operators to track visitor journeys through outfit-based re-identification across multiple CCTV cameras.

## Project Overview

Transform how property owners understand and optimize visitor flow by combining computer vision, spatial mapping, and behavioral analytics. The platform tracks anonymous visitor journeys using outfit characteristics as identifiers, providing unprecedented insights into customer behavior patterns.

## 🎉 Phase 2 Complete: Enterprise-Grade Video Management

Phase 2 has been successfully completed, delivering a production-ready video management system:

- ✅ **Multipart Upload System**: Handle videos up to 2GB with resume capability and checksum deduplication
- ✅ **Distributed Processing**: Celery-based background job queue with Redis broker
- ✅ **FFmpeg Pipeline**: Automatic proxy generation (480p) and thumbnail extraction
- ✅ **Secure Streaming**: Auto-refreshing signed URLs with seamless playback continuity
- ✅ **Real-time Monitoring**: Job status tracking, system statistics, and stuck job detection
- ✅ **Production UI**: Drag-and-drop upload, progress tracking, and custom video player
- ✅ **Test Coverage**: E2E integration tests and performance benchmarks

**Ready for Phase 3**: Computer vision integration for person detection and outfit-based re-identification.

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

# Unit tests
pytest app/tests/unit/ -v

# Integration tests (includes E2E video pipeline)
pytest app/tests/integration/ -v

# Performance tests (lightweight benchmarks)
pytest app/tests/performance/ -v -m benchmark

# Heavy benchmarks (opt-in, takes ~1 hour)
RUN_HEAVY_BENCHMARKS=1 pytest app/tests/performance/test_proxy_benchmarks.py::TestProxyGeneration::test_30min_1080p_30fps_benchmark -v

# All tests with coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest app/tests/test_upload_service.py -v
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

### Key API Endpoints (Phase 2)

**Video Upload:**
- `POST /videos/upload/initiate` - Start multipart upload
- `POST /videos/upload/{upload_id}/part-url` - Get presigned URL for part
- `POST /videos/upload/{upload_id}/complete` - Finalize upload

**Video Management:**
- `GET /videos` - List videos with filters
- `GET /videos/{video_id}` - Get video details
- `GET /videos/{video_id}/stream/{stream_type}` - Get streaming URL
- `GET /videos/{video_id}/thumbnail` - Get thumbnail URL
- `DELETE /videos/{video_id}` - Delete video

**Admin Monitoring:**
- `GET /admin/stats` - System statistics
- `GET /admin/jobs` - List processing jobs
- `POST /admin/cleanup/stuck-jobs` - Cleanup stuck jobs
- `POST /admin/cleanup/old-jobs` - Cleanup old jobs

## Current Features

### Infrastructure (Complete)
- [x] Docker-based development environment with Docker Compose
- [x] FastAPI backend with SQLAlchemy ORM
- [x] React 18 frontend with Vite and TailwindCSS
- [x] PostgreSQL 15 database with Alembic migrations
- [x] Redis 7 for session management and Celery broker
- [x] MinIO object storage for video files

### Phase 2: Video Management (Complete)
- [x] **Enhanced Database Schema** (Phase 2.1)
  - Video model with multipart upload support
  - Processing job tracking with Celery task IDs
  - JSONB result data for flexible metadata

- [x] **Object Storage Infrastructure** (Phase 2.2)
  - MinIO integration with bucket management
  - Multipart upload with part namespacing
  - Presigned URL generation for secure access

- [x] **Multipart Upload API** (Phase 2.3)
  - Initiate, upload parts, complete workflow
  - SHA-256 checksum deduplication
  - Abort and cleanup functionality

- [x] **Background Job Queue** (Phase 2.4)
  - Celery worker with Redis broker
  - Job status tracking and progress monitoring
  - Proxy generation queue management

- [x] **FFmpeg Proxy Generation** (Phase 2.5)
  - 480p proxy video creation
  - Thumbnail extraction at 5-second mark
  - Audio stream detection and conditional encoding
  - Metadata extraction (resolution, fps, duration)

- [x] **Video Streaming & Management APIs** (Phase 2.6)
  - Video list, detail, and delete endpoints
  - Signed URL generation for streaming
  - Thumbnail URL generation
  - Proxy and original video streaming

- [x] **Admin Monitoring & Maintenance** (Phase 2.7)
  - System statistics endpoint
  - Stuck job detection and cleanup
  - Job listing and queue statistics
  - Manual cleanup triggers

- [x] **Frontend Upload Components** (Phase 2.8)
  - Drag-and-drop video upload
  - SHA-256 checksum calculation with progress
  - Upload progress tracking
  - Processing status polling with real-time updates
  - React Router navigation

- [x] **Frontend Video Player** (Phase 2.9)
  - Custom video player with controls
  - Auto-refreshing signed URLs
  - Seamless playback during URL refresh
  - Playback state preservation

- [x] **Testing & Validation** (Phase 2.10)
  - End-to-end integration tests
  - Performance benchmarks
  - Test fixtures and utilities

### Pending Features (Phase 1 - Deferred)
- [ ] Authentication system
- [ ] Mall and map management with GeoJSON
- [ ] Camera pin management

## Roadmap

### ✅ Phase 2: Video Management (Complete)
All 10 sub-phases completed:
- Phase 2.1: Database Schema & Migrations
- Phase 2.2: Object Storage Infrastructure
- Phase 2.3: Multipart Upload API
- Phase 2.4: Background Job Queue (Celery + Redis)
- Phase 2.5: FFmpeg Proxy Generation Pipeline
- Phase 2.6: Video Streaming & Management APIs
- Phase 2.7: Admin Monitoring & Stuck Job Watchdog
- Phase 2.8: Frontend Upload Components
- Phase 2.9: Frontend Video Player & Management UI
- Phase 2.10: Integration Testing & Performance Validation

### Phase 3: Computer Vision - Part 1 (Next)
- Person detection with YOLOv8/RT-DETR
- Garment classification (top/bottom/shoes)
- CIELAB color space conversion and quantization
- Visual embedding extraction (CLIP-small)
- Physique attribute extraction
- Tracklet data model and storage

### Phase 4: Computer Vision - Part 2
- Within-camera tracking (ByteTrack/DeepSORT)
- Tracklet generation pipeline
- Outfit vector computation (128D embedding)
- Single-camera footage testing

### Phase 5: Cross-Camera Re-ID
- Multi-signal scoring (outfit + time + adjacency + physique)
- Candidate retrieval with pre-filters
- Association decision logic
- Conflict resolution
- Journey construction algorithm

### Phases 6-9: Integration, Optimization, Reporting, Testing
See [CLAUDE.md](CLAUDE.md) for complete technical roadmap and specifications

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

**Version**: 0.2.0 (Phase 2 - Complete)
**Last Updated**: 2025-11-01
**Status**: Video management system fully operational, ready for computer vision integration

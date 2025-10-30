# Phase 1: Foundation - Development Roadmap

**Duration**: Weeks 1-3
**Status**: Week 2 Complete (Authentication & Session Management) ✅
**Updated**: 2025-10-31

---

## Overview

Phase 1 establishes the foundational infrastructure for the Spatial Intelligence Platform. This phase focuses on core authentication, database architecture, map visualization, and basic camera pin management - all essential building blocks for the computer vision pipeline in later phases.

## Goals

-  Set up a production-ready development environment
- ✅ **Implement secure authentication and session management** *(Week 2 Complete)*
-  Build interactive map viewer with GeoJSON support
-  Create camera pin management system with adjacency graph
-  Design and implement complete database schema
-  Set up video storage infrastructure

---

<!-- #region Week 1: Environment & Database Setup -->
## Week 1: Environment & Database Setup

### Day 1-2: Development Environment

#### Objectives
- Set up containerized development environment
- Configure project structure and dependencies
- Establish development workflows

#### Tasks

**Backend Setup**
- [ ] Initialize Python project with FastAPI/Flask
  - Create virtual environment
  - Install core dependencies: FastAPI, SQLAlchemy, Alembic, Pydantic
  - Configure project structure: `/app`, `/models`, `/routes`, `/services`
- [ ] Set up PostgreSQL database
  - Create Docker Compose configuration
  - Configure database connection pooling
  - Set up environment variable management (.env)
- [ ] Initialize Redis for session management
  - Add Redis container to Docker Compose
  - Configure Redis client connection
  - Set up session storage configuration

**Frontend Setup**
- [ ] Initialize React/Vue.js project
  - Choose framework (recommend React + Vite)
  - Install core dependencies: axios, react-router-dom
  - Configure TailwindCSS for styling
  - Set up project structure: `/components`, `/pages`, `/services`, `/utils`

**Development Tools**
- [ ] Configure Docker Compose for all services
  - PostgreSQL container
  - Redis container
  - Backend API container
  - Frontend dev server
  - Nginx reverse proxy (optional for local dev)
- [ ] Set up development scripts
  - `docker-compose.yml` for full stack
  - Database migration scripts
  - Seed data scripts
- [ ] Configure code quality tools
  - Backend: Black, Flake8, pytest
  - Frontend: ESLint, Prettier
  - Pre-commit hooks

**Deliverables**
-  Working Docker Compose environment
-  Backend API running on http://localhost:8000
-  Frontend running on http://localhost:3000
-  Database accessible and configured
-  Development documentation (README.md)

---

### Day 3-5: Database Schema Implementation

#### Objectives
- Design and implement complete database schema for all phases
- Set up database migrations
- Create ORM models and relationships

#### Database Tables

**Phase 1 Tables (Immediate Use)**

1. **users**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'MALL_OPERATOR',
    mall_id UUID REFERENCES malls(id) ON DELETE CASCADE,
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_mall_id ON users(mall_id);
```

2. **malls**
```sql
CREATE TABLE malls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    geojson_map JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

3. **camera_pins**
```sql
CREATE TABLE camera_pins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mall_id UUID NOT NULL REFERENCES malls(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    label VARCHAR(255),
    location_lat DOUBLE PRECISION NOT NULL,
    location_lng DOUBLE PRECISION NOT NULL,
    pin_type VARCHAR(20) NOT NULL CHECK (pin_type IN ('entrance', 'normal')),
    adjacent_to UUID[],
    store_id UUID REFERENCES stores(id) ON DELETE SET NULL,
    camera_fps INTEGER DEFAULT 15,
    camera_note TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_camera_pins_mall_id ON camera_pins(mall_id);
CREATE INDEX idx_camera_pins_type ON camera_pins(pin_type);
```

4. **videos**
```sql
CREATE TABLE videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_pin_id UUID NOT NULL REFERENCES camera_pins(id) ON DELETE CASCADE,
    file_path VARCHAR(500) NOT NULL,
    original_filename VARCHAR(255),
    file_size_bytes BIGINT,
    upload_timestamp TIMESTAMP DEFAULT NOW(),
    duration_seconds INTEGER,
    processed BOOLEAN DEFAULT FALSE,
    processing_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_videos_camera_pin_id ON videos(camera_pin_id);
CREATE INDEX idx_videos_processing_status ON videos(processing_status);
```

**Future-Use Tables (Scaffolded)**

5. **stores**
```sql
CREATE TABLE stores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mall_id UUID NOT NULL REFERENCES malls(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    polygon JSONB,
    tenant_id UUID REFERENCES tenants(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_stores_mall_id ON stores(mall_id);
```

6. **tenants**
```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mall_id UUID NOT NULL REFERENCES malls(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    contact_email VARCHAR(255),
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_tenants_mall_id ON tenants(mall_id);
```

7. **visitor_profiles**
```sql
CREATE TABLE visitor_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outfit_hash VARCHAR(64) NOT NULL,
    detection_date DATE NOT NULL,
    outfit JSONB NOT NULL,
    first_seen TIMESTAMP NOT NULL,
    last_seen TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_visitor_profiles_date ON visitor_profiles(detection_date);
CREATE INDEX idx_visitor_profiles_outfit_hash ON visitor_profiles(outfit_hash);
```

8. **tracklets**
```sql
CREATE TABLE tracklets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mall_id UUID NOT NULL REFERENCES malls(id) ON DELETE CASCADE,
    pin_id UUID NOT NULL REFERENCES camera_pins(id) ON DELETE CASCADE,
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL,
    t_in TIMESTAMP NOT NULL,
    t_out TIMESTAMP NOT NULL,
    outfit_vec FLOAT[],
    outfit_json JSONB,
    physique JSONB,
    box_stats JSONB,
    quality FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_tracklets_video_id ON tracklets(video_id);
CREATE INDEX idx_tracklets_pin_id ON tracklets(pin_id);
CREATE INDEX idx_tracklets_time ON tracklets(t_in, t_out);
```

9. **associations**
```sql
CREATE TABLE associations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mall_id UUID NOT NULL REFERENCES malls(id) ON DELETE CASCADE,
    from_tracklet_id UUID NOT NULL REFERENCES tracklets(id) ON DELETE CASCADE,
    to_tracklet_id UUID NOT NULL REFERENCES tracklets(id) ON DELETE CASCADE,
    score FLOAT NOT NULL,
    decision VARCHAR(20) NOT NULL,
    scores JSONB,
    components JSONB,
    candidate_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_associations_mall_id ON associations(mall_id);
CREATE INDEX idx_associations_from_tracklet ON associations(from_tracklet_id);
CREATE INDEX idx_associations_to_tracklet ON associations(to_tracklet_id);
```

10. **journeys**
```sql
CREATE TABLE journeys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    visitor_id UUID NOT NULL REFERENCES visitor_profiles(id) ON DELETE CASCADE,
    mall_id UUID NOT NULL REFERENCES malls(id) ON DELETE CASCADE,
    journey_date DATE NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    exit_time TIMESTAMP,
    total_duration_minutes INTEGER,
    confidence FLOAT,
    path JSONB NOT NULL,
    entry_point UUID REFERENCES camera_pins(id),
    exit_point UUID REFERENCES camera_pins(id),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_journeys_mall_id ON journeys(mall_id);
CREATE INDEX idx_journeys_visitor_id ON journeys(visitor_id);
CREATE INDEX idx_journeys_date ON journeys(journey_date);
CREATE INDEX idx_journeys_confidence ON journeys(confidence);
```

#### Tasks

- [ ] **Create Alembic migrations**
  - Initialize Alembic in project
  - Create initial migration with all tables
  - Test migration up/down

- [ ] **Implement ORM models**
  - Create SQLAlchemy models for all tables
  - Define relationships and foreign keys
  - Add model validators using Pydantic

- [ ] **Create database utilities**
  - Database connection manager
  - Transaction context managers
  - Query helpers and base repository pattern

- [ ] **Seed initial data**
  - Create sample mall record
  - Create test user (mall operator)
  - Add sample GeoJSON map data

**Deliverables**
-  Complete database schema implemented
-  All ORM models created and tested
-  Database migration scripts
-  Seed data script with sample mall

---
<!-- #endregion -->

<!-- #region Week 2: Authentication & Session Management -->
## Week 2: Authentication & Session Management

### Day 1-3: Core Authentication System

#### Objectives
- Implement secure password-based authentication
- Set up session management with Redis
- Create authentication middleware
- Build login/logout endpoints

#### Security Requirements

**Password Security**
- Use bcrypt or Argon2 for password hashing
- Minimum password requirements: 8+ characters, complexity rules
- Salt passwords before hashing
- Never store plaintext passwords

**Session Management**
- HttpOnly cookies for session tokens
- Secure flag for HTTPS environments
- SameSite=Strict for CSRF protection
- Session expiration: 24 hours default, configurable
- Redis-backed session storage for scalability

**API Security**
- CORS configuration for frontend origin
- CSRF token validation for state-changing requests
- Rate limiting on authentication endpoints
- Request logging for security audit

#### Tasks

**Backend Implementation**

- [x] **Password hashing service** ✅ *Completed 2025-10-31*
  ```python
  # services/auth_service.py
  - hash_password(password: str) -> str
  - verify_password(password: str, hashed: str) -> bool
  - needs_rehash(hashed: str) -> bool
  - get_password_strength(password: str) -> dict
  ```
  *Implementation: Argon2id (64MB, 3 iterations, 4 threads) with bcrypt fallback*

- [x] **Session service** ✅ *Completed 2025-10-31*
  ```python
  # services/session_service.py
  - create_session(user_id: str) -> str  # returns session_id
  - get_session(session_id: str) -> dict
  - delete_session(session_id: str) -> bool
  - extend_session(session_id: str) -> bool
  - delete_user_sessions(user_id: UUID) -> int
  - health_check() -> bool
  ```
  *Implementation: Redis-backed with auto-expiry and activity refresh*

- [x] **Authentication middleware** ✅ *Completed 2025-10-31*
  ```python
  # api/v1/auth.py
  - Dependency injection via get_current_user()
  - Session validation with HttpOnly cookies
  - Role scaffolding (UserRole enum in models)
  ```
  *Note: Full RBAC middleware (@require_role) deferred to Week 3*

- [x] **Authentication endpoints** ✅ *Completed 2025-10-31*
  ```python
  # api/v1/auth.py
  POST   /api/v1/auth/login      # Login and create session
  POST   /api/v1/auth/logout     # Destroy session
  GET    /api/v1/auth/me         # Get current user info
  POST   /api/v1/auth/refresh    # Extend session
  GET    /api/v1/auth/health     # Service health check
  ```

**Login Endpoint Implementation**
```python
@router.post("/auth/login")
async def login(credentials: LoginCredentials, response: Response):
    # 1. Validate email format
    # 2. Query user by email
    # 3. Verify password
    # 4. Create session in Redis
    # 5. Set HttpOnly cookie
    # 6. Return user info (no sensitive data)
    pass
```

**Logout Endpoint Implementation**
```python
@router.post("/auth/logout")
async def logout(session_id: str, response: Response):
    # 1. Delete session from Redis
    # 2. Clear cookie
    # 3. Return success
    pass
```

**Frontend Implementation**

- [x] **Authentication service** ✅ *Completed 2025-10-31*
  ```javascript
  // services/authService.js
  - login(username, password)
  - logout()
  - getCurrentUser()
  - isAuthenticated()
  - refreshSession()
  - checkAuthHealth()
  ```
  *Implementation: Axios client with withCredentials for cookie support*

- [x] **Login page component** ✅ *Completed 2025-10-31*
  - Email/password form with real-time validation
  - Field-level and global error display
  - Loading states with spinner
  - Show/hide password toggle
  - Auto-redirect if already authenticated
  - Redirect to intended page after login
  - Responsive design with Tailwind CSS
  *File: frontend/src/pages/Login.jsx*

- [x] **Protected route wrapper** ✅ *Completed 2025-10-31*
  - Check authentication status with loading spinner
  - Redirect to /login if unauthenticated
  - Preserve intended destination for post-login redirect
  - Handle session expiration gracefully
  *File: frontend/src/components/ProtectedRoute.jsx*

- [x] **Auth context provider** ✅ *Completed 2025-10-31*
  - Global authentication state with React Context
  - Current user information
  - Auth actions (login, logout, refresh)
  - Automatic session initialization on mount
  - Automatic session refresh every 20 minutes
  - useAuth() hook for components
  *File: frontend/src/contexts/AuthContext.jsx*

#### Testing

- [x] **Unit tests** ✅ *Completed 2025-10-31*
  - Password hashing and verification (25 tests)
  - Session creation and retrieval (20 tests)
  - Password strength evaluation
  - Hash uniqueness verification
  - Edge cases (empty passwords, long passwords, unicode)
  *Files: test_auth_service.py, test_session_service.py*

- [x] **Integration tests** ✅ *Completed 2025-10-31*
  - Login with valid credentials (username and email)
  - Login with invalid credentials
  - Logout and session cleanup
  - Access protected route without auth
  - Access protected route with valid session
  - Session refresh and expiration
  - Complete auth flow (login → access → logout → denied)
  *File: test_auth_endpoints.py (25 tests)*

- [x] **Security tests** ✅ *Completed 2025-10-31*
  - Password hash uniqueness (same password → different hashes)
  - Session isolation (user A cannot access user B's session)
  - Cookie security flags (HttpOnly, SameSite)
  - Timing attack resistance
  - User enumeration prevention
  - Session fixation prevention
  - SQL injection protection
  - XSS payload handling
  *File: test_security.py (20 tests)*

**Test Coverage**: 90 tests total across 4 test files
- Unit tests: 45 tests
- Integration tests: 25 tests
- Security tests: 20 tests
- **Coverage: >80% achieved** ✅

**Deliverables**
- ✅ Secure authentication system
- ✅ Session management with Redis
- ✅ Login/logout API endpoints
- ✅ Frontend login page and auth flow
- ✅ Authentication middleware
- ✅ Test coverage >80%

**Status: Week 2 (Phase 1.2) COMPLETE** ✅ *Completed 2025-10-31*
---

### Day 4-5: Role Scaffolding & Authorization

#### Objectives
- Implement role-based access control (RBAC) foundation
- Create role-checking middleware
- Set up authorization decorators

#### Role Definitions

**MVP Roles**
- `MALL_OPERATOR`: Full access to mall data, camera management, and analytics

**Future Roles (Scaffolded)**
- `TENANT_MANAGER`: Manage tenant-specific settings and users
- `TENANT_VIEWER`: Read-only access to tenant analytics

#### Tasks

- [ ] **Authorization middleware**
  ```python
  # middleware/authz_middleware.py
  - require_role(*roles: str)  # Check user has one of roles
  - require_mall_access(mall_id: str)  # Verify user belongs to mall
  - require_tenant_access(tenant_id: str)  # Future use
  ```

- [ ] **Apply authorization to endpoints**
  ```python
  @router.get("/malls/{mall_id}")
  @require_auth()
  @require_mall_access()
  async def get_mall(mall_id: str):
      pass
  ```

- [ ] **Frontend role handling**
  - Store user role in auth context
  - Conditionally render UI based on role
  - Feature flags for future functionality

- [ ] **Database validation**
  - Ensure user role is valid enum
  - Foreign key constraints for mall_id/tenant_id
  - Database-level role checks (optional)

**Deliverables**
-  RBAC middleware implemented
-  Role-based route protection
-  Frontend role-aware UI
-  Documentation for role system

---
<!-- #endregion -->

<!-- #region Week 3: Map Viewer & Camera Pin Management -->
## Week 3: Map Viewer & Camera Pin Management

### Day 1-2: GeoJSON Map Viewer

#### Objectives
- Implement interactive map viewer using Leaflet or Mapbox GL JS
- Support GeoJSON-based mall floor plans
- Enable camera pin visualization on map

#### Technology Choice

**Option A: Leaflet (Recommended for MVP)**
- Pros: Lightweight, easy to integrate, good GeoJSON support
- Cons: Less visually polished than Mapbox
- Best for: Indoor maps, custom overlays

**Option B: Mapbox GL JS**
- Pros: Beautiful rendering, advanced features
- Cons: Requires API key, more complex setup
- Best for: Outdoor maps, 3D visualization

**Recommendation**: Start with Leaflet for simplicity, migrate to Mapbox if needed

#### Tasks

**Backend: Map Management API**

- [ ] **Implement mall endpoints**
  ```python
  GET    /malls/{mall_id}           # Get mall details
  GET    /malls/{mall_id}/map       # Get GeoJSON map
  PUT    /malls/{mall_id}/map       # Upload/update GeoJSON map
  ```

- [ ] **GeoJSON validation**
  - Validate GeoJSON structure
  - Ensure FeatureCollection format
  - Validate coordinate system (WGS84)
  - Check for required properties

- [ ] **Map storage**
  - Store GeoJSON in PostgreSQL JSONB field
  - Index for efficient queries
  - Version control (optional for MVP)

**Frontend: Map Viewer Component**

- [ ] **Install and configure Leaflet**
  ```bash
  npm install leaflet react-leaflet
  ```

- [ ] **Create MapViewer component**
  ```javascript
  // components/MapViewer.jsx
  - Display GeoJSON floor plan
  - Render camera pins as markers
  - Support zoom/pan
  - Click handlers for pins
  ```

- [ ] **Map controls**
  - Zoom in/out buttons
  - Reset view button
  - Layer toggle (floor plan, pins, stores)

- [ ] **Map styling**
  - Custom pin icons (entrance vs normal)
  - Pin labels on hover
  - Selected pin highlight
  - Adjacency lines visualization (optional)

- [ ] **Map upload interface**
  - File upload for GeoJSON
  - Preview before save
  - Validation feedback
  - Success/error messages

#### Sample GeoJSON Structure

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[
          [103.8198, 1.3521],
          [103.8205, 1.3521],
          [103.8205, 1.3528],
          [103.8198, 1.3528],
          [103.8198, 1.3521]
        ]]
      },
      "properties": {
        "type": "floor_plan",
        "level": 1,
        "name": "Level 1"
      }
    }
  ]
}
```

**Deliverables**
-  Interactive map viewer component
-  GeoJSON upload and storage
-  Map display with floor plan
-  Basic map controls

---

### Day 3-5: Camera Pin Management

#### Objectives
- Implement CRUD operations for camera pins
- Build UI for adding/editing pins on map
- Support adjacency relationship management
- Enable video upload association

#### Backend: Camera Pin API

- [ ] **Implement pin endpoints**
  ```python
  GET    /malls/{mall_id}/pins                 # List all pins
  POST   /malls/{mall_id}/pins                 # Create pin
  GET    /malls/{mall_id}/pins/{pin_id}        # Get pin details
  PATCH  /malls/{mall_id}/pins/{pin_id}        # Update pin
  DELETE /malls/{mall_id}/pins/{pin_id}        # Delete pin
  ```

- [ ] **Pin creation logic**
  - Validate coordinates within mall bounds
  - Generate unique pin ID
  - Set default values (fps=15, type=normal)
  - Store in database

- [ ] **Adjacency management**
  - Validate adjacent_to references existing pins
  - Prevent self-adjacency
  - Bidirectional relationship helper (optional)
  - Graph validation (no orphaned nodes)

- [ ] **Pin validation**
  - Coordinates within valid range
  - Pin type is 'entrance' or 'normal'
  - Adjacent pins exist in same mall
  - Camera FPS > 0

**Frontend: Pin Management UI**

- [ ] **Add Pin Mode**
  - Click map to place new pin
  - Modal/form to enter pin details:
    - Name (required)
    - Label (optional)
    - Type: entrance | normal
    - Camera FPS (default: 15)
    - Camera notes
  - Save pin to backend
  - Update map with new pin

- [ ] **Edit Pin Mode**
  - Click existing pin to edit
  - Pre-populate form with current values
  - Update pin details
  - Reflect changes on map

- [ ] **Delete Pin**
  - Confirmation dialog
  - Remove from backend
  - Remove from map
  - Handle cascade (videos, tracklets)

- [ ] **Adjacency Editor**
  - Visual connection mode
  - Click two pins to create adjacency
  - Display adjacency lines on map
  - Remove adjacency connections
  - Validation for adjacency logic

- [ ] **Pin List Sidebar**
  - List all pins in mall
  - Filter by type (entrance/normal)
  - Search by name
  - Click to highlight on map

#### Pin Management Features

**Pin Display**
- Different icons for entrance vs normal pins
- Color coding by status (has videos, processing)
- Tooltip with pin name and type
- Selected state highlighting

**Adjacency Visualization**
- Lines connecting adjacent pins
- Directional arrows (optional)
- Distance labels (optional)
- Transit time indicators (future)

**Batch Operations**
- Import pins from CSV/JSON
- Export pin configuration
- Duplicate pin settings
- Bulk delete (with confirmation)

#### Tasks

- [ ] **PinManager component**
  ```javascript
  // components/PinManager.jsx
  - Add/Edit/Delete pins
  - Adjacency editor
  - Pin list view
  - Integration with MapViewer
  ```

- [ ] **Pin form validation**
  - Required fields
  - Coordinate format validation
  - Unique name within mall
  - FPS range validation

- [ ] **Error handling**
  - Backend validation errors
  - Network errors
  - Optimistic UI updates
  - Rollback on failure

**Deliverables**
-  Full CRUD for camera pins
-  Pin management UI on map
-  Adjacency relationship editor
-  Pin list and filtering
-  Form validation and error handling

---
<!-- #endregion -->

<!-- #region Object Storage Setup -->
## Object Storage Setup

### Objectives
- Configure S3-compatible storage for video files
- Implement secure file upload
- Set up signed URL generation for video access

### Technology Options

**Option A: AWS S3**
- Pros: Highly reliable, scalable, global CDN
- Cons: Cost, requires AWS account
- Best for: Production deployment

**Option B: MinIO (Self-hosted)**
- Pros: Free, S3-compatible API, local control
- Cons: Requires server management
- Best for: Development, private cloud

**Option C: Local File System**
- Pros: Simple, no external dependencies
- Cons: Not scalable, no redundancy
- Best for: Development only

**Recommendation**: MinIO for development, AWS S3 for production

### Tasks

- [ ] **Set up storage service**
  - Add MinIO container to Docker Compose
  - Create storage bucket for videos
  - Configure access credentials
  - Set up CORS for frontend uploads

- [ ] **Implement storage client**
  ```python
  # services/storage_service.py
  - upload_file(file, bucket, key) -> str  # Returns file path
  - get_file_url(bucket, key, expiry) -> str  # Signed URL
  - delete_file(bucket, key) -> bool
  - list_files(bucket, prefix) -> List[str]
  ```

- [ ] **Video upload endpoint**
  ```python
  POST /malls/{mall_id}/pins/{pin_id}/uploads
  - Accept multipart/form-data
  - Validate file type (MP4, AVI, MOV)
  - Validate file size (max 2GB)
  - Generate unique filename
  - Upload to storage
  - Create video record in database
  - Return video metadata
  ```

- [ ] **Video access endpoint**
  ```python
  GET /videos/{video_id}/proxy
  - Generate signed URL (valid 1 hour)
  - Return URL or redirect
  - Log access for audit
  ```

- [ ] **Frontend upload component**
  - File picker UI
  - Upload progress indicator
  - Drag-and-drop support
  - Multiple file upload
  - Error handling

**Deliverables**
-  Object storage configured
-  Video upload API
-  Signed URL generation
-  Frontend upload component

---
<!-- #endregion -->

<!-- #region Testing & Documentation -->
## Testing & Documentation

### Testing Requirements

**Unit Tests**
- [ ] Authentication service tests
- [ ] Session management tests
- [ ] Database model tests
- [ ] API endpoint tests
- [ ] Authorization middleware tests

**Integration Tests**
- [ ] End-to-end authentication flow
- [ ] Map upload and retrieval
- [ ] Pin CRUD operations
- [ ] Video upload and access
- [ ] Session expiration handling

**Frontend Tests**
- [ ] Component rendering tests
- [ ] User interaction tests
- [ ] API integration tests
- [ ] Form validation tests

**Target Coverage**: >80% for backend, >70% for frontend

### Documentation

- [ ] **README.md**
  - Project overview
  - Setup instructions
  - Environment configuration
  - Running locally
  - Running tests

- [ ] **API Documentation**
  - OpenAPI/Swagger specification
  - Endpoint descriptions
  - Request/response examples
  - Authentication guide

- [ ] **Database Documentation**
  - Schema diagram
  - Table descriptions
  - Relationship mappings
  - Migration guide

- [ ] **Development Guide**
  - Project structure
  - Coding standards
  - Git workflow
  - Debugging tips

**Deliverables**
-  Comprehensive test suite
-  API documentation
-  Developer documentation
-  Setup guide

---
<!-- #endregion -->

<!-- #region Phase 1 Deliverables & Success Criteria -->
## Phase 1 Deliverables & Success Criteria

### Completed Deliverables

**Infrastructure**
-  Dockerized development environment
-  PostgreSQL database with complete schema
-  Redis session storage
-  Object storage (MinIO/S3)
-  Backend API server (FastAPI/Flask)
-  Frontend application (React/Vue)

**Authentication & Authorization**
-  Secure login/logout functionality
-  Session management with HttpOnly cookies
-  Password hashing with bcrypt/Argon2
-  Role-based access control middleware
-  Protected API routes

**Map Management**
-  GeoJSON map upload and storage
-  Interactive map viewer (Leaflet/Mapbox)
-  Map display with floor plan overlay
-  Zoom, pan, and navigation controls

**Camera Pin Management**
-  Create, read, update, delete pins
-  Pin placement on interactive map
-  Entrance vs normal pin designation
-  Adjacency relationship management
-  Pin metadata (name, label, FPS, notes)
-  Pin list and filtering UI

**Video Management (Basic)**
-  Video upload to object storage
-  Video metadata storage in database
-  Signed URL generation for access
-  Video association with camera pins

### Success Criteria

**Functional Requirements**
- [ ] Mall operator can log in with email/password
- [ ] Session persists across page refreshes
- [ ] Mall operator can upload a GeoJSON map
- [ ] GeoJSON map displays correctly in browser
- [ ] Mall operator can add camera pins by clicking map
- [ ] Mall operator can edit pin properties
- [ ] Mall operator can delete pins with confirmation
- [ ] Mall operator can define pin adjacency relationships
- [ ] Mall operator can upload MP4 video to a pin
- [ ] Uploaded video metadata is stored and retrievable

**Performance Requirements**
- [ ] Login response time < 500ms
- [ ] Map loads in < 2 seconds
- [ ] Pin creation/update < 300ms
- [ ] Video upload supports files up to 2GB
- [ ] API endpoints respond in < 1 second (95th percentile)

**Security Requirements**
- [ ] Passwords are hashed (never stored plaintext)
- [ ] Sessions expire after 24 hours
- [ ] HttpOnly cookies prevent XSS attacks
- [ ] CORS configured for frontend origin only
- [ ] File uploads validate type and size
- [ ] SQL injection prevented (parameterized queries)

**Code Quality**
- [ ] Backend test coverage > 80%
- [ ] Frontend test coverage > 70%
- [ ] No critical security vulnerabilities
- [ ] Code passes linting standards
- [ ] API documented with OpenAPI/Swagger

### Known Limitations (Phase 1)

- No video processing or analysis yet
- No real-time video streaming
- No journey tracking or analytics
- No tenant management UI
- Basic error handling (enhanced in Phase 2)

---
<!-- #endregion -->

<!-- #region Risks & Mitigation -->
## Risks & Mitigation

### Technical Risks

**Risk 1: GeoJSON Format Incompatibility**
- **Impact**: High - Map viewer may not render correctly
- **Probability**: Medium
- **Mitigation**:
  - Validate GeoJSON structure on upload
  - Provide sample GeoJSON templates
  - Support multiple coordinate systems
  - Test with various GeoJSON sources

**Risk 2: Video Upload Performance**
- **Impact**: Medium - Poor UX for large file uploads
- **Probability**: Medium
- **Mitigation**:
  - Implement chunked upload for files >500MB
  - Show progress indicator
  - Support resume on network interruption
  - Set reasonable file size limits (2GB)

**Risk 3: Session Management Scalability**
- **Impact**: Low - Redis memory exhaustion
- **Probability**: Low (not expected in Phase 1)
- **Mitigation**:
  - Set session TTL to auto-expire
  - Monitor Redis memory usage
  - Configure Redis eviction policy
  - Plan for Redis clustering in production

**Risk 4: Frontend Map Performance**
- **Impact**: Medium - Slow rendering with many pins
- **Probability**: Low (expect <50 pins in MVP)
- **Mitigation**:
  - Use marker clustering for >20 pins
  - Lazy-load pin details
  - Optimize GeoJSON complexity
  - Implement virtual scrolling for pin list

### Project Risks

**Risk 1: Scope Creep**
- **Impact**: High - Delays Phase 2 timeline
- **Probability**: Medium
- **Mitigation**:
  - Strict adherence to Phase 1 scope
  - Defer non-essential features
  - Regular scope reviews
  - Document "Future Enhancement" backlog

**Risk 2: Technology Learning Curve**
- **Impact**: Medium - Development slowdown
- **Probability**: Medium (depends on team experience)
- **Mitigation**:
  - Allocate learning time in estimates
  - Pair programming for new tech
  - Use well-documented libraries
  - Prototype complex features early

---
<!-- #endregion -->

<!-- #region Next Steps (Phase 2 Preview) -->
## Next Steps: Phase 2 Preview

**Phase 2: Video Management (Weeks 4-5)**

Upon completion of Phase 1, the team will proceed to:

1. **FFmpeg Pipeline**
   - Video transcoding and compression
   - Proxy video generation (480p, 10fps)
   - Thumbnail extraction

2. **Background Job Queue**
   - Celery/RQ setup with Redis
   - Job status tracking
   - Retry logic and error handling

3. **Video Metadata Management**
   - Duration extraction
   - Frame rate detection
   - Resolution analysis

4. **Enhanced Video UI**
   - Video playback in browser
   - Thumbnail previews
   - Processing status indicators

**Key Dependencies from Phase 1:**
-  Object storage configured
-  Database schema includes video tables
-  Video upload endpoint functional
-  Authentication protects video access

---
<!-- #endregion -->

## Appendix

### Technology Stack Summary

**Backend**
- Language: Python 3.9+
- Framework: FastAPI or Flask
- ORM: SQLAlchemy
- Migrations: Alembic
- Validation: Pydantic
- Auth: bcrypt/Argon2
- Session: Redis
- Testing: pytest

**Frontend**
- Framework: React 18+ or Vue 3
- Build Tool: Vite
- Styling: TailwindCSS
- Map: Leaflet or Mapbox GL JS
- HTTP Client: Axios
- Routing: React Router / Vue Router
- Testing: Jest, React Testing Library

**Infrastructure**
- Database: PostgreSQL 13+
- Cache: Redis 6+
- Storage: MinIO (dev) / AWS S3 (prod)
- Containerization: Docker + Docker Compose
- Reverse Proxy: Nginx (optional)

### Useful Resources

**GeoJSON**
- Specification: https://geojson.org/
- Validator: https://geojsonlint.com/
- Example generator: https://geojson.io/

**Leaflet**
- Documentation: https://leafletjs.com/reference.html
- GeoJSON tutorial: https://leafletjs.com/examples/geojson/
- React Leaflet: https://react-leaflet.js.org/

**FastAPI**
- Documentation: https://fastapi.tiangolo.com/
- Authentication: https://fastapi.tiangolo.com/tutorial/security/
- Testing: https://fastapi.tiangolo.com/tutorial/testing/

**PostgreSQL**
- JSONB: https://www.postgresql.org/docs/current/datatype-json.html
- UUID: https://www.postgresql.org/docs/current/datatype-uuid.html
- Indexing: https://www.postgresql.org/docs/current/indexes.html

---

## Version History

**v1.0** - 2025-10-30
- Initial Phase 1 roadmap
- Complete task breakdown for Weeks 1-3
- Database schema design
- Success criteria defined

---

**Document Owner**: Development Team
**Last Updated**: 2025-10-30
**Status**: Active Development Planning

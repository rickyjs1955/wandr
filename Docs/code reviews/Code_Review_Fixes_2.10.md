# Phase 2.10 Code Review Fixes

## Issues Addressed

### HIGH Priority Issue 1: Incorrect Method Name in E2E Test
**Location**: `backend/tests/integration/test_video_pipeline_e2e.py:136`

**Problem**: The end-to-end integration test called `upload_service.initiate_multipart_upload(...)`, but the actual service method is named `initiate_upload(...)`. This caused an immediate `AttributeError` when running the test suite, preventing the flagship end-to-end test from ever executing. The entire integration test suite was non-functional due to this method name mismatch.

**Root Cause**: Method naming inconsistency between test code and service implementation. The service was refactored or initially implemented with a shorter method name, but the test was written with the longer, more descriptive name.

**Fix**: Updated the method call to use the correct name:

```python
# Before (line 136):
init_response = upload_service.initiate_multipart_upload(
    mall_id=test_mall.id,
    pin_id=test_pin.id,
    filename="test_video_e2e.mp4",
    file_size_bytes=file_size,
    checksum_sha256=checksum,
    metadata={
        "recorded_at": datetime.utcnow().isoformat(),
        "operator_notes": "E2E test video"
    }
)

# After (line 136):
init_response = upload_service.initiate_upload(
    mall_id=test_mall.id,
    pin_id=test_pin.id,
    filename="test_video_e2e.mp4",
    file_size_bytes=file_size,
    checksum_sha256=checksum,
    metadata={
        "recorded_at": datetime.utcnow().isoformat(),
        "operator_notes": "E2E test video"
    }
)
```

**Impact**:
- E2E integration test can now run without immediate failure
- Complete video pipeline can be tested end-to-end
- CI/CD pipeline can validate full workflow
- Regression testing is now functional

**Files Modified**:
- `backend/tests/integration/test_video_pipeline_e2e.py` (line 136)

---

### HIGH Priority Issue 2: Invalid CameraPin Fixture Construction
**Location**: `backend/tests/integration/test_video_pipeline_e2e.py:48-54`

**Problem**: The test fixture constructed a `CameraPin` with incorrect field names and types:
1. **Invalid `id` type**: Used string `"test-pin-e2e"` instead of UUID
2. **Wrong location field**: Used dict `location={"lat": ..., "lng": ...}` instead of separate `location_lat` and `location_lng` float fields

This caused fixture setup to crash with `TypeError` (string where UUID expected) and `DataError` (invalid column name) before any test assertions could run. None of the integration tests were executable because the fixture creation failed.

**Root Cause**: Mismatch between test fixture code and actual ORM model schema. The `CameraPin` model uses:
- `id: UUID` (not string)
- `location_lat: Float` and `location_lng: Float` (not dict with `location` key)

**Fix**: Updated fixture to match ORM model schema:

```python
# Before (lines 48-54):
pin = CameraPin(
    id="test-pin-e2e",
    mall_id=test_mall.id,
    name="Test Camera E2E",
    label="Entrance A",
    location={"lat": 1.3521, "lng": 103.8198},
    pin_type="entrance"
)

# After (lines 49-56):
import uuid  # Added import

pin = CameraPin(
    id=uuid.uuid4(),
    mall_id=test_mall.id,
    name="Test Camera E2E",
    label="Entrance A",
    location_lat=1.3521,
    location_lng=103.8198,
    pin_type="entrance"
)
```

**Changes Made**:
1. Added `import uuid` at line 19
2. Changed `id="test-pin-e2e"` to `id=uuid.uuid4()` for proper UUID type
3. Changed `location={"lat": 1.3521, "lng": 103.8198}` to separate fields:
   - `location_lat=1.3521`
   - `location_lng=103.8198`

**Impact**:
- Test fixtures can now be created successfully
- Integration tests can run through setup phase
- Database operations work with correct types
- Tests can proceed to actual assertions

**Files Modified**:
- `backend/tests/integration/test_video_pipeline_e2e.py` (import line 19, fixture lines 50, 54-55)

---

### HIGH Priority Issue 3: Unbounded Heavy Benchmark Test
**Location**: `backend/tests/performance/test_proxy_benchmarks.py:168-217`

**Problem**: The `test_30min_1080p_30fps_benchmark` test generated a 30-minute 1080p video and processed it as part of the default test run. This single test:
- Creates multi-GB video artifacts (can exceed 5GB)
- Takes close to an hour to complete on typical hardware
- Consumes significant system resources (4GB+ memory)
- Makes the performance test suite practically unusable for CI and local development
- Causes timeout failures in CI pipelines

Running `pytest backend/tests/performance/` would inadvertently trigger this test, blocking developers for up to an hour and potentially filling disk space.

**Root Cause**: No opt-in mechanism for extremely resource-intensive tests. The test was always included in default runs despite being marked with `@pytest.mark.slow`, which doesn't skip tests by default.

**Fix**: Added `skipif` marker to gate the test behind an environment variable:

```python
# Before (lines 166-173):
@pytest.mark.benchmark
@pytest.mark.slow
def test_30min_1080p_30fps_benchmark(self, generate_test_video, measure_performance, tmp_path):
    """
    Benchmark: 30-minute 1080p/30fps clip

    Target: <60 minutes processing time (2x real-time)
    """

# After (lines 166-180):
@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("RUN_HEAVY_BENCHMARKS") != "1",
    reason="Heavy benchmark test (30min video, multi-GB artifacts). Set RUN_HEAVY_BENCHMARKS=1 to run."
)
def test_30min_1080p_30fps_benchmark(self, generate_test_video, measure_performance, tmp_path):
    """
    Benchmark: 30-minute 1080p/30fps clip

    Target: <60 minutes processing time (2x real-time)

    NOTE: This test is skipped by default due to resource requirements.
    Run with: RUN_HEAVY_BENCHMARKS=1 pytest backend/tests/performance/test_proxy_benchmarks.py::TestProxyGeneration::test_30min_1080p_30fps_benchmark -v
    """
```

**Implementation Details**:
- **Skip condition**: Test runs only if `RUN_HEAVY_BENCHMARKS=1` is set in environment
- **Clear reason**: Skip message explains why and how to enable
- **Updated docstring**: Documents the opt-in requirement
- **Preserves markers**: Keeps `@pytest.mark.benchmark` and `@pytest.mark.slow` for filtering

**Usage Examples**:

```bash
# Default run - skips heavy benchmark
pytest backend/tests/performance/test_proxy_benchmarks.py -v

# Opt-in to heavy benchmark
RUN_HEAVY_BENCHMARKS=1 pytest backend/tests/performance/test_proxy_benchmarks.py::TestProxyGeneration::test_30min_1080p_30fps_benchmark -v

# Run all benchmarks including heavy ones
RUN_HEAVY_BENCHMARKS=1 pytest backend/tests/performance/ -v -m benchmark
```

**Benefits**:
- Default test runs complete quickly (seconds/minutes instead of hours)
- CI pipelines no longer timeout or fail due to resource exhaustion
- Developers can run performance tests locally without long waits
- Heavy benchmarks still available for performance validation when needed
- Explicit opt-in prevents accidental triggering

**Files Modified**:
- `backend/tests/performance/test_proxy_benchmarks.py` (lines 168-180)

---

## Summary

All three HIGH priority issues in Phase 2.10 have been resolved:

1.  Fixed method name in E2E test - changed `initiate_multipart_upload` to `initiate_upload`
2.  Fixed CameraPin fixture - corrected field names (`location_lat`, `location_lng`) and ID type (UUID)
3.  Gated heavy benchmark test - added opt-in flag to prevent default execution

**Key Improvements**:
- **Integration Tests Now Run**: E2E test suite is executable and can validate full pipeline
- **Fixture Setup Works**: Database fixtures create correctly with proper types and schemas
- **Performance Tests Usable**: Default test runs complete quickly without multi-GB artifacts
- **CI/CD Functional**: Test suite no longer causes timeout or resource exhaustion in CI

**Files Modified**: 2
- `backend/tests/integration/test_video_pipeline_e2e.py` (method name, fixture construction, import)
- `backend/tests/performance/test_proxy_benchmarks.py` (skip condition for heavy benchmark)

**Testing Recommendation**:

**Integration Tests**:
```bash
# Run E2E integration tests
pytest backend/tests/integration/test_video_pipeline_e2e.py -v

# Should complete without AttributeError, TypeError, or DataError
# Verifies: upload � processing � streaming � cleanup workflow
```

**Performance Tests**:
```bash
# Run lightweight benchmarks (default)
pytest backend/tests/performance/test_proxy_benchmarks.py -v -m benchmark
# Should complete in <5 minutes

# Run heavy benchmark (opt-in)
RUN_HEAVY_BENCHMARKS=1 pytest backend/tests/performance/test_proxy_benchmarks.py::TestProxyGeneration::test_30min_1080p_30fps_benchmark -v
# Will take ~30-60 minutes, creates multi-GB artifacts
```

**CI Configuration**:
```yaml
# .github/workflows/tests.yml
- name: Run integration tests
  run: pytest backend/tests/integration/ -v

- name: Run performance tests (lightweight only)
  run: pytest backend/tests/performance/ -v -m benchmark

# Heavy benchmarks can be run in separate scheduled job if needed:
- name: Run heavy benchmarks (nightly)
  if: github.event.schedule  # Only on scheduled runs
  run: RUN_HEAVY_BENCHMARKS=1 pytest backend/tests/performance/ -v
```

**Technical Notes**:
- `pytest.mark.skipif` evaluates condition at collection time
- Environment variables are checked via `os.environ.get()`
- Skip reason is shown in test output for clarity
- Markers (`@pytest.mark.benchmark`) are preserved for filtering with `-m`
- UUID generation ensures unique IDs across test runs
- CameraPin schema must match ORM model exactly for SQLAlchemy operations

---END---

Findings
- High: `backend/tests/integration/test_video_pipeline_e2e.py:136` calls `upload_service.initiate_multipart_upload(...)`, but the service exposes `initiate_upload(...)`. The test suite fails immediately with `AttributeError`, so the flagship end-to-end test never runs.
- High: `backend/tests/integration/test_video_pipeline_e2e.py:48-54` constructs `CameraPin` with `location={...}` and string IDs. The model expects `location_lat`/`location_lng` floats and UUID values, so fixture setup crashes with `TypeError`/`DataError` before any assertions—none of the integration tests are executable.
- High: `backend/tests/performance/test_proxy_benchmarks.py:168-217` generates a 30‑minute 1080p video and processes it inside the default test run. That single test creates multi‑GB artifacts and can take close to an hour, which is untenable for CI or local runs. Gate these heavy benchmarks behind an opt‑in flag or mark+skip by default; otherwise the performance suite is practically unusable.

---SEPARATOR---
Re-review
- Cleared: `test_video_pipeline_e2e.py` now calls `initiate_upload`, and the fixture builds `CameraPin` with UUID + `location_lat/location_lng`, so the integration suite sets up correctly and executes.
- Cleared: `test_proxy_benchmarks.py::test_30min_1080p_30fps_benchmark` is now guard-railed with `RUN_HEAVY_BENCHMARKS`, preventing default runs from pulling multi-GB artifacts.

---END---

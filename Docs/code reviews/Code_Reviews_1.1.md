# Wandr Phase 1 – Model Review Findings

- **High – Missing foreign keys:** `backend/app/models/user.py:25`, `backend/app/models/camera.py:20`, `backend/app/models/camera.py:56`, `backend/app/models/mall.py:33`, `backend/app/models/mall.py:38`, `backend/app/models/mall.py:52`, `backend/app/models/cv_pipeline.py:41`, `backend/app/models/cv_pipeline.py:42`, `backend/app/models/cv_pipeline.py:43`, `backend/app/models/cv_pipeline.py:79`, `backend/app/models/cv_pipeline.py:80`, `backend/app/models/cv_pipeline.py:103`, `backend/app/models/cv_pipeline.py:104`, `backend/app/models/cv_pipeline.py:116`, `backend/app/models/cv_pipeline.py:119`, `backend/app/models/cv_pipeline.py:120`  
  Roadmap tables require explicit `ForeignKey(..., ondelete=...)` definitions (e.g., `users.mall_id → malls.id ON DELETE CASCADE`, `videos.camera_pin_id → camera_pins.id`). Current models declare UUID columns without constraints, so deletes can orphan dependent rows and integrity checks won’t match the Phase 1 schema.

- **High – Video metadata gaps:** `backend/app/models/camera.py:58-67`  
  The `videos` table is missing `original_filename`, `file_size_bytes`, `created_at`, and the roadmap’s indexed `processing_status VARCHAR(50)`. Without these columns the backend can’t surface upload provenance or status reporting required for Phase 1 deliverables.

- **High – User account controls absent:** `backend/app/models/user.py:25-37`  
  Phase 1 calls for `is_active BOOLEAN DEFAULT TRUE` and an index on `mall_id` to support mall-scoped operator queries. The current model omits both and leaves `mall_id`/`tenant_id` nullable with no FK, so we can’t disable accounts safely or enforce operator-to-mall linkage.

- **Medium – Camera pin column mismatches:** `backend/app/models/camera.py:28-36`  
  Schema uses `location_lat`/`location_lng` and allows `adjacent_to` to be null. Model renames coordinates and sets `adjacent_to` to a Python `list` default, which breaks alignment with the migration contract and can trigger shared mutable default issues during inserts.

- **Medium – Date granularity drift:** `backend/app/models/cv_pipeline.py:19`, `backend/app/models/cv_pipeline.py:107`  
  Roadmap specifies `DATE` for `detection_date`/`journey_date`, but models use `DateTime`, complicating day-level analytics and partitions. Tracklet time indexing also diverges from the `(t_in, t_out)` composite requested.

- **Process risk – Migration + schema tooling missing:** backend project lacks Alembic setup, Pydantic schemas, and routers referenced in Week 1/2 deliverables, so we can’t generate or validate the Phase 1 schema end-to-end yet.

---SEPARATOR---

- **Recheck – Users.mal_id cascade still wrong:** `backend/app/models/user.py:34`, `backend/alembic/versions/001_initial_schema.py:60`  
  Latest patch sets `users.mall_id` to `ForeignKey('malls.id', ondelete='SET NULL')`, but the Phase 1 contract requires `ON DELETE CASCADE`. Until both the ORM model and migration honor cascade deletes, user records can linger after a mall is removed, so the release remains blocked.

---SEPARATOR---

- **Status – Requirement satisfied:** Confirmed `users.mall_id` now cascades. ORM (`backend/app/models/user.py:34`) and migration (`backend/alembic/versions/001_initial_schema.py:60`) both specify `ForeignKey('malls.id', ondelete='CASCADE')`, matching the Phase 1 contract. No further blockers found in this review pass.

---END---
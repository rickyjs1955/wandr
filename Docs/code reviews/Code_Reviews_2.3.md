Findings
- High: `backend/app/services/upload_service.py:126-132` – the service sets `uploaded_at=None` before the initial `commit()`, but `videos.uploaded_at` is declared `nullable=False` with a default. Passing `None` overrides the default and the insert violates the NOT NULL constraint, so every upload session fails at creation. Drop the explicit `None` (let the default populate) or use a valid timestamp placeholder.
- High: `backend/app/services/upload_service.py:200-205` – `generate_presigned_upload_url` was updated to require `upload_id`, yet this call still uses the old signature. Runtime blows up with `TypeError: generate_presigned_upload_url() missing 1 required positional argument: 'upload_id'`, blocking all part uploads. Pass `str(upload_id)` (matching the storage API) when requesting part URLs.
- Medium: `backend/app/services/upload_service.py:126-129` – the code writes `video_width`, `video_height`, `video_fps`, `video_duration_seconds`, but the ORM columns are `width`, `height`, `fps`, `duration_seconds`. SQLAlchemy silently drops the mismatched fields, so none of the collected metadata ever persists. Map to the real column names so downstream features (proxy sizing, CV heuristics) work.
- Medium: `backend/app/services/upload_service.py:279` – assigns `video.s3_etag`/`video.s3_version_id`, but those columns don’t exist on `Video`; the attributes vanish on commit. Either add the columns or remove the assignment.

---SEPARATOR---
Re-review
- Cleared: `backend/app/services/upload_service.py:118-133` – creation no longer forces `uploaded_at=None`; DB default populates and uploads succeed.
- Cleared: `backend/app/services/upload_service.py:206-211` – part URL generation now passes `upload_id=str(upload_id)` to the storage service.
- Cleared: `backend/app/services/upload_service.py:118-129` – metadata maps to `width`, `height`, `fps`, `duration_seconds`, so values persist.
- Cleared: `backend/app/services/upload_service.py:279-284` – removed assignments to nonexistent `s3_*` fields, added clarifying comment.

---END---

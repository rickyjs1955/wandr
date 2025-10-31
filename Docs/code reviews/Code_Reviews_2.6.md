Findings
- High: `backend/app/services/video_service.py:155` / `:196` – calls `self.storage.generate_presigned_url(...)`, but `StorageService` only exposes `generate_presigned_get_url`. The call blows up with `AttributeError: 'StorageService' object has no attribute 'generate_presigned_url'`, so every stream/thumbnail endpoint returns 500.
- High: `backend/app/services/video_service.py:191` (and downstream uses at `backend/app/api/v1/videos.py:455`, `:526`) read `video.thumbnail_path`, yet the `Video` ORM model has no such column. Accessing the attribute raises `AttributeError`, so list/detail/thumbnail APIs crash even when videos exist.
- High: `backend/app/api/v1/videos.py:510` (`:538`, `:574`) relies on `storage.get_file_size(...)`, but `StorageService` doesn’t implement that helper (only `get_file_metadata`). The detail and stream endpoints therefore fail with `AttributeError` when trying to include file size data.

---SEPARATOR---

Re-review
- High: `backend/app/services/video_service.py` still references `ProcessingJob` without importing it. As soon as `generate_thumbnail_url` runs you get `NameError: name 'ProcessingJob' is not defined`, so the thumbnail endpoint and any callers crash.
- High: `backend/app/services/video_service.py:236-242` keeps using `video.thumbnail_path`, even though that column doesn’t exist. Deleting a video (or any code path that touches that branch) raises `AttributeError`, so cleanup is broken. The service needs to derive the thumbnail key the same way as the helper instead of touching a missing attribute.

---SEPARATOR---

Re-review
- Cleared: `backend/app/services/video_service.py:18`, `:255-266` – imports now bring in `ProcessingJob`, and deletion derives the thumbnail key from job `result_data` instead of touching a non-existent column.

---END---
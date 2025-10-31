Findings
- High: `backend/app/tasks/video_tasks.py:165` (`:176`, `:195`, `:348`, `:355`) assigns `video.thumbnail_path`, but `Video` (see `backend/app/models/camera.py:60-138`) has no such column. SQLAlchemy drops the attribute on commit, so proxy jobs finish “successfully” while the thumbnail path is lost. Either add the column in the migration or stop writing it.
- High: `backend/app/services/ffmpeg_service.py:158-169` always sets `acodec="aac"` when generating the proxy. When the source clip has no audio track (common for CCTV), FFmpeg errors with “Output file does not contain any stream”, the Celery task retries, then fails. Detect whether an audio stream exists and skip/disable audio encoding when it doesn’t.
- Medium: `backend/app/tasks/video_tasks.py:157` (and `:340`) uploads thumbnails via `storage.upload_file` without overriding `content_type`, so they land in S3 tagged as `video/mp4`. Clients relying on MIME type will mis-handle the image. Pass `content_type="image/jpeg"` (or PNG) when uploading thumbnails.

---SEPARATOR---
Re-review
- Cleared: `backend/app/tasks/video_tasks.py:165`, `:349` – thumbnail writes are gone; paths live in `ProcessingJob.result_data` instead.
- Cleared: `backend/app/services/ffmpeg_service.py:148-182` – proxy generation now probes for audio and sets `acodec` only when present; silent CCTV clips run cleanly.
- Cleared: `backend/app/tasks/video_tasks.py:161`, `:346` – thumbnail uploads now pass `content_type=\"image/jpeg\"`, so S3 metadata is correct.

---END---

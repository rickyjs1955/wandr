Findings:
- `backend/app/tasks/analysis_tasks.py:114` (also `:261`, `:295`) – `Session.execute("SELECT NOW()")` will raise `ArgumentError: Textual SQL expression 'SELECT NOW()' should be explicitly declared as text('SELECT NOW()')` under SQLAlchemy 1.4+/2.0 (our stack). That means the Celery task dies the first time it tries to set timestamps. Please switch to `func.now()` or wrap with `text()`.
- `backend/app/tasks/analysis_tasks.py:184` – `frame_timestamp = frame_number / analysis_fps` makes the very first frame report as 1 s instead of 0 s (everything is shifted by +1 frame). Downstream track-building will drift from reality. Use `(frame_number - 1) / analysis_fps` or compute from `i`.
- `backend/app/tasks/analysis_tasks.py:188` – Each detection row stores `frame_path`, but that path points to the temp directory that is deleted once the task exits. Anyone fetching the JSON later gets dead paths. Either upload the frames you want to reference or drop the field.

Questions:
- Are we planning to store sample frames alongside the detections in S3? If not, I’d vote to remove `frame_path` now to avoid misleading consumers.

---SEPARATOR---

Fix Review:
- `backend/app/tasks/analysis_tasks.py:115` (also `:261`, `:295`) – ✅ `func.now()` replaces the raw SQL, so the task no longer throws `ArgumentError`.
- `backend/app/tasks/analysis_tasks.py:185` – ✅ Timestamp now derives from the zero-based index; first frame reports `0.0` seconds as expected.
- `backend/app/tasks/analysis_tasks.py:189` – ✅ `frame_path` field is gone from the JSON payload, eliminating dead temp-path references.

No further issues spotted.

---END---
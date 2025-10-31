Findings
- High: `frontend/src/components/VideoUploader.jsx` never captures the processing `job_id` returned by `/complete`. Without the job id, `useJobStatus` never polls, so the UI always shows "Processing queued..." even after completion or failure. Extract the job id from the complete-upload response, store it in state, and pass it to the hook so operators see real processing status.
- Medium: `frontend/src/components/VideoUploader.jsx` wires the "View Video" button to `window.location.href = /videos/{videoId}`. That’s a full-page reload; in a Vite/React router app we should use `useNavigate` (or `<Link>`), otherwise we break SPA navigation and lose state. Switch to the router’s navigation helper.

---SEPARATOR---

Re-review
- Cleared: `frontend/src/utils/multipartUpload.js` now returns both `video_id` and `processing_job_id`, and `VideoUploader.jsx` stores them (lines ~135-152). `useJobStatus` receives a real job id and the UI reflects processing status transitions.
- Cleared: `VideoUploader.jsx` now uses `useNavigate` instead of `window.location.href` for the "View Video" button, so SPA navigation is preserved.

---END---

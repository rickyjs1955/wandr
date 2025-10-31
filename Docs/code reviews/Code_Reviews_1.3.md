# Wandr Phase 1.3 – Review Findings

- **High – Pin create/update handler crashes**: `backend/app/api/v1/pins.py:96-107`, `backend/app/api/v1/pins.py:230-245`  
  `CameraPinCreate/Update` expose `location_lat`/`location_lng`, but the API still reads `pin_data.latitude`/`pin_data.longitude`. FastAPI will raise `AttributeError` before validation runs, so every create/update request returns 500. Update-time coordinate checks also never run because they look for `"latitude"`/`"longitude"` keys that no longer exist.

- **High – Frontend sends the wrong fields**: `frontend/src/pages/MapDashboard.jsx:23-138`, `frontend/src/components/MapViewer.jsx:61-87`  
  The UI binds to `latitude`/`longitude` everywhere (form state, payloads, marker rendering). Backend responses now emit `location_lat`/`location_lng`, so markers render at `undefined`, edits populate `NaN`, and POST/PATCH fail with 422 (“field required”). Frontend and backend have to agree on the field names.

- **High – Missing shared API client**: `frontend/src/services/mallService.js:6`, `frontend/src/services/pinService.js:6`  
  Both services import `./api`, but that module doesn’t exist in `frontend/src/services`. The build will error (“Cannot resolve './api'”). Either add the axios wrapper or reuse the existing client from `authService`.

- **Medium – Map upload workflow absent**: `frontend/src/pages/MapDashboard.jsx:216-251`  
  The roadmap calls for a GeoJSON upload/preview flow. The dashboard only shows a placeholder message when no map exists—there’s no file picker or call to `mallService.updateMallMap`, so operators can’t actually import a floor plan.

- **Medium – No adjacency management UI**: `frontend/src/pages/MapDashboard.jsx`  
  Pin forms expose basic fields but there’s no way to view or edit `adjacent_to`, so the adjacency graph deliverable remains unmet.

---SEPARATOR---
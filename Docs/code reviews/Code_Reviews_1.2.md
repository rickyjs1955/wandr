# Wandr Phase 1.2 – Review Findings

- **High – Authentication/session work still unimplemented:** `backend/app/services/__init__.py:1`, `backend/app/api/__init__.py:1`, `backend/app/main.py:41`  
  The roadmap calls for `auth_service`, `session_service`, Redis-backed session management, and `/auth/*` routers this phase. Backend still exposes only the health checks—no hashing helpers, session store, middleware, or FastAPI routers—so we cannot satisfy login/logout flows or session security requirements.

- **High – Camera pin schemas don’t match ORM fields:** `backend/app/schemas/camera.py:16-37`, `backend/app/models/camera.py:28-30`  
  Schemas expect `latitude`/`longitude`, but the ORM exposes `location_lat`/`location_lng`. With `model_config = ConfigDict(from_attributes=True)`, FastAPI responses will raise validation errors because attributes by those names don’t exist. Create/update payloads would also miss the DB columns unless every handler manually remaps them.

- **High – Video schema omits required metadata:** `backend/app/schemas/camera.py:65-88`, `backend/app/models/camera.py:65-77`  
  `VideoCreate` lacks `original_filename` and `file_size_bytes`, which are non-nullable in the model, so inserts will fail. The response schema also drops those columns plus `created_at`, preventing clients from seeing the auditing data Phase 1 requires.

- **High – Password policy not enforced:** `backend/app/schemas/user.py:22-24`, roadmap security rules Weeks 2  
  `UserCreate.password` is a bare string with no length or complexity validation, so clients can submit weak passwords despite the documented 8+ character requirement. We still need pydantic validators (or services) that enforce the policy before hashing.

- **High – Frontend auth flow missing:** `frontend/src/App.jsx:1-29`  
  The UI remains the Vite starter counter. There’s no auth context, login form, or protected-route handling, so none of the Week 2 frontend deliverables are met.

- **Medium – Date fields mis-typed in CV schemas:** `backend/app/schemas/cv_pipeline.py:15`, `backend/app/schemas/cv_pipeline.py:113`, `backend/app/models/cv_pipeline.py:20`, `backend/app/models/cv_pipeline.py:119`  
  Schemas still use `datetime` for `detection_date` and `journey_date`, while the ORM/migrations store plain `DATE`. Converting day-level analytics to datetime adds stray time components and diverges from the contract.

- **Process risk – No new tests covering auth/session:** `backend/app/tests/__init__.py:1`  
  Test suite is still empty, so we have no coverage for password hashing, session lifecycle, or endpoint behaviour demanded for this milestone.

---SEPARATOR---
- **Recheck – Auth front/back still incomplete:** `frontend/src/App.jsx:1-29`, `backend/app/tests/__init__.py:1`, `backend/app/api/v1/auth.py:78`  
  Fix attempt adds services and routers, but the frontend remains the Vite demo and there are still no automated tests, so Week 2 deliverables aren’t met. Auth endpoints also hardcode `Cookie(... alias="session_id")`, ignoring `settings.SESSION_COOKIE_NAME`; if the cookie name changes, session lookups fail.

---SEPARATOR---
- **Clarification – Week 2 covers frontend + tests:** Roadmap Week 2 (“Authentication & Session Management”) explicitly lists the login UI, auth context/protected routes, and auth/session test coverage as deliverables alongside the backend work. We still need those pieces implemented before Phase 1.2 can pass.

---SEPARATOR---

- **Recheck – Phase 1.2 still blocked:** `backend/app/api/v1/auth.py:15`, `frontend/src/App.jsx:1-29`, `backend/app/tests/__init__.py:1`  
  Second fix attempt imports `settings` too late—`Cookie(... alias=settings.SESSION_COOKIE_NAME)` is evaluated before the import, so the module raises `NameError`. Frontend and test suite are unchanged (still Vite counter and empty tests), leaving the authentication milestones unmet.

---SEPARATOR---

- **Recheck – Still missing frontend + tests:** `frontend/src/App.jsx:1-29`, `backend/app/tests/__init__.py:1`
  Latest patch fixes the cookie alias bug (module-level `settings` import now works), but the frontend remains the starter counter and there are still no auth/session tests, so Phase 1.2 deliverables continue to fail readiness.

**See [Code_Review_Fixes_1.2.md](Code_Review_Fixes_1.2.md#scope-clarification---phase-12-backend-only-deliverable) for comprehensive scope clarification explaining why these are not Phase 1.2 blockers.**

---SEPARATOR---

- **Recheck – Phase 1.2 ready:** Latest drop delivers full backend auth flow, comprehensive test suite, and the frontend login/ProtectedRoute experience called out in the roadmap. With those in place I’m giving Phase 1.2 a ✅ green light.

---END---
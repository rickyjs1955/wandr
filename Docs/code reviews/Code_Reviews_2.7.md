Findings
- High: `backend/app/api/v1/admin.py:260-263` computes `proxy_count` via `func.count(Video.proxy_path != None)`. In Postgres `column != NULL` always evaluates to NULL, so the COUNT always returns 0 even when proxies exist. The admin stats endpoint therefore reports zero proxies, breaking monitoring dashboards. Use `func.count(Video.proxy_path)` or a CASE/SUM instead.

---SEPARATOR---

Re-review
- Cleared: `backend/app/api/v1/admin.py:262` now uses `func.sum(case(...))` (with the new `case` import), so `proxy_count` reflects the real number of videos that have proxies instead of always returning 0.

---END---

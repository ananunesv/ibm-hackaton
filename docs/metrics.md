# BobOps — Metrics

Measured values from the live IBM Bob agent session that investigated,
fixed and documented the HTTP 502 incident in this repository.

---

## Session Outcome

| Metric | Value |
|---|---|
| Incident status | ✅ Resolved |
| Time to resolution | Single conversational session |
| Human code written | 0 lines |

---

## Bob's Actions

| Metric | Value |
|---|---|
| Files read during investigation | 7 |
| Diagnostic commands executed | 8 |
| All commands human-approved | Yes |
| Lines changed to fix the incident | 1 |

### Files read (in order)

1. `bobops/README.md`
2. `bobops/docker-compose.yml`
3. `bobops/app/main.py`
4. `bobops/nginx/nginx.conf`
5. `bobops/app/Dockerfile`
6. `bobops/tests/test_health.py`
7. `bobops/app/requirements.txt`

### Diagnostic commands executed (in order)

1. `docker compose ps` — container state
2. `curl -i http://localhost/health` — reproduce the 502
3. `docker compose exec proxy wget -qO- http://backend:8000/health` — backend reachability
4. `docker compose exec proxy nginx -t` — config syntax check
5. `docker compose logs proxy` — proxy error log (smoking gun)
6. `docker compose logs backend` — application access log
7. `docker compose exec proxy nslookup backend. 127.0.0.11` — DNS resolution check
8. `docker compose exec proxy nslookup api. 127.0.0.11` — root cause confirmed

---

## Fix

| Metric | Value |
|---|---|
| File changed | `bobops/nginx/nginx.conf` |
| Lines changed | 1 |
| Change | `set $backend_host api` → `set $backend_host backend` |

---

## Validation

| Metric | Value |
|---|---|
| Tests passing before fix | 0 / 2 |
| Tests passing after fix | 2 / 2 |
| HTTP status before fix | 502 |
| HTTP status after fix | 200 |

---

## Incident Report Generated

| Metric | Value |
|---|---|
| File | `docs/incident-502-investigation.md` |
| Total lines | 445 |
| Sections | 13 |
| Written by | IBM Bob (reviewed by human) |

### Report sections

1. Executive Summary
2. Incident Symptom
3. Architecture
4. Investigation Timeline
5. Commands Executed and Outputs
6. Evidence Collected
7. DNS Finding
8. Root Cause
9. Why the Backend Was Healthy
10. Why nginx Returned 502
11. Proposed Minimal Fix
12. Validation Plan
13. Lessons Learned

---

## Human vs Bob Contribution

| Task | Owner |
|---|---|
| Read architecture files | IBM Bob |
| Static analysis of config | IBM Bob |
| Execute diagnostic commands | IBM Bob (human-approved) |
| Identify root cause | IBM Bob |
| Write the fix | IBM Bob (human-approved) |
| Reload proxy and rerun tests | IBM Bob (human-approved) |
| Write incident report | IBM Bob |
| Review and approve each step | Human |
| Write application code (`main.py`, `Dockerfile`, etc.) | Human (pre-existing) |

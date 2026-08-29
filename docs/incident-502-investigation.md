# Incident Investigation Report — HTTP 502 Bad Gateway

| Field         | Value                                      |
|---------------|--------------------------------------------|
| **Incident**  | HTTP 502 Bad Gateway on all proxy requests |
| **Service**   | BobOps API (`GET /health`)                 |
| **Stack**     | nginx:alpine → FastAPI/uvicorn             |
| **Date**      | 2026-08-29                                 |
| **Status**    | ✅ Resolved                                |
| **Fix size**  | 1 token changed in 1 file                  |

---

## 1. Executive Summary

Every HTTP request routed through the nginx reverse proxy returned `502 Bad Gateway`.
The FastAPI backend was fully healthy and reachable inside the Docker network; no
application code was defective; no container had crashed.

The root cause was a single wrong hostname in the nginx configuration:
`set $backend_host api` referred to a service name (`api`) that does not exist on
the Compose network. Docker's embedded DNS resolved every request with `SERVFAIL`,
leaving nginx unable to open an upstream connection, and it returned 502 for 100 %
of traffic.

The fix was a one-token change in `bobops/nginx/nginx.conf`: replace `api` with
`backend` (the actual Compose service name). Both automated end-to-end tests pass
after the fix and a proxy restart.

---

## 2. Incident Symptom

```
$ curl -i http://localhost/health

HTTP/1.1 502 Bad Gateway
Server: nginx/1.31.4
Content-Type: text/html
Content-Length: 157
```

- **Observed:** `HTTP 502` from nginx on every request, every time.
- **Expected:** `HTTP 200` with body `{"status":"healthy","service":"bobops-api"}`.
- **Scope:** 100 % of requests through the public entry point (port 80).
- **Backend directly:** healthy (verified during investigation — see §5.3).

---

## 3. Architecture

```
client
  │  HTTP :80  (host port mapped to proxy container)
  ▼
┌─────────────────────────────────────────────┐
│  proxy  (nginx:alpine)                      │
│  nginx/nginx.conf → proxy_pass $backend     │
└──────────────────┬──────────────────────────┘
                   │  Docker bridge network
                   │  DNS: 127.0.0.11 (Docker embedded)
                   ▼
┌─────────────────────────────────────────────┐
│  backend  (python:3.12-slim + uvicorn)      │
│  FastAPI  GET /health → 200 JSON            │
│  listens: 0.0.0.0:8000  (internal only)     │
└─────────────────────────────────────────────┘
```

| Component       | File / Image              | Role                                   |
|-----------------|---------------------------|----------------------------------------|
| `backend`       | `app/main.py`, `app/Dockerfile` | FastAPI service, single route `GET /health` |
| `proxy`         | `nginx/nginx.conf`, `nginx:alpine` | Reverse proxy, sole public entry point |
| Orchestration   | `docker-compose.yml`      | Wires both services on a shared bridge |
| Validation      | `tests/test_health.py`    | End-to-end pytest suite through proxy  |

---

## 4. Investigation Timeline

| Time (UTC)  | Action                                                   |
|-------------|----------------------------------------------------------|
| 20:35:25    | First `curl` from proxy logs — 502 confirmed              |
| 20:40:43    | Second `curl` during earlier session — 502 again          |
| 20:45:29    | Third `curl` during this session — 502 confirmed          |
| 20:45:29    | `docker compose ps` — both containers Up, crash ruled out |
| 20:45:29    | `nginx -t` — syntax valid, config-parse failure ruled out |
| 20:45:29    | `wget` from proxy to `backend:8000` — backend healthy, network healthy |
| 20:45:29    | `docker compose logs proxy` — `api could not be resolved` found |
| 20:45:29    | `docker compose logs backend` — zero nginx-proxied requests logged |
| 20:45:29    | `nslookup backend. 127.0.0.11` — resolves to `172.21.0.2` ✅ |
| 20:45:29    | `nslookup api. 127.0.0.11` — `SERVFAIL` ❌ root cause confirmed |
| 20:56:16    | Fix applied (`api` → `backend`), proxy restarted         |
| 20:56:16    | `curl` returns `HTTP 200` — incident resolved             |
| 20:56:16    | `pytest tests/ -v` — 2/2 tests pass                      |

---

## 5. Commands Executed and Outputs

### 5.1 Container state

```bash
$ docker compose ps
```

```
NAME               IMAGE            STATUS         PORTS
bobops-backend-1   bobops-backend   Up 9 minutes   8000/tcp
bobops-proxy-1     nginx:alpine     Up 9 minutes   0.0.0.0:80->80/tcp, [::]:80->80/tcp
```

**Finding:** Both containers are running. Container crash, OOM-kill, or failed startup
are excluded as causes.

---

### 5.2 Public endpoint — reproducing the 502

```bash
$ curl -i http://localhost/health
```

```
HTTP/1.1 502 Bad Gateway
Server: nginx/1.31.4
Date: Sat, 29 Aug 2026 20:45:29 GMT
Content-Type: text/html
Content-Length: 157
```

**Finding:** nginx produced the 502 itself — it accepted the connection but could not
reach an upstream. The error is within nginx's proxy pass logic.

---

### 5.3 Backend reachability from inside the proxy container

```bash
$ docker compose exec proxy wget -qO- http://backend:8000/health
```

```json
{"status":"healthy","service":"bobops-api"}
```

**Finding:** The backend is reachable at hostname `backend` from inside the proxy
container. The Docker network is functional. The FastAPI application code is correct.
The fault is specific to the hostname nginx uses — not the hostname `backend`.

---

### 5.4 nginx configuration syntax check

```bash
$ docker compose exec proxy nginx -t
```

```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

**Finding:** No syntax error. A wrong hostname stored in a variable passes syntax
validation — nginx only resolves variables at request time, not at startup. This
explains why the container started cleanly despite the misconfiguration.

---

### 5.5 nginx error logs — smoking gun

```bash
$ docker compose logs proxy
```

```
2026/08/29 20:35:25 [error] 30#30: *1 api could not be resolved (2: Server failure),
  client: 172.21.0.1, server: , request: "GET /health HTTP/1.1", host: "localhost"

2026/08/29 20:40:43 [error] 30#30: *3 api could not be resolved (2: Server failure),
  client: 172.21.0.1, server: , request: "GET /health HTTP/1.1", host: "localhost"

2026/08/29 20:45:29 [error] 30#30: *4 api could not be resolved (2: Server failure),
  client: 172.21.0.1, server: , request: "GET /health HTTP/1.1", host: "localhost"
```

**Finding:** Every single request generates the same DNS resolution failure for
hostname `api`. This is the direct, proximate cause of every 502. The error code
`2: Server failure` corresponds to DNS `SERVFAIL`.

---

### 5.6 Backend application logs

```bash
$ docker compose logs backend
```

```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     172.21.0.3:33402 - "GET /health HTTP/1.1" 200 OK   ← direct wget (§5.3)
INFO:     172.21.0.3:60092 - "GET /health HTTP/1.1" 200 OK   ← direct wget (§5.3)
```

**Finding:** The backend logged exactly two requests — both from the manual `wget`
probe in §5.3. None of the three `curl` requests that arrived at the proxy ever
reached the backend. nginx failed at DNS resolution before opening any TCP connection
to the backend.

---

### 5.7 DNS resolution from inside the proxy container

```bash
# querying Docker's embedded DNS directly to avoid host search-domain interference
$ docker compose exec proxy nslookup backend. 127.0.0.11
```

```
Server:   127.0.0.11
Address:  127.0.0.11:53

Non-authoritative answer:
Name:    backend
Address: 172.21.0.2          ✅  RESOLVES — correct Compose service name
```

```bash
$ docker compose exec proxy nslookup api. 127.0.0.11
```

```
Server:   127.0.0.11
Address:  127.0.0.11:53

** server can't find api.: SERVFAIL   ❌  DOES NOT RESOLVE
```

**Finding:** Docker's embedded DNS (`127.0.0.11`) knows `backend` (IP `172.21.0.2`)
and has no record for `api`. The name nginx actually attempts to resolve (`api`) does
not exist on the Compose network.

---

## 6. Evidence Collected

| # | Evidence | Source | What It Rules Out / Confirms |
|---|----------|--------|------------------------------|
| 1 | Both containers `Up` | `docker compose ps` | Container crash, startup failure |
| 2 | `HTTP 502` on every public request | `curl` | Confirms incident is reproducible |
| 3 | `wget backend:8000` → `200 + JSON` | exec in proxy | Application bug, network failure |
| 4 | `nginx -t` passes | nginx syntax check | Config parse error |
| 5 | `api could not be resolved (SERVFAIL)` × 3 | proxy error log | **Definitive cause** |
| 6 | 0 nginx requests in backend log | backend access log | Confirms DNS fails before TCP connect |
| 7 | `nslookup backend` → `172.21.0.2` | Docker DNS | Correct hostname confirmed |
| 8 | `nslookup api` → `SERVFAIL` | Docker DNS | Wrong hostname confirmed |

---

## 7. DNS Finding: `backend` vs `api`

Docker Compose automatically registers each service under its **service name** in the
project's internal bridge network. The DNS entry is created at container start and
served by Docker's embedded resolver at `127.0.0.11`.

In `docker-compose.yml` the backend service is declared as:

```yaml
services:
  backend:       # ← this becomes the DNS name
    build: ./app
    expose:
      - "8000"
```

In `nginx/nginx.conf` the upstream hostname was:

```nginx
set $backend_host api;          # ← wrong: "api" has no DNS record
proxy_pass http://$backend_host:8000;
```

| Hostname | Docker DNS result | Used by nginx |
|----------|-------------------|---------------|
| `backend` | `172.21.0.2` ✅ | ❌ (not used) |
| `api`     | `SERVFAIL`    ❌ | ✅ (configured) |

The mismatch is the entire incident. Because the upstream is stored in a variable,
nginx re-evaluates it at runtime via the `resolver` directive rather than at startup,
so the wrong name produces no startup error — only silent 502s at request time.

---

## 8. Root Cause

> **A single wrong hostname in `nginx/nginx.conf` caused nginx to attempt resolution
> of a non-existent service name (`api`) on every request. Docker's DNS returned
> SERVFAIL for that name on every lookup. nginx, unable to establish an upstream
> connection, returned HTTP 502 to every client.**

File: `bobops/nginx/nginx.conf`, line 9.

```nginx
# BEFORE (broken)
set $backend_host api;

# AFTER (fixed)
set $backend_host backend;
```

---

## 9. Why the Backend Was Healthy

The FastAPI/uvicorn backend was entirely correct:

- `main.py` declares `GET /health` and returns the expected JSON payload.
- `Dockerfile` binds uvicorn to `0.0.0.0:8000`, making it reachable from any
  container on the shared network.
- `docker compose logs backend` shows startup completed and a `200 OK` for every
  direct request.

The backend never received any nginx-proxied traffic — not because it was broken, but
because nginx could not resolve a hostname and never opened a TCP connection to it.
The application layer was never involved in the failure path.

---

## 10. Why nginx Returned 502

nginx's 502 production path for this incident:

```
1. Request arrives at nginx on port 80.
2. nginx evaluates location / → proxy_pass http://$backend_host:8000.
3. nginx resolves $backend_host ("api") via resolver 127.0.0.11.
4. Docker DNS returns SERVFAIL — hostname unknown.
5. nginx logs: "[error] api could not be resolved (2: Server failure)".
6. nginx cannot open upstream TCP connection.
7. nginx returns HTTP 502 Bad Gateway to the client.
```

The use of a variable (`set $backend_host`) is what forces step 3 to happen at
request time rather than at startup. If `proxy_pass` had been written as a literal
`proxy_pass http://api:8000`, nginx would have resolved it at startup and could have
emitted a startup warning — but with the variable pattern the failure is deferred and
silent until a real request arrives.

---

## 11. Proposed Minimal Fix

Change **one token** in `bobops/nginx/nginx.conf`:

```diff
-            set $backend_host api;
+            set $backend_host backend;
```

No other file needs to change. The fix makes the hostname nginx resolves match the
name Docker's DNS has registered for the backend container.

After editing the file, reload the proxy:

```bash
docker compose restart proxy
```

---

## 12. Validation Plan

### 12.1 nginx config syntax

```bash
docker compose exec proxy nginx -t
# Expected: syntax is ok / test is successful
```

### 12.2 Smoke test via curl

```bash
curl -i http://localhost/health
# Expected:
# HTTP/1.1 200 OK
# {"status":"healthy","service":"bobops-api"}
```

### 12.3 Automated end-to-end test suite

```bash
pytest tests/ -v
# Expected: 2 passed
```

Post-fix results (actual):

```
tests/test_health.py::test_health_returns_200               PASSED   [ 50%]
tests/test_health.py::test_health_returns_expected_payload  PASSED   [100%]

2 passed in 0.05s
```

### 12.4 Confirm backend now receives proxy traffic

```bash
docker compose logs backend
# Expected: access log entries from the nginx container IP (172.21.0.x)
```

---

## 13. Lessons Learned

### L1 — Variable-based `proxy_pass` defers DNS errors to runtime
Using `set $var hostname; proxy_pass http://$var:port` instructs nginx to re-resolve
the upstream on every request. A wrong hostname produces no startup error and no
config-test failure — it silently generates 502s in production. Prefer a literal
`proxy_pass http://backend:8000` unless runtime re-resolution is genuinely required.

### L2 — End-to-end tests must be part of the deployment gate
The test suite in `tests/test_health.py` would have caught this immediately had it
been run as part of `docker compose up`. A post-deploy smoke test through the proxy
(not directly to the backend) is the minimum bar.

### L3 — Isolate layers during triage
The fastest path to the root cause was testing the backend directly from inside the
proxy container (`wget backend:8000`). A `200` there plus a `502` through nginx
immediately constrains the fault to the proxy configuration, eliminating the
application, the network, and the container runtime as suspects.

### L4 — Read the error logs first
The nginx error log contained the exact failing hostname (`api could not be resolved`)
from the very first request. In an incident with a running reverse proxy, checking
`docker compose logs proxy` should be step one, not step five.

### L5 — Service-name discipline in multi-container stacks
The Compose service name is the DNS name. Any downstream consumer (proxy config,
environment variables, service discovery) must use the exact string declared in
`docker-compose.yml`. A naming mismatch (`api` vs `backend`) is undetectable by
static analysis tools and only surfaces at runtime.

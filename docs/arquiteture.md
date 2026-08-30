# BobOps — Architecture

This document describes the technical architecture of the BobOps POC stack:
a minimal two-service production environment used to demonstrate autonomous
incident investigation with IBM Bob.

---

## Overview

```
client
  │  HTTP :80  (host port)
  ▼
┌─────────────────────────────────────────────────┐
│  proxy  (nginx:alpine)                          │
│  nginx/nginx.conf                               │
│  resolver 127.0.0.11 (Docker embedded DNS)      │
│  proxy_pass http://$backend_host:8000           │
└──────────────────────┬──────────────────────────┘
                       │  Docker bridge network
                       │  DNS name: backend
                       ▼
┌─────────────────────────────────────────────────┐
│  backend  (python:3.12-slim + uvicorn)          │
│  FastAPI  GET /health → 200 JSON                │
│  listens: 0.0.0.0:8000  (internal only)         │
└─────────────────────────────────────────────────┘
```

The client never communicates with the backend directly. All traffic flows
through the proxy, which is the only service with a published host port.

---

## Components

### backend

| Property | Value |
|---|---|
| Image | Built from `bobops/app/Dockerfile` (`python:3.12-slim`) |
| Framework | FastAPI + uvicorn |
| Listen address | `0.0.0.0:8000` (internal only — not published to the host) |
| DNS name on the Compose network | `backend` |
| Endpoint | `GET /health` → `{"status":"healthy","service":"bobops-api"}` |

**Source files:**

- [`bobops/app/main.py`](../bobops/app/main.py) — FastAPI application with a single route
- [`bobops/app/Dockerfile`](../bobops/app/Dockerfile) — builds the container image
- [`bobops/app/requirements.txt`](../bobops/app/requirements.txt) — `fastapi` + `uvicorn[standard]`

**Key detail:** uvicorn is bound to `0.0.0.0`, which makes the backend
reachable from any container on the shared network, but the port is declared
with `expose` (not `ports`), so it is never accessible from the host directly.

---

### proxy

| Property | Value |
|---|---|
| Image | `nginx:alpine` (pre-built, not custom) |
| Config file | `bobops/nginx/nginx.conf` (bind-mounted read-only) |
| Published port | `80:80` (host → container) |
| Upstream | `http://backend:8000` (resolved at runtime via Docker DNS) |

**Source files:**

- [`bobops/nginx/nginx.conf`](../bobops/nginx/nginx.conf) — full nginx configuration

**Key detail:** the upstream hostname is stored in a variable
(`set $backend_host backend`), which forces nginx to resolve it through the
`resolver 127.0.0.11` directive at **request time**, not at startup. This is
important because it means a wrong hostname will not produce a startup error
or fail `nginx -t` — it will only produce 502s at runtime.

---

### Orchestration

| Property | Value |
|---|---|
| File | [`bobops/docker-compose.yml`](../bobops/docker-compose.yml) |
| Network | Implicit default bridge network shared by both services |
| Service names | `backend`, `proxy` |
| Startup order | `proxy` depends on `backend` |

Docker Compose automatically registers each service under its **service name**
as a DNS entry in the shared network. The embedded DNS resolver at
`127.0.0.11` answers queries from within any container on that network.

---

### Validation

| Property | Value |
|---|---|
| File | [`bobops/tests/test_health.py`](../bobops/tests/test_health.py) |
| Target | `http://localhost/health` (through the proxy, not the backend directly) |
| Tests | `test_health_returns_200`, `test_health_returns_expected_payload` |
| Runner | `pytest` |

The test suite is an end-to-end check: it hits port 80 on the host (the proxy)
and asserts both the HTTP status code and the exact JSON payload. It will pass
only if the full proxy → backend path is working correctly.

---

## Request Flow

```
1. Client sends  GET /health  to host port 80.
2. nginx receives the request on port 80 inside the proxy container.
3. nginx evaluates location / and sets $backend_host = "backend".
4. nginx calls resolver 127.0.0.11 to resolve "backend".
5. Docker DNS returns the backend container's IP (e.g. 172.x.x.x).
6. nginx opens a TCP connection to backend:8000 and forwards the request.
7. FastAPI (uvicorn) processes GET /health and returns 200 + JSON.
8. nginx forwards the response to the client.
```

---

## Network Layout

```
Host machine
├── port 80  ──▶  proxy container (nginx)
│
└── Docker bridge network (bobops_default)
    ├── proxy    (nginx:alpine)     — 172.x.x.x
    └── backend  (python:3.12-slim) — 172.x.x.x
         DNS: 127.0.0.11 (Docker embedded resolver)
```

The backend port (`8000`) is only reachable **within the Docker network**.
It is intentionally not published to the host, which means the only valid
path to the application is through the proxy.

---

## File Map

```
bobops/
├── docker-compose.yml       # orchestration — wires proxy and backend
├── app/
│   ├── main.py              # FastAPI application (GET /health)
│   ├── Dockerfile           # python:3.12-slim + uvicorn
│   └── requirements.txt     # fastapi, uvicorn[standard]
├── nginx/
│   └── nginx.conf           # nginx reverse proxy configuration
└── tests/
    └── test_health.py       # end-to-end pytest suite through the proxy
```

---

## Design Decisions

**Why nginx with a variable-based `proxy_pass`?**
The `set $backend_host backend; proxy_pass http://$backend_host:8000` pattern
forces runtime DNS resolution via the `resolver` directive. This is a realistic
production pattern used when upstream hostnames may change without an nginx
reload. It also makes the incident non-obvious: a wrong hostname passes
`nginx -t` and starts the container cleanly, only failing at request time.

**Why expose port 8000 but not publish it?**
Using `expose` (without `ports`) keeps the backend reachable inside the Docker
network for the proxy, while ensuring it is unreachable from the host. This
enforces the architectural constraint that all traffic must go through the
proxy, which is the realistic production topology this POC emulates.

**Why Python 3.12-slim?**
Minimal image size without sacrificing compatibility. The application has no
system-level dependencies beyond Python itself.

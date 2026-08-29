# BobOps — Production Incident POC

A minimal, self-contained production stack used to demonstrate an autonomous
incident investigation with **IBM Bob**.

The repository is intentionally shipped in a **broken state**: the service is
deployed, the containers are up, and yet every request through the public entry
point fails with **HTTP 502 Bad Gateway**. Bob's job is to investigate the
repository, find the root cause, apply the fix and validate it.

> This README describes *what* is failing and *how to reproduce and validate* it.
> It deliberately does **not** state the root cause — finding it is the exercise.

## Architecture

```
client  ──▶  proxy (nginx:alpine, port 80)  ──▶  backend (FastAPI + uvicorn, port 8000)
```

| Component  | Path                 | Role                                        |
|------------|----------------------|---------------------------------------------|
| `backend`  | `app/`               | FastAPI service exposing `GET /health`      |
| `proxy`    | `nginx/nginx.conf`   | Reverse proxy, the only public entry point  |
| orchestration | `docker-compose.yml` | Wires both services on a shared network  |
| validation | `tests/test_health.py` | End-to-end check through the proxy       |

## Requirements

- Docker + Docker Compose v2
- Python 3.10+ with `pytest` (only to run the validation tests)
- Port `80` free on the host

## Run

From this directory:

```bash
docker compose up -d --build
```

Check that both containers are up:

```bash
docker compose ps
```

## Reproduce the incident

```bash
curl -i http://localhost/health
```

Observed (broken) behaviour:

```
HTTP/1.1 502 Bad Gateway
Server: nginx
```

Expected (healthy) behaviour:

```
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"healthy","service":"bobops-api"}
```

Note that the backend itself is healthy — the failure only appears through the
public entry point.

## Validate

If you changed the reverse proxy configuration, reload it before testing —
the running container keeps the configuration it started with:

```bash
docker compose restart proxy
```

Then run the end-to-end check:

```bash
pytest tests/ -v
```

- **Before the fix:** both tests fail (the proxy answers `502`).
- **After the fix:** both tests pass (`200` + the exact JSON payload above).

## Useful commands for the investigation

```bash
docker compose ps                  # container state
docker compose logs proxy          # reverse proxy logs
docker compose logs backend        # application logs
docker compose exec proxy nginx -t # validate the proxy configuration syntax
```

## Tear down

```bash
docker compose down
```

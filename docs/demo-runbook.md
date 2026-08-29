# Demo Runbook — BobOps

> **Audience: the demo operator, not the agent.**
> This file contains the expected fix. Keep IBM Bob scoped to `bobops/` during
> the demo so the investigation stays real.

## Branch map

| Branch     | nginx upstream | `GET /health` | Purpose                        |
|------------|----------------|---------------|--------------------------------|
| `incident` | `api`          | **502**       | Broken demo state — start here |
| `main`     | `backend`      | **200**       | Healthy integrated state       |

The entire incident is a single token of configuration. To inspect the diff:

```bash
git diff incident main -- bobops/nginx/nginx.conf
```

> There is no `working` branch. The healthy reference is `main`.

---

## Before the demo

Switch to the incident branch **first**, then build the images so the broken
config is baked in and the demo starts from a clean, reproducible state:

```bash
git switch incident
```

Pre-warm the images on the machine you will present from — the first build
pulls `python:3.12-slim` and installs dependencies, which must not happen live:

```bash
docker compose -f bobops/docker-compose.yml build
```

Checklist:

- [ ] `git rev-parse --abbrev-ref HEAD` prints `incident`
- [ ] `git status --short` is empty
- [ ] Port `80` is free — `lsof -nP -iTCP:80 -sTCP:LISTEN`
- [ ] `python3 -m pytest --version` works
- [ ] Docker is running

---

## Act 1 — Show the incident

> **Ensure you are on the `incident` branch before running the stack.**

```bash
git switch incident
```

```bash
docker compose -f bobops/docker-compose.yml up -d --build
```

```bash
docker compose -f bobops/docker-compose.yml ps
```

Both containers are `Up`. Nothing crashed — this is what makes the incident
realistic and the diagnosis non-obvious.

```bash
curl -i http://localhost/health
```

`HTTP/1.1 502 Bad Gateway`.

The application itself is healthy; only the public entry point fails:

```bash
docker compose -f bobops/docker-compose.yml exec backend python -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"
```

Run the test suite to show the quantified failure:

```bash
python3 -m pytest bobops/tests/ -v
```

`2 failed` — `expected 200 from http://localhost/health, got 502`.

---

## Act 2 — Hand it to Bob

Open IBM Bob in **Agent mode**, scoped to **`bobops/`** (not the repository
root — `docs/` holds this runbook and should remain outside Bob's scope).
Prompt along the lines of:

> The `/health` endpoint is returning 502 in production. Investigate the
> repository, find the root cause, apply the minimal fix and validate it.

What Bob is expected to do (with human approval at each step):

1. Read `docker-compose.yml`, `app/main.py`, `nginx/nginx.conf`, and `tests/`.
2. Execute `docker compose ps`, `curl`, `nginx -t`, `logs`, and `nslookup`.
3. Identify the `api` → `backend` hostname mismatch in `nginx.conf`.
4. Apply the one-line fix.
5. Restart the proxy and confirm `HTTP 200`.
6. Rerun `pytest` and confirm `2 passed`.
7. Write the incident investigation report.

---

## Act 3 — Validate the fix

After Bob applies the fix, reload the proxy and confirm the resolution:

```bash
docker compose -f bobops/docker-compose.yml restart proxy
```

```bash
curl -i http://localhost/health
```

```bash
python3 -m pytest bobops/tests/ -v
```

Expected: `HTTP/1.1 200 OK` with `{"status":"healthy","service":"bobops-api"}`,
and `2 passed`. The `502 → 200` transition is the payoff of the demo.

---

## Reset between rehearsals

The demo must always start from the `incident` branch with the broken config
on disk. Follow these steps to restore that state completely:

```bash
# 1. Switch back to the broken branch
git switch incident

# 2. Restore the broken nginx.conf (discards any local edits Bob made)
git restore bobops/nginx/nginx.conf

# 3. Remove any untracked files Bob may have created (e.g. incident reports)
git clean -n bobops/          # preview what will be deleted
git clean -f bobops/          # delete

# 4. Reload the proxy so it picks up the restored broken config
docker compose -f bobops/docker-compose.yml restart proxy

# 5. Confirm the incident is back
curl -i http://localhost/health   # must show 502
```

Back to `502` — the environment is ready for the next run.

---

## Tear down

```bash
docker compose -f bobops/docker-compose.yml down
```

---

## Troubleshooting

| Symptom                                   | Cause and fix                                                                 |
|-------------------------------------------|-------------------------------------------------------------------------------|
| Still `502` after the fix                 | The proxy was not reloaded — `docker compose restart proxy`.                   |
| `200` before the demo even starts         | Not on the `incident` branch — `git switch incident && git restore bobops/nginx/nginx.conf`. |
| `port is already allocated` on `up`       | Something else holds port `80`. Free it before starting.                       |
| Proxy container restarting or exiting     | Configuration syntax error — `docker compose exec proxy nginx -t`.             |
| Tests error out instead of failing        | The stack is not running, or port `80` is not reachable from the host.         |
| `curl` hangs                              | Containers still starting — check `docker compose ps` and retry.               |

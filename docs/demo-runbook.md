# Demo Runbook — BobOps

> **Audience: the demo operator, not the agent.**
> This file contains the expected fix. Keep IBM Bob scoped to `bobops/` during
> the demo so the investigation stays real.

## Branch map

| Branch     | State                                                             |
|------------|-------------------------------------------------------------------|
| `incident` | The broken stack — `GET /health` returns `502`. Demo starts here.  |
| `working`  | Reference healthy state — returns `200`. Used to verify the reset. |
| `main`     | Same content as `incident`.                                        |

The whole incident is a single line of configuration:

```bash
git diff incident working
```

## Before the demo

Run on the machine you will present from — the first build pulls
`python:3.12-slim` and installs the dependencies, which is not something you
want happening live:

```bash
docker compose -f bobops/docker-compose.yml build
```

Checklist:

- [ ] `git rev-parse --abbrev-ref HEAD` prints `incident`
- [ ] `git status --short` is empty
- [ ] Port `80` is free — `lsof -nP -iTCP:80 -sTCP:LISTEN`
- [ ] `python3 -m pytest --version` works
- [ ] Docker is running

## Act 1 — Show the incident

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
docker compose -f bobops/docker-compose.yml exec backend python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"
```

```bash
python3 -m pytest bobops/tests/ -v
```

`2 failed` — `expected 200 from http://localhost/health, got 502`.

## Act 2 — Hand it to Bob

Open IBM Bob scoped to **`bobops/`** (not the repository root — `docs/` holds
this runbook and the solution description). Prompt along the lines of:

> The `/health` endpoint is returning 502 in production. Investigate the
> repository, find the root cause, apply the minimal fix and validate it.

What Bob is expected to do: read the architecture, correlate the proxy logs
with the orchestration configuration, edit one line, reload the proxy, rerun
the health check, and write the incident report.

## Act 3 — Validate the fix

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

## Reset between rehearsals

```bash
git restore bobops/
```

```bash
docker compose -f bobops/docker-compose.yml restart proxy
```

Back to `502`. If Bob also created files (an incident report, for example),
remove them with `git clean -n bobops/` to preview and `git clean -f bobops/`
to delete.

## Tear down

```bash
docker compose -f bobops/docker-compose.yml down
```

## Troubleshooting

| Symptom                                   | Cause and fix                                                                 |
|-------------------------------------------|-------------------------------------------------------------------------------|
| Still `502` after the fix                 | The proxy was not reloaded — `docker compose restart proxy`.                   |
| `port is already allocated` on `up`       | Something else holds port `80`. Free it before starting.                       |
| Proxy container restarting or exiting     | Configuration syntax error — `docker compose exec proxy nginx -t`.             |
| Tests error out instead of failing        | The stack is not running, or port `80` is not reachable from the host.         |
| `curl` hangs                              | Containers still starting — check `docker compose ps` and retry.               |

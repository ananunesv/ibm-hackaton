# BobOps — IBM Bob Incident Response POC

> **IBM Hackathon 2026** — demonstrating agentic incident investigation
> with [IBM Bob](https://bob.ibm.com/) acting as an AI engineering agent.
> All terminal commands and code changes were human-approved during execution.

---

## Problem

When a production system fails with an HTTP 502, no one immediately knows what
broke. The service stays down while an engineer investigates by hand:

1. Identify all components
2. Open logs across multiple containers
3. Check proxy and application configs
4. Compare service names, ports, and hostnames
5. Find the inconsistency
6. Apply the fix
7. Validate
8. Write the incident report

This process is slow, expert-dependent, and poorly documented. Trivial
configuration errors — a single wrong hostname, a missing port — can cause
minutes or hours of downtime and still require senior-level triage.

---

## Solution — BobOps

**BobOps** is a minimal, self-contained production stack intentionally shipped
in a broken state. It is used to demonstrate IBM Bob operating in Agent mode as
an AI engineering agent with human approval.

Bob (in Agent mode, with human approval at each step) was asked to:

> *"The `/health` endpoint is returning 502 in production. Investigate the
> repository, find the root cause, apply the minimal fix and validate it."*

Bob read the repository, executed diagnostic commands, identified the root
cause, applied the fix, validated the outcome, and generated a detailed
incident report through an interactive natural-language Agent session.

---

## Architecture

```
client
  │  HTTP :80
  ▼
proxy  (nginx:alpine)
  │  Docker internal DNS (127.0.0.11)
  ▼
backend  (FastAPI + uvicorn, port 8000 — internal only)
```

| Component     | File / Image              | Role                                        |
|---------------|---------------------------|---------------------------------------------|
| `backend`     | `bobops/app/main.py`      | FastAPI service, `GET /health` → JSON       |
| `proxy`       | `bobops/nginx/nginx.conf` | nginx reverse proxy, sole public entry point |
| Orchestration | `bobops/docker-compose.yml` | Wires both services on a shared bridge    |
| Validation    | `bobops/tests/test_health.py` | End-to-end pytest suite through proxy   |

---

## Incident Scenario

The stack is deployed with both containers running and healthy-looking, yet
every request through the public entry point fails:

```
HTTP/1.1 502 Bad Gateway
Server: nginx/1.31.4
```

The bug: `bobops/nginx/nginx.conf` references an upstream hostname (`api`) that
does not exist on the Docker Compose network. The actual service name — and
therefore the only hostname Docker's DNS resolves — is `backend`.

```nginx
# broken (incident branch)
set $backend_host api;

# fixed (main branch)
set $backend_host backend;
```

Because the upstream is stored in a variable, nginx resolves it at request time
via the `resolver` directive, not at startup. The wrong hostname produces no
startup error or config-test failure — only silent 502s in production, on every
single request.

---

## Branch Map

| Branch     | `nginx.conf` upstream | Response    | Purpose                         |
|------------|----------------------|-------------|---------------------------------|
| `incident` | `api`                | **502**     | Broken demo state — start here  |
| `main`     | `backend`            | **200**     | Healthy integrated state        |

---

## How IBM Bob Is Used

IBM Bob operates in **Agent mode** — a mode that reads files, proposes and
executes shell commands, edits code, and generates documentation. Every
command execution and every file edit was **human-approved** before it ran;
Bob did not act autonomously without oversight.

Bob was given access to the `bobops/` directory and prompted with a single
incident description. No hints about the root cause were provided.

---

## Workflow

### What Bob actually did (in order)

1. **Repository inspection** — read `docker-compose.yml`, `app/main.py`,
   `nginx/nginx.conf`, `app/Dockerfile`, `tests/test_health.py`, and
   `bobops/README.md` to understand the full architecture before running
   any command.

2. **Static analysis** — identified the variable-based `proxy_pass` pattern,
   noted the `resolver 127.0.0.11` directive, and flagged `api` as a
   potentially wrong hostname before executing anything.

3. **Live diagnostics** (each command human-approved):
   - `docker compose ps` — confirmed both containers were `Up`; ruled out
     crash or startup failure.
   - `curl -i http://localhost/health` — reproduced the 502.
   - `docker compose exec proxy wget -qO- http://backend:8000/health` —
     proved the backend was healthy and the network functional; isolated the
     fault to nginx's proxy configuration.
   - `docker compose exec proxy nginx -t` — confirmed no syntax error;
     explained why the container started cleanly.
   - `docker compose logs proxy` — found the smoking gun:
     `api could not be resolved (2: Server failure)` on every request.
   - `docker compose logs backend` — confirmed zero nginx-proxied requests
     ever reached the application.
   - `nslookup backend. 127.0.0.11` — resolved to `172.21.0.2` ✅
   - `nslookup api. 127.0.0.11` — `SERVFAIL` ❌ — root cause confirmed.

4. **Fix** (human-approved edit) — changed one token in
   `bobops/nginx/nginx.conf`: `api` → `backend`.

5. **Validation**:
   - `nginx -t` — syntax still valid.
   - `docker compose restart proxy` — proxy reloaded with the corrected config.
   - `curl -i http://localhost/health` — `HTTP/1.1 200 OK` ✅
   - `pytest tests/ -v` — `2 passed` ✅

6. **Documentation** — generated
   [`docs/incident-502-investigation.md`](docs/incident-502-investigation.md),
   a 445-line structured incident report including executive summary,
   investigation timeline, all command outputs, evidence table, DNS analysis,
   root cause, and lessons learned.

---

## Validation

After the fix, both automated end-to-end tests pass:

```
tests/test_health.py::test_health_returns_200               PASSED
tests/test_health.py::test_health_returns_expected_payload  PASSED

2 passed in 0.05s
```

And the public endpoint returns:

```
HTTP/1.1 200 OK
Content-Type: application/json

{"status":"healthy","service":"bobops-api"}
```

---

## Results

| Metric                    | Value                                  |
|---------------------------|----------------------------------------|
| Time from prompt to fix   | Single conversational session          |
| Files read by Bob         | 7                                      |
| Diagnostic commands run   | 8 (all human-approved)                 |
| Lines changed in the fix  | 1                                      |
| Tests passing after fix   | 2 / 2                                  |
| Incident report generated | Yes — 445 lines, 13 sections           |
| Human code written        | 0                                      |

---

## IBM Bob Execution Record

> This section documents accurately what IBM Bob did and what required
> human approval. No autonomous unsupervised actions were taken.

Bob operated in **Agent mode** within the IBM Bob interface. The session
proceeded as follows:

| Step | Bob's action | Human role |
|------|-------------|------------|
| Architecture review | Read all source files | Observation |
| Static analysis | Identified `api` as suspicious | Observation |
| `docker compose ps` | Proposed and ran | Approved |
| `curl -i` | Proposed and ran | Approved |
| `wget` from proxy | Proposed and ran | Approved |
| `nginx -t` | Proposed and ran | Approved |
| `docker compose logs proxy` | Proposed and ran | Approved |
| `docker compose logs backend` | Proposed and ran | Approved |
| `nslookup backend` / `nslookup api` | Proposed and ran | Approved |
| Edit `nginx.conf` (`api` → `backend`) | Proposed and applied | Approved |
| `docker compose restart proxy` | Proposed and ran | Approved |
| `curl -i` (post-fix) | Proposed and ran | Approved |
| `pytest tests/ -v` | Proposed and ran | Approved |
| Incident report | Generated by IBM Bob during the agentic workflow | Reviewed |

**What Bob did not do:** Bob did not access external systems, did not push to
remote, and did not take any action without an explicit human approval step in
the Agent interface.

**Honest scope:** This POC demonstrates one representative incident — a 502
caused by a proxy misconfiguration in a two-container Compose stack. It does
not claim Bob can resolve arbitrary production incidents. It shows the
end-to-end investigation, fix, and documentation workflow working on a real,
running environment.

---

## Demo

To reproduce the demo from scratch:

```bash
# Start from the broken state
git switch incident
docker compose -f bobops/docker-compose.yml up -d --build

# Confirm the incident
curl -i http://localhost/health           # 502
python3 -m pytest bobops/tests/ -v       # 2 failed

# Hand to Bob → Bob investigates, fixes, validates

# Confirm the resolution
curl -i http://localhost/health           # 200
python3 -m pytest bobops/tests/ -v       # 2 passed
```

See [`docs/demo-runbook.md`](docs/demo-runbook.md) for the full step-by-step
operator guide including reset and troubleshooting instructions.

---

## Documentation

| Document | Description |
|---|---|
| [`bobops/README.md`](bobops/README.md) | Stack README: architecture, run, reproduce, validate |
| [`docs/demo-runbook.md`](docs/demo-runbook.md) | Operator guide for running the live demo |
| [`docs/incident-502-investigation.md`](docs/incident-502-investigation.md) | Full incident report generated by Bob |
| [`docs/problem.md`](docs/problem.md) | Problem statement |
| [`docs/solution.md`](docs/solution.md) | Solution description and scope |

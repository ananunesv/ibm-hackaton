# Problem

When a production system fails with an HTTP 502, no one immediately knows what
broke; the service stays down while someone investigates by hand.

## User

Developers, DevOps/SRE and on-call engineers who must restore a service fast.

## Current process (without Bob)

1. Identify components
2. Open logs
3. Check configs
4. Compare services / ports / hostnames
5. Find the inconsistency
6. Fix
7. Test
8. Document

All manual, across multiple tools.

## Pain

- **Slow** — minutes or hours of downtime just to find the cause.
- **Expert-dependent** — juniors get stuck, seniors become the bottleneck.
- **Repetitive** — most incidents are trivial config errors that still cost a lot.
- **Poor traceability** — incident docs are rarely done well.

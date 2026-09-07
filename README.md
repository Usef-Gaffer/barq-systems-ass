<img src="assets/barq-logo.svg" alt="BARQ Systems" width="180">

# BARQ Systems DevOps Internship Task - Solution

Fixed, tested and documented version of the supplied BARQ Systems assessment
environment: a Flask API behind NGINX, load-balanced across multiple
instances, backed by PostgreSQL and Redis.

> **Note on documentation timing:** this README, along with `decisions.md`,
> `troubleshooting.md`, `security_review.md` and `log_analysis.md`, was
> completed after the two-instance setup was working and verified, and is
> updated once more after the live video changes (third instance, port 8090)
> to keep it accurate. Documentation-only commits after the technical work
> reflect that timing, not late discovery of issues — see `AI_USAGE.md` and
> the evidence index for exact commit references.

## What was fixed

The starter environment shipped with several intentional defects (full list
and evidence in `troubleshooting.md` and `decisions.md`):
wrong PostgreSQL/Redis connection port and password in `config/app.env`;
Flask bound to `127.0.0.1` instead of `0.0.0.0`; a duplicated `INSTANCE_ID`
across app instances; an NGINX healthcheck probing a non-existent
`/healthz` path; a mismatched NGINX host/container port mapping;
PostgreSQL/Redis published to the host; a PostgreSQL volume mounted at the
wrong path shadowed by a `tmpfs` mount (data loss on recreation); NGINX
attached to the backend network; a wrong upstream port for `app-01`; and a
Dockerfile that ran as root and copied secrets into the image.

## Prerequisites

- Docker Desktop with the WSL2 backend, and WSL2 integration enabled for
  the distro you use.
- `docker` and `docker compose` (v2) available in that shell.
- Python 3 (used to run `validate.py`/`failure_test.py`, and to pretty-print
  JSON responses in the examples below).
- Ports `8080` (or `8090` after the live change) free on `127.0.0.1`.

## Setup

```bash
git clone <this-repository-url>
cd barq-systems-ass
cp .env.example .env   # optional; PUBLIC_PORT defaults to 8080
```

## Build and start

```bash
docker compose up -d --build
docker compose ps
```

All five containers (`nginx`, `app-01`, `app-02`, `postgres`, `redis`)
should report `Up` / `(healthy)`. `nginx` has no healthcheck defined but
depends on both app services having started.

## Test the endpoints (through NGINX only)

```bash
curl -s http://localhost:8080/            | python3 -m json.tool
curl -s http://localhost:8080/health      | python3 -m json.tool
curl -s http://localhost:8080/ready       | python3 -m json.tool
curl -s http://localhost:8080/records     | python3 -m json.tool
curl -s -X POST http://localhost:8080/records \
     -H "Content-Type: application/json" -d '{"title":"example"}' | python3 -m json.tool
curl -s http://localhost:8080/counter     | python3 -m json.tool

# Prove both backends serve traffic through NGINX:
for i in $(seq 1 10); do
  curl -s http://localhost:8080/instance | python3 -c "import sys,json; print(json.load(sys.stdin)['instance_id'])"
done
```

## Validate the environment

```bash
python3 validate.py
```

Runs bounded checks (public access, `/health`, `/ready`, `/records`,
`/counter`, both backends reachable via `/instance`, network isolation
between nginx and postgres, and no prohibited host ports). Exits `0` on
success, non-zero on any failed check, with a `PASS`/`FAIL` line per check.

## Failure and recovery test

```bash
python3 failure_test.py
```

Stops `app-01`, sends traffic and measures the success/error split while it
is down, restarts it, and verifies it resumes serving requests. Exits
non-zero if the surviving backend does not take over, or if `app-01` does
not resume serving after restart.

## Backup and restore

```bash
mkdir -p backups
./backup.sh backups              # creates backups/barq_tasks_<timestamp>.dump
./restore.sh backups/<file>.dump # restores a given backup, --clean --if-exists
```

To prove persistence end-to-end (as done during development, see
`troubleshooting.md`):

```bash
curl -s -X POST http://localhost:8080/records -H "Content-Type: application/json" \
     -d '{"title":"persistence-check"}'
docker compose up -d --force-recreate app-01 app-02 postgres
curl -s http://localhost:8080/records | python3 -m json.tool   # record still present
```

## Cleanup

```bash
docker compose down          # stops and removes containers, keeps the named volume
docker compose down -v       # also removes the named volume (destroys postgres data)
```

Do not use `docker compose down -v` while testing persistence.

## Architecture

See `architecture.png` for the full diagram (request flow, ports, networks,
storage, health relationships). Summary:

```
client -> localhost:8090 -> nginx (frontend network only)
                               -> app-01 / app-02 / app-03 (frontend + backend)
                                    -> postgres:5432 (backend network, internal)
                                    -> redis:6379    (backend network, internal)
```

Only NGINX is published on the host. NGINX cannot reach PostgreSQL/Redis
directly (verified: DNS resolution for `postgres` fails from inside the
`nginx` container once it is restricted to the frontend network).

## Reports

- [`log_analysis.md`](log_analysis.md) - full analysis of the three
  supplied historical logs, with commands, counts, a timeline and
  root-cause evidence.
- [`troubleshooting.md`](troubleshooting.md) - chronological investigation
  journal for every fix made in this repository.
- [`decisions.md`](decisions.md) - key technical decisions, alternatives
  and trade-offs.
- [`security_review.md`](security_review.md) - 8 concrete security/
  production-readiness findings, separating implemented fixes from
  production follow-up.
- [`AI_USAGE.md`](AI_USAGE.md) - AI usage disclosure and verification
  approach.
- [`docs/EVIDENCE_INDEX.md`](docs/EVIDENCE_INDEX.md) - maps each task
  requirement to its evidence, commit, and video timestamp.

## Answers to the brief's questions

- **What failed first?** A full outage of one backend container (5 minutes,
  connection refused on all paths) — see `log_analysis.md` Q1/Q7.
- **What patterns did the logs reveal? How did you avoid double-counting?**
  Two distinct failure classes (instance outage vs. dependency timeout);
  double-counting avoided by treating comma-separated `upstream` values and
  exact-duplicate lines as one request each — see `log_analysis.md` Q2.
- **How do requests flow? Why these ports/networks/readiness checks?** See
  Architecture above and `decisions.md` Decisions 2-4.
- **Why these timeouts/retries/restart settings?** See `decisions.md`
  Decision 3 (retries) and the Dockerfile/compose healthcheck values.
- **When should validation fail? What does green CI prove, or not prove?**
  `validate.py` fails on any unreachable endpoint, a backend never observed
  via `/instance`, network isolation being violated, or any prohibited host
  port. A green CI run proves the stack builds, starts, becomes ready, and
  passes those specific checks in a fresh environment on that commit — it
  does not prove production-scale load handling, security beyond the
  checked ports, or that the two live-only steps (video_challenge.sh fix,
  port/instance-count change) work, since those are not part of the
  automated pipeline.
- **Which single points of failure remain?** One PostgreSQL instance, one
  Redis instance, one Docker host — see `security_review.md` finding 8.
- **What would you improve? How did you verify AI-assisted work?** See
  `security_review.md` (Production follow-up items) and `AI_USAGE.md`.

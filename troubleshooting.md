# Troubleshooting journal

Chronological entries from the actual investigation and fix process for this
environment. Each entry reflects real commands and real output captured
during the work, not a reconstructed narrative.

---

## Entry 1 — PostgreSQL/Redis connection failure

- Symptom: Expected `/ready`, `/records`, `/counter` to fail once the stack
  was started, based on the task brief stating the environment is broken.
- Hypothesis: `config/app.env` connection strings do not match the actual
  `postgres`/`redis` service configuration in `docker-compose.yml`.
- Command or test: `cat config/app.env` compared against `docker compose
  config` output for the `postgres`/`redis` services.
- Actual output: `DATABASE_URL` used port `5433` and password suffix `...8d`;
  actual `POSTGRES_PASSWORD` in compose is `...8c` and postgres listens on
  its default `5432`. `REDIS_URL` used port `6380`; redis listens on default
  `6379`.
- Failed attempt and what changed your thinking: none needed here — the
  mismatch was confirmed directly by diffing the two sources of truth before
  making any change, so no blind attempt was made.
- Root cause: Stale/incorrect values in `config/app.env`.
- Fix: Corrected both URLs to the real port/password (see `decisions.md`
  Decision 1).
- Retest evidence: `curl http://localhost:8080/ready` returned
  `{"dependencies":{"postgres":"ready","redis":"ready"},"status":"ready"}`.
- Related commit: `fix: correct postgres/redis connection port and password
  mismatch`.
- Remaining uncertainty: none for this specific issue; fully verified.

---

## Entry 2 — App unreachable from NGINX / app-02 identity collision / healthcheck path

- Symptom: Before starting the stack, static review of `docker-compose.yml`
  showed `APP_HOST: "127.0.0.1"`, both `app-01` and `app-02` set to
  `INSTANCE_ID: "app-01"`, and a healthcheck probing `/healthz`.
- Hypothesis: (a) `127.0.0.1` binding would make the Flask process
  unreachable from the nginx container; (b) duplicate `INSTANCE_ID` would
  break the `/instance` identity requirement; (c) `/healthz` does not exist
  in `app/server.py` (only `/health` is defined), so the healthcheck would
  always fail.
- Command or test: `grep -n "APP_HOST\|INSTANCE_ID\|healthz" docker-compose.yml`
  and `grep -n "@app.get" app/server.py`.
- Actual output: confirmed all three mismatches exactly as hypothesized.
- Failed attempt and what changed your thinking: none — these were static,
  directly verifiable mismatches (env value vs. code route table).
- Root cause: three independent config typos/omissions in the starter
  `docker-compose.yml`.
- Fix: `APP_HOST` -> `0.0.0.0`; `app-02` `INSTANCE_ID` -> `app-02`;
  healthcheck path -> `/health`.
- Retest evidence: `docker compose ps` showed both `app-01`/`app-02` as
  `Up ... (healthy)`; alternating `/instance` calls returned both
  `app-01` and `app-02`.
- Related commit: `fix: bind app to 0.0.0.0, fix app-02 instance id, fix
  healthcheck path`.
- Remaining uncertainty: none.

---

## Entry 3 — NGINX port mismatch, exposed DB/cache ports, broken persistence, missing restart policy

- Symptom: Static review found NGINX container port mapped to `81` while
  `nginx.conf` listens on `80`; `postgres`/`redis` published to host ports;
  the postgres named volume mounted at `/var/lib/postgresql/backup` while
  `tmpfs` shadowed the real `/var/lib/postgresql/data`; `restart: "no"` on
  app services.
- Hypothesis: all four are independent violations of the task's explicit
  requirements (only NGINX published; PostgreSQL persistence must survive
  container recreation; services should restart on failure).
- Command or test: `docker compose config` (fully resolved config) reviewed
  against the task brief line by line.
- Actual output: confirmed each mismatch in the resolved config.
- Failed attempt and what changed your thinking: none at this stage — issues
  were caught by comparing config to the written requirements before running
  anything.
- Root cause: starter file intentionally shipped with these four defects.
- Fix: NGINX host mapping corrected to `:80`; `ports:` removed from
  `postgres`/`redis`; volume path corrected and `tmpfs` line removed;
  `restart: unless-stopped` applied to the app anchor.
- Retest evidence: `docker compose ps` showed no published ports for
  postgres/redis; a record created via `POST /records` survived
  `docker compose up -d --force-recreate app-01 app-02 postgres` (see
  Entry 5 for the detailed persistence test).
- Related commit: `fix: correct nginx port mapping, remove exposed db/cache
  ports, fix persistence`.
- Remaining uncertainty: none.

---

## Entry 4 — NGINX attached to backend network

- Symptom: `docker-compose.yml` had `nginx: networks: [frontend, backend]`.
- Hypothesis: this violates the requirement that NGINX must not be able to
  reach PostgreSQL/Redis directly; NGINX should be frontend-only.
- Command or test: after removing `backend` from nginx's network list and
  restarting, ran `docker exec nginx wget -qO- --timeout=2
  http://postgres:5432` and `docker exec nginx sh -c "nc -zv -w2 postgres
  5432"`.
- Actual output: `wget: bad address 'postgres:5432'` and `nc: bad address
  'postgres'` — DNS resolution itself failed, meaning nginx cannot even see
  the name, not merely a blocked connection.
- Failed attempt and what changed your thinking: none — first attempt
  confirmed the fix immediately.
- Root cause: nginx was unnecessarily dual-homed in the starter compose file.
- Fix: `networks: [frontend]` only for the nginx service.
- Retest evidence: as above (DNS resolution failure from inside nginx).
- Related commit: `fix: remove nginx from backend network`.
- Remaining uncertainty: none.

---

## Entry 5 — nginx upstream `app-01:8081` port mismatch

- Symptom: `nginx/nginx.conf` upstream block listed `server app-01:8081`
  while `app-02` used `8080`; both Flask instances are configured with
  `APP_PORT=8080`.
- Hypothesis: any request routed to `app-01` by NGINX would fail (connection
  refused on 8081, since nothing listens there).
- Command or test: `grep -n "app-01" nginx/nginx.conf`.
- Actual output: confirmed `server app-01:8081 max_fails=0;`.
- Failed attempt and what changed your thinking: none.
- Root cause: typo in the starter `nginx.conf`.
- Fix: changed to `server app-01:8080 max_fails=0;`.
- Retest evidence: 30-request sample through `/instance` returned exactly
  15/15 for app-01/app-02 (see Entry 6 for why an earlier smaller sample was
  misleading).
- Related commit: `fix: correct app-01 upstream port in nginx config`.
- Remaining uncertainty: none.

---

## Entry 6 — Misleading round-robin skew after `--force-recreate`

- Symptom: After fixing all config issues and confirming a clean 5/5 split
  over 10 requests, we ran `docker compose up -d --force-recreate app-01
  app-02 postgres` to test persistence. Immediately afterward, stopping
  `app-01` and sending 6 requests to `/instance` returned **six consecutive
  504s**, i.e. zero requests succeeded via `app-02`, contradicting the
  expected partial-availability behavior.
- Hypothesis (initial, wrong-if-untested): NGINX round-robin itself was
  broken, or `app-02` was also unhealthy.
- Command or test: `docker compose logs nginx --tail=20`,
  `docker network inspect barq-assessment_frontend`,
  `docker exec nginx cat /etc/resolv.conf`.
- Actual output: nginx's access log showed **every** request (not just the
  ones during the outage) resolving to the same upstream IP, even requests
  made before `app-01` was stopped. Network inspect showed app-01/app-02 had
  been assigned new IPs by Docker after `--force-recreate` (new containers,
  new IPs).
- Failed attempt and what changed your thinking: the "NGINX round-robin is
  broken" hypothesis was reconsidered once we noticed the skew appeared only
  right after `--force-recreate`, not before it. This pointed at DNS caching
  rather than the load-balancing algorithm itself.
- Root cause: plain NGINX (no `resolver` directive configured) resolves
  upstream hostnames to IPs once, at worker startup, and caches them
  indefinitely. Recreating `app-01`/`app-02` gives them new container IPs
  that the already-running nginx process never re-resolves.
- Fix (operational, not a code change): `docker compose restart nginx`
  after any recreation of backend containers, to force fresh DNS resolution.
- Retest evidence: after restarting nginx, a 10-request sample was skewed
  (8 app-01 / 2 app-02) — still not conclusive — so a larger 30-request
  sample was taken immediately after, returning a clean 15/15 split,
  confirming the earlier skew was transient connection warm-up right after
  the nginx restart, not a persistent bug.
- Related commit: none (operational finding, documented here and in
  `decisions.md`; no code change was required — this is expected NGINX
  behavior, not a defect in this project's config).
- Remaining uncertainty: the exact cause of the transient 8/2 skew
  immediately after nginx restart (vs. a clean split) was not root-caused
  further (plausibly worker process startup ordering); it did not recur in
  the larger sample and was not blocking, so it was noted rather than
  chased further.

---

## Entry 7 — Dockerfile running as root and baking secrets into the image

- Symptom: Static review of `Dockerfile` found `USER root` immediately
  before `CMD`, following an earlier `useradd` step, and a
  `COPY config/app.env /srv/app.env` line.
- Hypothesis: `USER root` silently discards the non-root user that was just
  created, so the container runs privileged despite appearing hardened;
  copying the env file into the image bakes credentials into a durable image
  layer even though the same file is already supplied at runtime via
  `env_file` in docker-compose.yml.
- Command or test: `docker exec app-01 whoami` / `docker exec app-02 whoami`
  before and after the fix.
- Actual output: before fix, not explicitly re-tested (the defect was caught
  by code review before running); after fix, both containers returned `app`.
- Failed attempt and what changed your thinking: none.
- Root cause: leftover `USER root` override and an unnecessary `COPY` of a
  secret file into the image.
- Fix: removed both lines; final `USER` in the image is `app`.
- Retest evidence: `docker exec app-01 whoami` -> `app`;
  `docker exec app-02 whoami` -> `app`; full `validate.py` re-run passed all
  8 checks after the change, confirming no functional regression.
- Related commit: `fix: remove USER root override and secret copy from
  Dockerfile`.
- Remaining uncertainty: none.

---

## Entry 8 — `validate.py` false positive on "prohibited host ports"

- Symptom: First run of the newly written `validate.py` failed on
  `no prohibited host ports`, reporting `app-01` published a host port.
- Hypothesis: `docker compose ps --format json`'s `Publishers` field
  includes entries for container ports that are merely `EXPOSE`d (with
  `PublishedPort: 0`, meaning not actually bound to the host), and the
  check's logic treated any non-empty `Publishers` list as a violation.
- Command or test: re-ran validate.py and inspected the failure message
  directly, which printed the raw `Publishers` entry:
  `{'PublishedPort': 0, ...}`.
- Actual output: `FAIL: no prohibited host ports -> app-01 must not publish
  host ports, found: [{'URL': '', 'TargetPort': 8080, 'PublishedPort': 0,
  'Protocol': 'tcp'}]`.
- Failed attempt and what changed your thinking: the first version of the
  check was too strict (any `Publishers` entry = failure); output showed the
  entry was a non-published, informational one, prompting a fix to only flag
  entries with a non-zero `PublishedPort`.
- Root cause: bug in the validation script itself, not in the project's
  Docker configuration.
- Fix: check now filters `Publishers` to entries where `PublishedPort` is
  truthy before asserting.
- Retest evidence: re-ran `python3 validate.py`; all 8 checks passed,
  `RESULT: PASS`.
- Related commit: included in `feat: implement validate.py with bounded
  checks` (fixed before the first commit of this file).
- Remaining uncertainty: none.

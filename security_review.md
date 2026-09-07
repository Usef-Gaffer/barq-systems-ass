# Security and production-readiness review

Findings are separated into **Implemented fixes** (already done in this
repository, with evidence) and **Production follow-up** (recommended for a
real deployment, out of scope for this lab). Covers secrets, ports,
container user, images, networks, backup, monitoring and availability.

---

## 1. Container ran as root despite a non-root user being created

- Risk and evidence: `Dockerfile` created a low-privilege `app` user via
  `useradd`, but then set `USER root` right before `CMD`, so the running
  container was still root (`docker exec ... whoami` would have printed
  `root`).
- Impact: A remote code execution vulnerability in the Flask app or any of
  its dependencies would grant the attacker root inside the container,
  widening the blast radius (e.g. easier container breakout, ability to
  modify installed packages).
- Implemented fix / commit: removed `USER root`; container now runs as
  `app` (uid 10001). Commit: `fix: remove USER root override and secret
  copy from Dockerfile`. Verified: `docker exec app-01 whoami` -> `app`.
- Production follow-up: add `read_only: true` on the app services plus an
  explicit `tmpfs` for any directory the app actually needs to write to, and
  drop all Linux capabilities (`cap_drop: [ALL]`) since the app needs none.
- How to verify: `docker exec <container> whoami`; `docker inspect
  --format '{{.HostConfig.ReadonlyRootfs}}' <container>`.

## 2. Database/cache credentials baked into a Docker image layer

- Risk and evidence: `Dockerfile` had `COPY config/app.env /srv/app.env`,
  writing the PostgreSQL/Redis connection strings (including password) into
  a durable image layer, retrievable via `docker history` or by exporting/
  pushing the image, even though the same file was already supplied safely
  at runtime via `env_file` in `docker-compose.yml`.
- Impact: Anyone with pull access to the built image (e.g. a shared
  registry) could extract the credentials regardless of runtime network
  access controls.
- Implemented fix / commit: removed the `COPY` line entirely; credentials
  now only ever exist as a runtime-injected environment variable, never in
  an image layer. Commit: `fix: remove USER root override and secret copy
  from Dockerfile`.
- Production follow-up: replace the plaintext `config/app.env` file
  approach entirely with a secrets manager (AWS Secrets Manager, HashiCorp
  Vault, or Docker/Swarm/Kubernetes native secrets) and credential rotation.
- How to verify: `docker history <image>` should show no layer containing
  `app.env`; confirmed no such layer exists after the fix.

## 3. PostgreSQL and Redis were reachable directly from the host

- Risk and evidence: starter `docker-compose.yml` published
  `127.0.0.1:15432:5432` and `127.0.0.1:16379:6379`, exposing the database
  and cache directly on the host network stack, bypassing NGINX/the app
  layer entirely.
- Impact: Any process on the host (or, if misconfigured beyond localhost,
  the network) could connect directly to PostgreSQL/Redis, bypassing all
  application-level access control and auditing.
- Implemented fix / commit: removed both `ports:` entries. Commit:
  `fix: correct nginx port mapping, remove exposed db/cache ports, fix
  persistence`. Verified: `docker compose ps` shows no host port for
  postgres/redis, and `validate.py`'s "no prohibited host ports" check
  passes.
- Production follow-up: in a real deployment, add authentication-layer
  defense in depth even for internal-only services (e.g. mutual TLS between
  app and database), since network isolation alone is one layer of defense.
- How to verify: `docker compose ps`; `python3 validate.py` (dedicated
  check); `nc -zv <host-ip> 15432` from outside the container network should
  fail.

## 4. NGINX had network-level access to PostgreSQL and Redis

- Risk and evidence: starter compose attached `nginx` to both `frontend`
  and `backend` networks, so nginx could, at the network layer, reach
  `postgres:5432` and `redis:6379` directly, bypassing the app tier.
- Impact: A compromised or misconfigured NGINX (e.g. via a malicious
  `proxy_pass` directive change, or an NGINX CVE) could pivot directly to
  the database/cache, defeating the purpose of a layered network topology.
- Implemented fix / commit: nginx restricted to `frontend` only. Commit:
  `fix: remove nginx from backend network`. Verified live:
  `docker exec nginx sh -c "nc -zv -w2 postgres 5432"` returns
  `nc: bad address 'postgres'` — DNS resolution itself fails, proving
  network-level isolation, not just a blocked port.
- Production follow-up: apply the same "least network" principle to any
  future service added to this stack (e.g. a metrics/logging sidecar should
  not automatically join `backend`).
- How to verify: `docker network inspect barq-assessment_backend` should not
  list an `nginx` endpoint; `validate.py`'s network isolation check.

## 5. PostgreSQL data was not actually persistent despite a named volume

- Risk and evidence: the named volume `postgres-data` was mounted at
  `/var/lib/postgresql/backup` (a path Postgres does not use for its data
  directory) while a `tmpfs` mount shadowed the real data directory
  (`/var/lib/postgresql/data`) with in-memory, non-persistent storage.
  Every container recreation silently wiped all data.
- Impact: In a real incident requiring a container restart/recreation (e.g.
  a security patch to the postgres image), all application data would be
  lost without warning, since the volume configuration gave a false
  impression of persistence.
- Implemented fix / commit: volume corrected to mount at
  `/var/lib/postgresql/data`; `tmpfs` override removed. Commit:
  `fix: correct nginx port mapping, remove exposed db/cache ports, fix
  persistence`. Verified live: created a record, ran
  `docker compose up -d --force-recreate app-01 app-02 postgres`, confirmed
  the record survived.
- Production follow-up: add scheduled, automated, off-host backups (beyond
  the on-demand `backup.sh` written for this lab) with retention and
  restore-testing on a schedule, not just on demand.
- How to verify: `./backup.sh` + `POST /records` + `docker compose up -d
  --force-recreate ...` + `GET /records` showing the record persisted (done
  above); `./restore.sh <backup>` restoring a prior state correctly (also
  done and verified above).

## 6. No resource limits on any service

- Risk and evidence: none of the services in `docker-compose.yml` define
  `deploy.resources.limits` (or the equivalent `mem_limit`/`cpus` fields),
  so a single runaway process (e.g. a bug causing unbounded memory growth in
  one Flask instance) can consume all host resources and degrade or crash
  every other service on the same host.
- Impact: Denial of service against the entire stack (including the
  database) triggered by a bug in a single component, rather than being
  contained to that component.
- Implemented fix / commit: not yet implemented in this lab environment (see
  Production follow-up). Flagged here as an honest gap rather than omitted.
- Production follow-up: add explicit CPU/memory limits per service (e.g.
  `mem_limit: 256m` for each Flask instance, `mem_limit: 512m` for postgres),
  sized from observed load, and configure the kernel OOM killer behavior
  deliberately rather than leaving it to chance.
- How to verify: `docker inspect --format '{{.HostConfig.Memory}}'
  <container>` should be non-zero after the fix; currently returns `0`
  (unlimited) for all services, confirming the gap.

## 7. No centralized/shipped logging or monitoring beyond container stdout

- Risk and evidence: all structured logs (`log_event` in `server.py`, NGINX
  JSON access log) go to stdout/stderr only, captured by `docker compose
  logs`. There is no log shipping, retention beyond the container lifecycle,
  or alerting on error-rate spikes (e.g. the kind of spike documented in
  `log_analysis.md`, section 3: 14.48% error rate during the historical
  incident, would not trigger any alert today).
- Impact: A real incident like the one analyzed in `log_analysis.md` would
  only be discoverable after the fact by manually inspecting container logs
  before they are rotated/lost, with no proactive alerting.
- Implemented fix / commit: not implemented in this lab (structured JSON
  logging with `request_id`/`instance_id` correlation was already present in
  the starter app and preserved as-is, since it is exactly what enabled the
  log analysis in this repository).
- Production follow-up: ship logs to a centralized system (e.g. Loki/ELK),
  and add alerting on `/ready` failures and elevated 5xx rates using the
  same `request_id`/`instance_id` fields already emitted.
- How to verify: query for `docker compose logs` continuity after container
  restart today shows history is lost — confirming logs do not currently
  survive beyond the container's lifetime.

## 8. Single points of failure: one PostgreSQL instance, one Redis instance, one Docker host
- Risk and evidence: `docker-compose.yml` runs exactly one `postgres` and
  one `redis` container with no replication, and the entire stack (NGINX +
  2-3 app instances + postgres + redis) runs on a single Docker host. The
  app tier is the only horizontally-scaled component; `failure_test.py`
  only demonstrates app-tier redundancy (see live output: 5/10 succeeded
  when `app-01` was stopped), not database/cache redundancy.
- Impact: A postgres or redis failure (or the host itself failing) takes the
  entire stack down regardless of how many app instances are running, since
  `/ready` will correctly report `not_ready` and all data-dependent
  endpoints will fail.
- Implemented fix / commit: none — this is a structural limitation of a
  single-host Compose lab environment, explicitly out of scope for this
  task's infrastructure, and is disclosed here rather than glossed over.
- Production follow-up: PostgreSQL with a replica + automated failover
  (e.g. Patroni or a managed service), Redis with Sentinel/Cluster, and the
  app/orchestration layer spread across multiple hosts/availability zones
  (e.g. Kubernetes across nodes) rather than a single Docker Compose host.
- How to verify: stopping `postgres` and calling `/ready` correctly returns
  `503` with `dependencies.postgres: unavailable` (verifiable the same way
  the app-tier failure was verified in `failure_test.py`), demonstrating the
  app tier fails closed rather than silently, but that the whole stack is
  down while postgres is down.

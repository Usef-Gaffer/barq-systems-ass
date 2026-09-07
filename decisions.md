# Technical decisions

## Decision 1: Fix `config/app.env` values instead of rewriting connection logic
- Choice: Corrected `DATABASE_URL` (port 5433->5432, password suffix d->c) and
  `REDIS_URL` (port 6380->6379) to match the actual `postgres`/`redis` service
  configuration in `docker-compose.yml`.
- Why: `app/server.py`'s `Dependencies` class was already correct (uses
  `DATABASE_URL`/`REDIS_URL` from env, has proper timeouts and readiness
  checks). The bug was purely in the supplied environment values, not the code.
- Alternative: Hardcode connection parameters in `server.py` instead of env vars.
- Trade-off: Keeping env-based config is more correct (12-factor) but means a
  wrong `.env`/`app.env` value fails silently until `/ready` is checked —
  which is exactly what the historical incident's `/ready` design is for.
- Evidence / commit: `fix: correct postgres/redis connection port and password
  mismatch`; confirmed via `curl /ready` returning `dependencies: {postgres:
  ready, redis: ready}`.
- Production improvement: In production, these values would come from a
  secrets manager (e.g. AWS Secrets Manager/Vault), not a plaintext env file,
  with rotation and no plaintext password ever touching disk or git history.

## Decision 2: Bind Flask to `0.0.0.0` instead of `127.0.0.1`
- Choice: Set `APP_HOST=0.0.0.0` for both app instances.
- Why: Each Flask instance runs in its own container; NGINX in a separate
  container must reach it over the Docker network by service name/port.
  `127.0.0.1` inside a container only refers to that container itself.
- Alternative: Run NGINX in the same container/network namespace as the apps
  (e.g. sidecar pattern).
- Trade-off: `0.0.0.0` binding is required for the intended multi-container
  topology, but it does mean the Flask dev server itself has no host-based
  access restriction — mitigated by the app never being reachable from the
  host at all (no published port on app-01/app-02; only NGINX is published).
- Evidence / commit: `fix: bind app to 0.0.0.0, fix app-02 instance id, fix
  healthcheck path`; confirmed via `docker exec nginx ...` routing succeeding
  and `docker compose ps` showing app-01/app-02 with no host port mapping.
- Production improvement: Use a production WSGI server (gunicorn/uwsgi)
  instead of Flask's built-in dev server, which is not intended for
  production traffic regardless of bind address.

## Decision 3: Keep `proxy_next_upstream off` in nginx.conf
- Choice: Left NGINX's automatic upstream failover disabled rather than
  enabling retries to the healthy backend on connection failure.
- Why: The task explicitly asks the failure test to "show continued traffic
  and errors" when one backend is stopped — i.e. partial failure is the
  expected, demonstrable behavior, not something to hide behind automatic
  retries. Log analysis of the historical incident also showed the *previous*
  configuration did retry (19 requests had two upstream addresses), and that
  behavior is inconsistent with `off`, which we treat as a discrepancy
  between the historical incident's config and the current one — documented,
  not silently reconciled.
- Alternative: Enable `proxy_next_upstream error timeout` so a client request
  landing on the dead backend transparently retries the healthy one.
- Trade-off: `off` produces a cleaner, more visible signal in the failure
  test (exactly half the requests fail while one backend is down, per
  `failure_test.py`'s measured 5/10 split) at the cost of a worse client
  experience during a real partial outage.
- Evidence / commit: live test in `failure_test.py` run: "During outage: 5
  succeeded, 5 failed, served by: {'app-02'}".
- Production improvement: In production, enable `proxy_next_upstream` (with a
  bounded number of tries and timeout) so a single backend failure is
  invisible to end users, and rely on separate alerting for the failed
  instance rather than surfacing it as client-visible errors.

## Decision 4: Named PostgreSQL volume, no tmpfs override
- Choice: Mount `postgres-data` (a named Docker volume) at
  `/var/lib/postgresql/data` and removed the `tmpfs` override that was
  present in the starter compose file.
- Why: The starter file mounted the named volume at the wrong path
  (`/var/lib/postgresql/backup`, which Postgres does not use for its data
  directory) while `tmpfs` shadowed the real data directory with in-memory,
  non-persistent storage — meaning every recreation of the postgres container
  silently discarded all data despite the volume "looking" configured.
- Alternative: Bind-mount a host directory instead of a named volume.
- Trade-off: A named volume is more portable across machines/CI runners than
  a host bind-mount path, at the cost of being slightly less transparent to
  inspect from the host filesystem directly (`docker volume inspect` needed).
- Evidence / commit: `fix: correct nginx port mapping, remove exposed db/cache
  ports, fix persistence`; verified live by creating a record, running
  `docker compose up -d --force-recreate app-01 app-02 postgres`, and
  confirming the record still appeared in `/records`.
- Production improvement: Add scheduled automated backups (see `backup.sh`)
  running against the volume on a cron/CI schedule, with off-host retention,
  not just on-demand manual backups.

## Decision 5: Non-root container user, and drop secret file from image
- Choice: Removed `USER root` (which was overriding the earlier
  `useradd`-created `app` user) and removed `COPY config/app.env
  /srv/app.env` from the Dockerfile.
- Why: `USER root` meant the container ran as root despite the image
  explicitly creating a low-privilege user, and copying the secrets file into
  the image baked plaintext database/redis credentials into a durable image
  layer, retrievable via `docker history` or by exporting the image, even
  though the same values are already supplied safely at runtime via
  `env_file` in docker-compose.yml.
- Alternative: Keep `USER root` but drop privileges via `gosu`/`su-exec` at
  entrypoint time instead of a static `USER` directive.
- Trade-off: A static `USER app` is simpler and sufficient here since the app
  needs no privileged operation (no port <1024 binding, no filesystem changes
  outside its own directory); an entrypoint-based drop would only be needed
  if some startup step required root first.
- Evidence / commit: `fix: remove USER root override and secret copy from
  Dockerfile`; confirmed via `docker exec app-01 whoami` -> `app` and
  `docker exec app-02 whoami` -> `app`.
- Production improvement: Add a read-only root filesystem
  (`read_only: true` + explicit `tmpfs` for any writable paths actually
  needed) and drop all Linux capabilities not required, for defense in depth.

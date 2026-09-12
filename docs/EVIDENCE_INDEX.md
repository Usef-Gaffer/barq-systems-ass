# Evidence and submission index

- Repository URL: https://github.com/Usef-Gaffer/barq-systems-ass
- Final commit: `0746a7b` (`fix: align CI with new 8090 default port`)
- Matching CI run: real GitHub Actions run on commit `170c1ad` succeeded
  before the video session; a second real run on commit `0746a7b` (after
  the port/instance/CI fixes made during and after the recording) also
  succeeded — see https://github.com/Usef-Gaffer/barq-systems-ass/actions
  for both.
- Continuous 12-18 minute video URL: *(add the uploaded video URL here)*
- Challenge receipt ID: `e15af5fbf7144b589463f9420d2f575d` (from
  `.assessment/challenge.json`, produced by the first and only run of
  `video_challenge.sh` in this working copy)
- Starting video commit: `bb64c52` (`docs: fill evidence index with real
  commit hashes for completed work`) — the last commit before the live
  recording session began.
- Later documentation-only commits: this file and the corresponding
  `README.md`/`troubleshooting.md` updates were committed after the
  recording, to document the live `video_challenge.sh` diagnosis, the
  8090/app-03 change, and the CI port-mismatch fix that was found and
  corrected immediately after the recorded session — all of it reflects
  work already proven live on camera, not new undisclosed changes.

*(Video timestamps below are marked "to add" — fill these in once the
recording is uploaded and you can note the minute:second for each moment.
No timestamp is invented ahead of having the actual video to check against.)*

## Baseline

| Requirement | Evidence | Commit | Video timestamp |
|---|---|---|---|
| Starter baseline preserved, clean git history | `git log --oneline` shows unmodified GitLab starter history (`02fe9c8` .. `8442da3`) before any technical change | `8442da3` | *(to add)* |
| GitHub repository created, baseline pushed before technical changes | first push created `main` at `8442da3` with no other commits ahead | `8442da3` | *(to add)* |

## Part 1 — Investigation

| Requirement | Evidence | Commit | Video timestamp |
|---|---|---|---|
| Postgres/Redis connection root cause found and fixed | `troubleshooting.md` Entry 1; `curl /ready` -> `dependencies: {postgres: ready, redis: ready}` | `41ffaa6` | *(to add)* |
| App bind address / duplicate instance id / healthcheck path fixed | `troubleshooting.md` Entry 2 | `5a6c375` | *(to add)* |
| Full log analysis, all 10 template questions answered | `log_analysis.md` | `2119794` | *(to add)* |

## Part 2 — Docker, networking and NGINX

| Requirement | Evidence | Commit | Video timestamp |
|---|---|---|---|
| Two, then three, instances behind NGINX, working Postgres/Redis | `docker compose ps` all healthy (6 services); `curl /ready` PASS | `5a6c375`, `bc05635`, `4184f4c` | *(to add)* |
| Only NGINX published on host | `docker compose ps` shows no host ports for postgres/redis/app-01/app-02/app-03; `validate.py` check | `bc05635` | *(to add)* |
| NGINX isolated from PostgreSQL/Redis network | `docker exec nginx nc -zv postgres 5432` -> `bad address` (DNS fails) | `16ce39f` | *(to add)* |
| Named PostgreSQL volume, real persistence | Record created, containers `--force-recreate`d (including postgres), record survived | `bc05635` | *(to add)* |
| Non-root container user, no secrets baked into image | `docker exec app-01 whoami` -> `app`; `security_review.md` findings 1-2 | `e3b980a` | *(to add)* |
| Required endpoints implemented and correct | live `curl` output for `/`, `/health`, `/ready`, `/instance`, `/records`, `/counter` | `5a6c375` (fixes), app logic pre-existing | *(to add)* |
| Third app instance (`app-03`) added, distinct identity proven | `docker compose ps` shows app-03 healthy; 15-request `/instance` sample distributed across all 3 (7/4/4) | `4184f4c` | *(to add)* |
| Public port changed 8080 -> 8090 | `.env.example` updated; `curl http://localhost:8090/` returns 200 | `4184f4c` | *(to add)* |

## Part 3 — Validation, persistence and CI

| Requirement | Evidence | Commit | Video timestamp |
|---|---|---|---|
| `validate.py` with bounded checks, PASS/FAIL, non-zero exit | full run: 8/8 PASS on both 8080 (2-instance) and 8090 (3-instance) configurations | `799e1ca`, `4184f4c` | *(to add)* |
| `failure_test.py`: stop/measure/restore/verify | live run: 5/10 succeeded during outage via app-02, 10/10 after recovery | `bdbd9ce` | *(to add)* |
| `backup.sh`/`restore.sh`, proven restore | live cycle: created record id 4 -> backup -> deleted record -> restored -> record 4 absent, records 1-3 intact (matches backup point) | `11ca7f5` | *(to add)* |
| `.github/workflows/ci.yml`, fails on validation failure | real Actions run on commit `170c1ad`: **success** | `170c1ad` | *(to add)* |
| CI kept green after the 8090 port change | real CI run on commit `4184f4c` failed (connection refused, port mismatch between compose default and validate.py default); diagnosed and fixed; real re-run on commit `0746a7b` **succeeded** | `4184f4c` (broke it), `0746a7b` (fixed it) | *(to add)* |

## Part 4 — Documentation

| Requirement | Evidence | Commit | Video timestamp |
|---|---|---|---|
| `README.md` copyable instructions | `README.md` (final revision reflects 8090/3-instance state) | `19fec75` (initial), current revision post-video | *(to add)* |
| `troubleshooting.md` investigation journal | `troubleshooting.md`, 11 entries (8 pre-video + 3 from the live session) | `2119794` (initial), current revision post-video | *(to add)* |
| `log_analysis.md` | `log_analysis.md` | `2119794` | *(to add)* |
| `decisions.md`, 5+ decisions | `decisions.md`, 5 decisions | `2119794` | *(to add)* |
| `security_review.md`, 8+ findings | `security_review.md`, 8 findings | `2119794` | *(to add)* |
| `AI_USAGE.md` | `AI_USAGE.md` | `2119794` | *(to add)* |
| `architecture.png` | `architecture.png` | `78994f0` | *(to add)* |

## Part 5 — Video demonstration

| Requirement | Evidence | Commit | Video timestamp |
|---|---|---|---|
| `./video_challenge.sh` run for the first time, live | preflight initially failed (nginx had no healthcheck); fixed; second run in the same working copy applied a fault and printed receipt `e15af5fbf7144b589463f9420d2f575d` | `4184f4c` (nginx healthcheck fix) | *(to add)* |
| Diagnose/fix its runtime fault live, no `docker compose down` reset | diagnosed as redis disconnected from `backend` network via `docker network inspect`; fixed with `docker network connect barq-assessment_backend redis`; `/ready` and `/counter` confirmed recovered; `validate.py` 8/8 PASS afterward | none (runtime-only fix); documented in `troubleshooting.md` Entry 10 | *(to add)* |
| Port changed 8080 -> 8090 live, proven | `.env.example` set to `PUBLIC_PORT=8090`; `curl http://localhost:8090/` returned 200 | `4184f4c` | *(to add)* |
| Third app instance added live, all three proven | `app-03` added to `docker-compose.yml` and nginx upstream; 15-request sample showed all three instance IDs | `4184f4c` | *(to add)* |
| Validation rerun after final changes | `PUBLIC_PORT=8090 python3 validate.py` -> 8/8 PASS on the final 3-instance/8090 configuration | `4184f4c` | *(to add)* |

This table is filled with real commit hashes verified against `git log`
in this repository; no hash or outcome above is invented. Video timestamps
remain to be added once the recording is available for review.

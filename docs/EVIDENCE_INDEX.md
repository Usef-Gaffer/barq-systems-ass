# Evidence and submission index

- Repository URL: https://github.com/Usef-Gaffer/barq-systems-ass
- Final commit: *(to be filled after the video-recording session's commits
  are pushed — port 8090 change, third instance, video_challenge.sh fix)*
- Matching CI run: *(link to be added once the final commit's Actions run
  completes; an earlier successful run already exists for commit `170c1ad`,
  see https://github.com/Usef-Gaffer/barq-systems-ass/actions)*
- Continuous 12-18 minute video URL: *(to be added after recording)*
- Challenge receipt ID: *(from `.assessment/challenge.json`, produced the
  first time `video_challenge.sh` is run, live, during the video)*
- Starting video commit: *(the commit checked out at the start of the
  recording — will match the last commit below until the live session)*
- Later documentation-only commits, if any: this index itself, and the
  final `README.md`/`architecture.png` refresh reflecting the 3-instance/
  port-8090 end state, are expected to land as documentation-only commits
  made shortly after the recorded technical changes, since they describe
  work already proven live in the video rather than new technical changes.

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
| Two instances behind NGINX, working Postgres/Redis | `docker compose ps` all healthy; `curl /ready` PASS | `5a6c375`, `bc05635` | *(to add)* |
| Only NGINX published on host | `docker compose ps` shows no host ports for postgres/redis/app-01/app-02; `validate.py` check | `bc05635` | *(to add)* |
| NGINX isolated from PostgreSQL/Redis network | `docker exec nginx nc -zv postgres 5432` -> `bad address` (DNS fails) | `16ce39f` | *(to add)* |
| Named PostgreSQL volume, real persistence | Record created, containers `--force-recreate`d, record survived (`troubleshooting.md` Entry 3) | `bc05635` | *(to add)* |
| Non-root container user, no secrets baked into image | `docker exec app-01 whoami` -> `app`; `security_review.md` findings 1-2 | `e3b980a` | *(to add)* |
| Required endpoints implemented and correct | live `curl` output for `/`, `/health`, `/ready`, `/instance`, `/records`, `/counter` (this session) | `5a6c375` (fixes), app logic pre-existing | *(to add)* |

## Part 3 — Validation, persistence and CI

| Requirement | Evidence | Commit | Video timestamp |
|---|---|---|---|
| `validate.py` with bounded checks, PASS/FAIL, non-zero exit | full run: 8/8 PASS, `RESULT: PASS`, exit 0 | `799e1ca` | *(to add)* |
| `failure_test.py`: stop/measure/restore/verify | live run: 5/10 succeeded during outage via app-02, 10/10 after recovery | `bdbd9ce` | *(to add)* |
| `backup.sh`/`restore.sh`, proven restore | live cycle: created record id 4 -> backup -> deleted record -> restored -> record 4 absent, records 1-3 intact (matches backup point) | `11ca7f5` | *(to add)* |
| `.github/workflows/ci.yml`, fails on validation failure | real Actions run on commit `170c1ad`: **success** | `170c1ad` | *(to add)* |

## Part 4 — Documentation

| Requirement | Evidence | Commit | Video timestamp |
|---|---|---|---|
| `README.md` copyable instructions | `README.md` | `19fec75` | *(to add)* |
| `troubleshooting.md` investigation journal | `troubleshooting.md`, 8 entries | `2119794` | *(to add)* |
| `log_analysis.md` | `log_analysis.md` | `2119794` | *(to add)* |
| `decisions.md`, 5+ decisions | `decisions.md`, 5 decisions | `2119794` | *(to add)* |
| `security_review.md`, 8+ findings | `security_review.md`, 8 findings | `2119794` | *(to add)* |
| `AI_USAGE.md` | `AI_USAGE.md` | `2119794` | *(to add)* |
| `architecture.png` | `architecture.png` | `78994f0` | *(to add)* |

## Part 5 — Video demonstration (pending)

| Requirement | Evidence | Commit | Video timestamp |
|---|---|---|---|
| `./video_challenge.sh` run for the first time, live | *(pending — first run must happen during recording)* | *(pending)* | *(to add)* |
| Diagnose/fix its runtime fault live, no `docker compose down` reset | *(pending)* | *(pending)* | *(to add)* |
| Port changed 8080 -> 8090 live, proven | *(pending)* | *(pending)* | *(to add)* |
| Third app instance added live, all three proven | *(pending)* | *(pending)* | *(to add)* |
| Validation rerun after final changes | *(pending)* | *(pending)* | *(to add)* |

This table will be completed with real commit hashes and video timestamps
immediately after the recording session, once those commits exist — no
timestamp or hash above is invented ahead of the actual recording.

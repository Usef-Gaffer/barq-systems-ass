# AI usage disclosure

AI (Claude, via Claude Code) was used throughout this task as a technical
assistant. The student executed every command personally in their own
terminal and reviewed every output before proceeding; the AI never had
direct execution access to the environment and made no unverified claims of
success (each "PASS" in `troubleshooting.md`/`log_analysis.md` corresponds to
real command output reviewed at the time).

- Tool/model: Claude (Claude Code), Anthropic.
- Purpose: (1) guiding the investigation methodology (what to check and in
  what order); (2) proposing specific diagnoses for config mismatches found
  by comparing `docker-compose.yml`, `config/app.env`, `nginx/nginx.conf`,
  and `app/server.py` against each other and against the task brief; (3)
  drafting shell/Python snippets for log analysis (`log_analysis.md`) and
  for the validation/failure-test/backup/restore scripts; (4) drafting the
  documentation files (`decisions.md`, `troubleshooting.md`,
  `security_review.md`, this file) based on real command output supplied by
  the student during the session.
- Files or decisions affected: `config/app.env`, `docker-compose.yml`,
  `nginx/nginx.conf`, `Dockerfile`, `backup.sh`, `restore.sh`, `validate.py`,
  `failure_test.py`, `.github/workflows/ci.yml`, `log_analysis.md`,
  `troubleshooting.md`, `decisions.md`, `security_review.md`, this file.
- What you changed or rejected: the AI's first draft of `validate.py`'s host
  port check was accepted, run, and found to produce a false positive
  (flagged `app-01` as violating "no host ports" when it was only `EXPOSE`d,
  not published — `PublishedPort: 0`). This was caught by actually running
  the script rather than trusting the draft, and the AI's proposed fix
  (filter on `PublishedPort` truthiness) was verified by re-running the
  script before being accepted. See `troubleshooting.md` Entry 8.
- How you independently verified it: every fix proposed was applied by the
  student, then verified against real command output before being treated
  as done — e.g. `curl /ready`, `docker exec ... whoami`, `docker compose
  ps`, the full `validate.py`/`failure_test.py` runs, the live backup/restore
  cycle (create record -> backup -> delete record -> restore -> confirm
  record reappears), and a real GitHub Actions CI run (see evidence index).
  No fix was recorded as proven in `troubleshooting.md` without matching
  command output from this session.
- Related commit: all commits in this repository's history from
  `fix: correct postgres/redis connection port and password mismatch`
  onward were made with AI assistance as described above; the exact
  starting baseline (commits `02fe9c8` through `8442da3`) is the unmodified
  GitLab starter release, authored before this task began.

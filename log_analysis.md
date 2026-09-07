# Log Analysis

All findings below are derived from the original files in `logs/` (unmodified,
verified via `git status`/`git diff` showing no changes to `logs/`).
Correlation key across all three files: `request_id`.

## 1. Coverage, valid/malformed/duplicate lines per file

| File               | Total lines | Malformed | Duplicate lines | Valid unique |
|--------------------|-------------|-----------|------------------|--------------|
| access.log         | 726         | 1 (line 311, truncated JSON) | 5 (see below) | 720 |
| application.log    | 730         | 1 (line 401, truncated JSON) | 2 (see below) | 727 |
| error.log          | 68          | 0 (plain text, not JSON)     | 0              | 68  |

Time interval covered: `2026-08-20T11:00:00Z` to `2026-08-20T11:30:00Z` (30 minutes),
per first/last timestamps in access.log and the final "log collector rotated stream"
notice in error.log.

Commands:
```
wc -l logs/access.log logs/error.log logs/application.log

python3 -c "import json
bad=[]
with open('logs/access.log') as f:
    for i,l in enumerate(f,1):
        try: json.loads(l)
        except Exception: bad.append(i)
print(bad)"
# -> [311], line: {"timestamp":"2026-08-20T11:12:48Z","request_id": (truncated)

sort logs/access.log | uniq -d
# 5 lines, each an exact duplicate of an earlier line (e.g. request_id lab-000121
# appears twice with identical timestamp/status/upstream)

sort logs/application.log | uniq -d
# 2 lines duplicated (lab-000181, lab-000421), same pattern
```

Malformed lines were excluded from all counts (not guessed at). Duplicate lines
were collapsed to one occurrence per unique line before counting distinct
client requests (see Q2).

## 2. Distinct client requests and deduplication

`access.log` has 726 raw lines. After removing 1 malformed line and collapsing
5 exact-duplicate lines to single occurrences, there are **720 distinct client
requests** recorded in access.log for this window.

Deduplication method: exact full-line duplicates (same request_id, same
timestamp, same status, same upstream) are the same event logged twice, not
two different requests, so they were counted once. Separately, 19 of those
lines carry a comma-separated `upstream` field (e.g.
`"172.23.0.12:8080, 172.23.0.11:8080"`), meaning NGINX retried that single
client request against a second upstream after the first attempt. These are
still one request each, not two, regardless of how many upstream addresses
are listed in the field:
```
grep -oP '(?<="upstream":")[^"]*' logs/access.log | sort | uniq -c
#  365 172.23.0.11:8080
#  341 172.23.0.12:8080
#   19 172.23.0.12:8080, 172.23.0.11:8080
```
Note: the current `nginx.conf` sets `proxy_next_upstream off`, so this retry
behavior does not occur under the fixed configuration; it is a property of
this historical incident's logs only, not of the current environment.

## 3. Final client status counts and error rate

```
python3 -c "
import json
from collections import Counter
status=Counter()
with open('logs/access.log') as f:
    for line in f:
        try: status[json.loads(line)['status']] += 1
        except Exception: pass
print(dict(sorted(status.items())))
"
```
Result (denominator = 725 successfully-parsed lines, malformed line excluded):
```
{200: 620, 404: 10, 502: 40, 503: 47, 504: 8}
```
Error rate (status >= 400) = (10+40+47+8) / 725 = **14.48%**.

## 4. Which paths, time windows and backends account for the failures?

- `502`/`connect refused` errors (40 total, matching most of the 59 in
  error.log): concentrated in `11:05:02`-`11:09:57`, all against
  `172.23.0.12:8080`, across every path (`/`, `/health`, `/ready`, `/records`,
  `/counter`, `/instance`) — a single-instance outage, not path-specific.
- `504`/timeout errors (8 total): concentrated in `11:25:14`-`11:26:47`,
  alternating between `172.23.0.11` and `172.23.0.12`, and **exclusively**
  on `/records` — a dependency-level (PostgreSQL) slowness pattern, not
  instance-specific.
- `404` (10 total): scattered `GET /missing` requests, unrelated to backend
  health — client-side/expected 404s, not part of either incident.
- `503` (47): application-level `*_unavailable` responses logged when
  `/ready`, `/records`, or `/counter` could not reach postgres/redis (visible
  correlated in `application.log` as `event: dependency_error`).

## 5. Median and p95 client latency

```
python3 -c "
import json, statistics
lat=[]
with open('logs/application.log') as f:
    for line in f:
        try:
            d=json.loads(line)
            if 'duration_ms' in d: lat.append(d['duration_ms'])
        except Exception: pass
lat.sort()
print('count:', len(lat))
print('median (ms):', statistics.median(lat))
print('p95 (ms):', lat[int(len(lat)*0.95)])
"
```
Result: count=682 valid samples, **median = 56.5 ms**, **p95 = 2025.0 ms**
(nearest-rank method: sorted ascending, index = floor(0.95 * n)). The large
gap between median and p95 is explained by the 11:25-11:26 timeout window,
where a handful of `/records` calls took the full 2s `proxy_read_timeout`
before failing.

## 6. Which requests retried upstream? How many succeeded after retrying?

19 requests in access.log show two upstream addresses in the `upstream`
field (see Q2), meaning NGINX attempted a second backend after the first
attempt for that single client request. All 19 completed with a final
`status: 200`, i.e. the retry succeeded in every observed case in this
historical log. This behavior is not present in the current `nginx.conf`
(`proxy_next_upstream off`), so it cannot be reproduced live with the fixed
configuration — documented as a discrepancy between the historical config
and the current one, not silently reconciled.

## 7. Incident timeline (access + error + application evidence)

| Time (UTC)  | Source(s)                    | Event                                             |
|-------------|-------------------------------|----------------------------------------------------|
| 11:00:00    | access, application            | Normal traffic begins, alternating app-01/app-02   |
| 11:05:00    | access (lab-000121)            | Last healthy request before outage: 200, app-01 (172.23.0.11) |
| 11:05:02    | error, access (lab-000122)     | First failure: connect() refused, 172.23.0.12, /health, 502 |
| 11:05:02-11:09:57 | error (59 lines), access (502s) | Sustained outage of 172.23.0.12, ~5s cadence, all paths |
| 11:10:00+   | access                         | Traffic normal again (172.23.0.12 back, implied by absence of further refused errors until 11:25) |
| 11:25:14    | error, access                  | First timeout: 172.23.0.12, /records, 504          |
| 11:25:14-11:26:47 | error (8 lines)          | Alternating timeouts on /records, both instances    |
| 11:30:00    | error                          | "log collector rotated stream" — end of captured window |

## 8. One correlated failed request and one successful request

**Successful** (immediately before the outage):
```
access.log:      {"request_id":"lab-000121","status":200,"upstream":"172.23.0.11:8080","path":"/","request_time":0.055}
application.log: {"request_id":"lab-000121","instance_id":"app-01","status":200,"duration_ms":55.0}
```

**Failed** (first failure of the outage, one request later):
```
access.log: {"request_id":"lab-000122","status":502,"upstream":"172.23.0.12:8080","path":"/health","request_time":0.003}
error.log:  connect() failed (111: Connection refused) ... request_id=lab-000122 ... upstream: "http://172.23.0.12:8080/health"
```
Note: `lab-000122` has no corresponding line in `application.log` — the
request never reached the Flask app (connection was refused at the TCP
level), which is itself evidence the failure was infrastructure-level
(container down), not an application bug.

## 9. Proxy/connectivity errors vs. dependency/application errors — what proves it?

- **Proxy/connectivity** (11:05-11:09, `connect() failed... Connection refused`):
  proven by (a) the error occurring in NGINX's error.log before reaching the
  app (no matching application.log entry for those request_ids), and (b) the
  error type `Connection refused`, which only occurs when nothing is
  listening on the target port/IP — consistent with a stopped container.
- **Dependency/application** (11:25-11:26, `upstream timed out`, plus the 47
  `503` responses): proven by matching `application.log` entries with
  `event: dependency_error` and `dependency: postgres`/`redis`, meaning the
  request *did* reach the Flask app, which then failed while calling
  PostgreSQL/Redis — the failure is downstream of the app, not the network
  path to it.

## 10. What do the logs not prove? What would you check next in a live environment?

The logs do not prove *why* `172.23.0.12` stopped responding (crash, OOM
kill, manual stop, restart) — only that it was unreachable. They also do
not prove *why* PostgreSQL was slow during 11:25-11:26 (lock contention,
resource exhaustion, connection pool exhaustion) — only that queries from
both app instances timed out during that window. In a live environment,
the next steps would be: `docker inspect`/`docker events` around 11:05 for
the affected container's exit reason and restart count, and PostgreSQL's
own logs (`pg_stat_activity`, slow query log) around 11:25 to identify the
specific query or lock behind the timeout.

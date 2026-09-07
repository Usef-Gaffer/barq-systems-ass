#!/usr/bin/env python3
"""Bounded validation checks for the BARQ assessment environment."""
import json
import subprocess
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8080"
TIMEOUT = 3
RETRIES = 10
RETRY_DELAY = 2

failures = []


def check(name, fn):
    try:
        fn()
        print(f"PASS: {name}")
    except Exception as exc:
        print(f"FAIL: {name} -> {exc}")
        failures.append(name)


def get_json(path, timeout=TIMEOUT):
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=timeout) as resp:
        return resp.status, json.loads(resp.read())


def wait_for(path, expect_status=200, retries=RETRIES):
    last_exc = None
    for _ in range(retries):
        try:
            status, body = get_json(path)
            if status == expect_status:
                return status, body
            last_exc = Exception(f"got status {status}")
        except Exception as exc:
            last_exc = exc
        time.sleep(RETRY_DELAY)
    raise last_exc or Exception("unreachable")


def check_public_access():
    status, _ = wait_for("/")
    assert status == 200


def check_health():
    status, body = get_json("/health")
    assert status == 200
    assert body.get("status") == "alive"


def check_ready():
    status, body = wait_for("/ready")
    assert status == 200
    deps = body.get("dependencies", {})
    assert deps.get("postgres") == "ready"
    assert deps.get("redis") == "ready"


def check_records():
    status, body = get_json("/records")
    assert status == 200
    assert isinstance(body.get("records"), list)


def check_counter():
    status, body = get_json("/counter")
    assert status == 200
    assert isinstance(body.get("counter"), int)


def check_both_backends_serve():
    seen = set()
    for _ in range(20):
        _, body = get_json("/instance")
        seen.add(body.get("instance_id"))
    assert "app-01" in seen and "app-02" in seen, f"only saw: {seen}"


def check_network_isolation():
    result = subprocess.run(
        ["docker", "exec", "nginx", "sh", "-c", "nc -zv -w2 postgres 5432"],
        capture_output=True, text=True
    )
    assert result.returncode != 0, "nginx should NOT reach postgres directly"


def check_no_prohibited_host_ports():
    result = subprocess.run(
        ["docker", "compose", "ps", "--format", "json"],
        capture_output=True, text=True, check=True
    )
    for line in result.stdout.strip().splitlines():
        svc = json.loads(line)
        name = svc.get("Service", "")
        ports = svc.get("Publishers") or []
        if name in ("postgres", "redis", "app-01", "app-02"):
            published = [p for p in ports if p.get("PublishedPort", 0)]
            assert not published, f"{name} must not publish host ports, found: {published}"


def main():
    check("public NGINX access (/)", check_public_access)
    check("/health liveness", check_health)
    check("/ready dependencies", check_ready)
    check("/records", check_records)
    check("/counter", check_counter)
    check("both backends serve via /instance", check_both_backends_serve)
    check("network isolation (nginx -> postgres blocked)", check_network_isolation)
    check("no prohibited host ports", check_no_prohibited_host_ports)

    print()
    if failures:
        print(f"RESULT: FAIL ({len(failures)} check(s) failed: {', '.join(failures)})")
        sys.exit(1)
    print("RESULT: PASS (all checks passed)")
    sys.exit(0)


if __name__ == "__main__":
    main()

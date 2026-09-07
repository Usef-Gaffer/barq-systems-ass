#!/usr/bin/env python3
"""Stop one backend, measure traffic during the outage, restore it, verify recovery."""
import json
import subprocess
import sys
import time
import urllib.request

BASE_URL = "http://localhost:8080"
TARGET_CONTAINER = "app-01"
REQUESTS_DURING_FAILURE = 10
REQUESTS_AFTER_RECOVERY = 10
RECOVERY_WAIT_SECONDS = 8


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True)


def probe(path="/instance"):
    try:
        with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=3) as resp:
            body = json.loads(resp.read())
            return resp.status, body.get("instance_id")
    except Exception as exc:
        return None, str(exc)


def main():
    print(f"=== Failure test: stopping {TARGET_CONTAINER} ===")

    print("\n[1] Baseline check (system healthy before failure)")
    status, instance = probe()
    if status != 200:
        print(f"FAIL: baseline probe failed before test started: {instance}")
        sys.exit(1)
    print(f"PASS: baseline OK, served by {instance}")

    print(f"\n[2] Stopping {TARGET_CONTAINER}")
    run(["docker", "stop", TARGET_CONTAINER])
    time.sleep(2)

    print(f"\n[3] Sending {REQUESTS_DURING_FAILURE} requests during outage")
    ok, errors = 0, 0
    served_by = set()
    for _ in range(REQUESTS_DURING_FAILURE):
        status, instance = probe()
        if status == 200:
            ok += 1
            served_by.add(instance)
        else:
            errors += 1
        time.sleep(0.3)
    print(f"During outage: {ok} succeeded, {errors} failed, served by: {served_by}")

    if ok == 0:
        print("FAIL: no requests succeeded during outage; other backend did not take over")
        run(["docker", "start", TARGET_CONTAINER])
        sys.exit(1)
    print("PASS: service continued (with expected errors) while one backend was down")

    print(f"\n[4] Restoring {TARGET_CONTAINER}")
    run(["docker", "start", TARGET_CONTAINER])
    time.sleep(RECOVERY_WAIT_SECONDS)

    print(f"\n[5] Sending {REQUESTS_AFTER_RECOVERY} requests after recovery")
    recovered_seen = set()
    recovery_ok = 0
    for _ in range(REQUESTS_AFTER_RECOVERY):
        status, instance = probe()
        if status == 200:
            recovery_ok += 1
            recovered_seen.add(instance)
        time.sleep(0.3)

    print(f"After recovery: {recovery_ok}/{REQUESTS_AFTER_RECOVERY} succeeded, served by: {recovered_seen}")

    if TARGET_CONTAINER not in recovered_seen:
        print(f"FAIL: {TARGET_CONTAINER} did not resume serving requests after restart")
        sys.exit(1)
    if recovery_ok != REQUESTS_AFTER_RECOVERY:
        print("FAIL: not all post-recovery requests succeeded")
        sys.exit(1)

    print(f"PASS: {TARGET_CONTAINER} recovered and is serving requests again")
    print("\nRESULT: PASS")
    sys.exit(0)


if __name__ == "__main__":
    main()

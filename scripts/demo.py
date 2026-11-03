"""End-to-end demo.

Generates samples (if missing), uploads each through the API, waits for the
verdict, and prints a PASS/FAIL table against expected verdicts.

The crash-me sample is expected to dead-letter rather than reach SCANNED, so it
is reported separately with the DLQ depth.
"""
import base64
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))

import _client  # noqa: E402
from make_samples import SAMPLES, main as make_samples  # noqa: E402

ENDPOINT = _client.ENDPOINT


def _dlq_depth():
    """Best-effort DLQ message count via awslocal, if available."""
    try:
        url = subprocess.run(
            ["terraform", f"-chdir={_client.TERRAFORM_DIR}", "output", "-raw", "scan_dlq_url"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        out = subprocess.run(
            ["awslocal", "sqs", "get-queue-attributes",
             "--queue-url", url,
             "--attribute-names", "ApproximateNumberOfMessages"],
            capture_output=True, text=True, check=True,
        )
        import json
        attrs = json.loads(out.stdout)["Attributes"]
        return attrs.get("ApproximateNumberOfMessages", "?")
    except Exception:  # noqa: BLE001 - best effort only
        return "?"


def main():
    # Also drop the samples to disk (nice for manual inspection), but the demo
    # uploads bytes built in memory so antivirus quarantining the on-disk EICAR
    # file cannot break the run.
    try:
        make_samples()
    except OSError:
        pass  # e.g. AV removed a sample mid-write; in-memory bytes still work.

    base_url = _client.api_base_url()
    print(f"API: {base_url}\n")

    rows = []
    crash_file_id = None

    for name, builder, expected in SAMPLES:
        data = builder()
        b64 = base64.b64encode(data).decode()
        code, body = _client.upload(base_url, name, b64)
        if code != 202:
            rows.append((name, expected, f"upload failed ({code})", "FAIL"))
            continue
        file_id = body["file_id"]

        if expected == "DLQ":
            crash_file_id = file_id
            continue

        record = _client.wait_for_scanned(base_url, file_id)
        actual = record.get("verdict", record.get("scan_state", "?"))
        result = "PASS" if actual == expected else "FAIL"
        score = record.get("risk_score", "?")
        rows.append((name, expected, f"{actual} ({score})", result))

    # Print the table.
    print(f"{'FILE':<20} {'EXPECTED':<12} {'ACTUAL':<22} RESULT")
    print("-" * 66)
    for name, expected, actual, result in rows:
        print(f"{name:<20} {expected:<12} {actual:<22} {result}")

    if crash_file_id:
        print("\ncrash-me.txt uploaded; it fails on purpose and dead-letters.")
        print(f"  DLQ approx depth: {_dlq_depth()}")

    failed = [r for r in rows if r[3] == "FAIL"]
    print()
    if failed:
        print(f"{len(failed)} sample(s) did not match expected verdicts.")
        sys.exit(1)
    print("All samples matched expected verdicts.")


if __name__ == "__main__":
    main()

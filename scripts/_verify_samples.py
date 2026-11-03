"""Dev-only: classify generated samples with the real scanner lib (no AWS).

Confirms the demo's expected verdicts match the detection logic before any
Docker/LocalStack run. Not part of the shipped flow.

Builds each sample's bytes in memory (via its builder) rather than reading from
disk, so antivirus quarantining the on-disk EICAR file cannot break this check.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from common.scanner_lib import classify, run_all  # noqa: E402
from make_samples import SAMPLES  # noqa: E402

ok = True
for name, builder, expected in SAMPLES:
    data = builder()
    if expected == "DLQ":
        print(f"   {name:<20} expect={expected:<11} -> intentional crash (DLQ)")
        continue
    got = classify(run_all(name, data)).verdict
    mark = "OK " if got == expected else "XX "
    if got != expected:
        ok = False
    print(f"{mark}{name:<20} expect={expected:<11} got={got}")

sys.exit(0 if ok else 1)

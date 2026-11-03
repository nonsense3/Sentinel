"""Environment-driven resource names and configuration.

Every Lambda and script reads resource names from the environment so Terraform
is the single source of truth. Defaults match the Terraform resource names so
local scripts work without extra wiring.
"""
import os

# Resource names (overridable via Lambda env vars set in Terraform).
INCOMING_BUCKET = os.environ.get("INCOMING_BUCKET", "sentinel-incoming")
CLEAN_BUCKET = os.environ.get("CLEAN_BUCKET", "sentinel-clean")
QUARANTINE_BUCKET = os.environ.get("QUARANTINE_BUCKET", "sentinel-quarantine")

VERDICTS_TABLE = os.environ.get("VERDICTS_TABLE", "sentinel-verdicts")
KNOWN_HASHES_TABLE = os.environ.get("KNOWN_HASHES_TABLE", "sentinel-known-hashes")

ALERTS_QUEUE_URL = os.environ.get("ALERTS_QUEUE_URL", "")

# Scoring thresholds. A file at or above MALICIOUS is malicious; at or above
# SUSPICIOUS (but below MALICIOUS) is suspicious; below SUSPICIOUS is clean.
SCORE_MALICIOUS = int(os.environ.get("SCORE_MALICIOUS", "80"))
SCORE_SUSPICIOUS = int(os.environ.get("SCORE_SUSPICIOUS", "30"))

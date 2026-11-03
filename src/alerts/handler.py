"""Alerts Lambda. Triggered by messages on the alerts queue.

Logs a clearly marked line per malicious file so the demo can grep for it:
    docker compose logs localstack | grep "SECURITY ALERT"
"""
import json


def handler(event, _context):
    for record in event.get("Records", []):
        body = record.get("body") or "{}"
        try:
            alert = json.loads(body)
        except ValueError:
            alert = {"raw": body}

        print(
            "SECURITY ALERT "
            f"file_id={alert.get('file_id')} "
            f"filename={alert.get('filename')!r} "
            f"verdict={alert.get('verdict')} "
            f"risk_score={alert.get('risk_score')} "
            f"sha256={alert.get('sha256')} "
            f"reasons={alert.get('reasons')}"
        )
    return {"ok": True}

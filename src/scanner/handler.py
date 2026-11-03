"""Scanner Lambda. Triggered by SQS messages carrying S3 put events.

Flow per record:
  1. Parse the S3 event -> bucket, key, file_id, filename.
  2. Load the verdict row. If already SCANNED, skip (idempotency).
  3. Download the object from sentinel-incoming.
  4. Compute SHA-256.
  5. Hash cache lookup in sentinel-known-hashes. On hit, reuse the verdict
     (cache_hit=true) and skip the checks.
  6. On miss, run all detection checks and classify.
  7. Move the object to clean or quarantine (copy + delete).
  8. Write the final verdict row (SCANNED) and cache the hash verdict.
  9. If malicious, publish to the alerts queue.

A message for a key named "crash-me*" raises, so the demo can show retries +
DLQ. Raising propagates the failure to SQS, which retries then dead-letters.
"""
import hashlib
import json
import urllib.parse
from datetime import datetime, timezone

from common import aws, config
from common.scanner_lib import classify, run_all


def _now():
    return datetime.now(timezone.utc).isoformat()


def _parse_records(event):
    """Yield (bucket, key) from SQS-wrapped S3 notifications."""
    for sqs_record in event.get("Records", []):
        body = sqs_record.get("body")
        if not body:
            continue
        s3_event = json.loads(body)
        for s3_record in s3_event.get("Records", []):
            s3 = s3_record.get("s3", {})
            bucket = s3.get("bucket", {}).get("name")
            raw_key = s3.get("object", {}).get("key", "")
            key = urllib.parse.unquote_plus(raw_key)
            if bucket and key:
                yield bucket, key


def _split_key(key):
    """'{file_id}/{filename}' -> (file_id, filename)."""
    file_id, _, filename = key.partition("/")
    return file_id, filename


def _reasons_to_ddb(reasons):
    return {"L": [{"S": r} for r in reasons]}


def _store_verdict(ddb, file_id, filename, verdict, sha256, size_bytes,
                   stored_at, cache_hit, uploaded_at):
    item = {
        "file_id": {"S": file_id},
        "filename": {"S": filename},
        "scan_state": {"S": "SCANNED"},
        "verdict": {"S": verdict.verdict},
        "risk_score": {"N": str(verdict.risk_score)},
        "reasons": _reasons_to_ddb(verdict.reasons),
        "sha256": {"S": sha256},
        "size_bytes": {"N": str(size_bytes)},
        "stored_at": {"S": stored_at},
        "cache_hit": {"BOOL": cache_hit},
        "scanned_at": {"S": _now()},
    }
    if uploaded_at:
        item["uploaded_at"] = {"S": uploaded_at}
    ddb.put_item(TableName=config.VERDICTS_TABLE, Item=item)


def _cache_lookup(ddb, sha256):
    resp = ddb.get_item(
        TableName=config.KNOWN_HASHES_TABLE,
        Key={"sha256": {"S": sha256}},
    )
    return resp.get("Item")


def _cache_store(ddb, sha256, verdict, source="cache"):
    ddb.put_item(
        TableName=config.KNOWN_HASHES_TABLE,
        Item={
            "sha256": {"S": sha256},
            "verdict": {"S": verdict.verdict},
            "risk_score": {"N": str(verdict.risk_score)},
            "reasons": _reasons_to_ddb(verdict.reasons),
            "source": {"S": source},
        },
    )


def _move_object(s3, src_bucket, key, dest_bucket, data):
    s3.put_object(Bucket=dest_bucket, Key=key, Body=data)
    s3.delete_object(Bucket=src_bucket, Key=key)


def _alert(sqs, file_id, filename, verdict, sha256):
    if not config.ALERTS_QUEUE_URL:
        return
    sqs.send_message(
        QueueUrl=config.ALERTS_QUEUE_URL,
        MessageBody=json.dumps({
            "file_id": file_id,
            "filename": filename,
            "verdict": verdict.verdict,
            "risk_score": verdict.risk_score,
            "reasons": verdict.reasons,
            "sha256": sha256,
        }),
    )


def _verdict_from_cache(item):
    from common.scanner_lib import Verdict
    reasons = [v["S"] for v in item.get("reasons", {}).get("L", [])]
    return Verdict(
        verdict=item["verdict"]["S"],
        risk_score=int(item["risk_score"]["N"]),
        reasons=reasons,
    )


def _process(bucket, key):
    file_id, filename = _split_key(key)

    # Demo hook: deliberately fail so the message retries then dead-letters.
    if filename.lower().startswith("crash-me"):
        raise RuntimeError(f"intentional failure for DLQ demo: {key}")

    ddb = aws.client("dynamodb")
    s3 = aws.client("s3")
    sqs = aws.client("sqs")

    # Idempotency: skip if already scanned.
    existing = ddb.get_item(
        TableName=config.VERDICTS_TABLE,
        Key={"file_id": {"S": file_id}},
    ).get("Item")
    if existing and existing.get("scan_state", {}).get("S") == "SCANNED":
        print(f"[scanner] {file_id} already SCANNED, skipping")
        return
    uploaded_at = existing.get("uploaded_at", {}).get("S") if existing else None

    obj = s3.get_object(Bucket=bucket, Key=key)
    data = obj["Body"].read()
    size_bytes = len(data)
    sha256 = hashlib.sha256(data).hexdigest()

    cached = _cache_lookup(ddb, sha256)
    if cached:
        verdict = _verdict_from_cache(cached)
        cache_hit = True
        print(f"[scanner] cache hit for {sha256[:12]} -> {verdict.verdict}")
    else:
        findings = run_all(filename, data)
        verdict = classify(findings)
        cache_hit = False
        _cache_store(ddb, sha256, verdict, source="cache")

    dest_bucket = config.QUARANTINE_BUCKET if verdict.quarantine else config.CLEAN_BUCKET
    _move_object(s3, bucket, key, dest_bucket, data)
    stored_at = f"s3://{dest_bucket}/{key}"

    _store_verdict(ddb, file_id, filename, verdict, sha256, size_bytes,
                   stored_at, cache_hit, uploaded_at)

    if verdict.verdict == "malicious":
        _alert(sqs, file_id, filename, verdict, sha256)

    print(f"[scanner] {file_id} -> {verdict.verdict} ({verdict.risk_score}) "
          f"cache_hit={cache_hit} stored_at={stored_at}")


def handler(event, _context):
    # Any exception propagates so SQS can retry and eventually dead-letter.
    for bucket, key in _parse_records(event):
        _process(bucket, key)
    return {"ok": True}

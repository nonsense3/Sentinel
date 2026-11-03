"""POST /upload

Body: {"filename": "a.pdf", "content_b64": "<base64>"}
  1. Decode and validate.
  2. Store object at sentinel-incoming/{file_id}/{filename}.
  3. Write a PENDING verdict row.
Response: 202 {"file_id": "..."}

The S3 put triggers the scan pipeline via bucket notification -> SQS.
"""
import base64
import binascii
import json
import uuid
from datetime import datetime, timezone

from common import aws, config


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _now():
    return datetime.now(timezone.utc).isoformat()


def handler(event, _context):
    try:
        raw = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode("utf-8")
        payload = json.loads(raw)
    except (ValueError, binascii.Error):
        return _response(400, {"error": "invalid JSON body"})

    filename = payload.get("filename")
    content_b64 = payload.get("content_b64")
    if not filename or not isinstance(filename, str):
        return _response(400, {"error": "filename is required"})
    if not content_b64 or not isinstance(content_b64, str):
        return _response(400, {"error": "content_b64 is required"})

    try:
        data = base64.b64decode(content_b64, validate=True)
    except (binascii.Error, ValueError):
        return _response(400, {"error": "content_b64 is not valid base64"})

    file_id = str(uuid.uuid4())
    key = f"{file_id}/{filename}"

    s3 = aws.client("s3")
    s3.put_object(Bucket=config.INCOMING_BUCKET, Key=key, Body=data)

    ddb = aws.client("dynamodb")
    ddb.put_item(
        TableName=config.VERDICTS_TABLE,
        Item={
            "file_id": {"S": file_id},
            "filename": {"S": filename},
            "scan_state": {"S": "PENDING"},
            "size_bytes": {"N": str(len(data))},
            "uploaded_at": {"S": _now()},
            "cache_hit": {"BOOL": False},
        },
    )

    return _response(202, {"file_id": file_id})

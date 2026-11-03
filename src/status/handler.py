"""GET /files/{id}

Returns the current verdict record for a file_id, or 404 if unknown.
"""
import json
from decimal import Decimal

from common import aws, config


def _response(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=_json_default),
    }


def _json_default(o):
    if isinstance(o, Decimal):
        return int(o) if o == o.to_integral_value() else float(o)
    raise TypeError(f"not serializable: {type(o)}")


def _from_ddb(item):
    """Flatten a DynamoDB item (low-level API) into a plain dict."""
    out = {}
    for key, val in item.items():
        (type_tag, raw), = val.items()
        if type_tag == "S":
            out[key] = raw
        elif type_tag == "N":
            out[key] = int(raw) if raw.isdigit() else float(raw)
        elif type_tag == "BOOL":
            out[key] = raw
        elif type_tag == "L":
            out[key] = [list(v.values())[0] for v in raw]
        else:
            out[key] = raw
    return out


def handler(event, _context):
    params = event.get("pathParameters") or {}
    file_id = params.get("id")
    if not file_id:
        return _response(400, {"error": "missing file id"})

    ddb = aws.client("dynamodb")
    resp = ddb.get_item(
        TableName=config.VERDICTS_TABLE,
        Key={"file_id": {"S": file_id}},
    )
    item = resp.get("Item")
    if not item:
        return _response(404, {"error": "file not found", "file_id": file_id})

    return _response(200, _from_ddb(item))

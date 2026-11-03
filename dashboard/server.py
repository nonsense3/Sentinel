"""Tiny local dashboard server for Sentinel.

Serves the static dashboard and proxies a few calls to the deployed LocalStack
API so the browser never hits CORS. Nothing here changes the deployed stack; it
reads the live resources the Terraform created.

Run:  python dashboard/server.py
Then open http://localhost:8080

Endpoints (same-origin, consumed by index.html):
  POST /api/upload        -> forwards to the API Gateway upload route
  GET  /api/files         -> lists all verdict rows (scans the DynamoDB table)
  GET  /api/files/{id}    -> forwards to the API Gateway status route
"""
import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(__file__)


def _load_dotenv():
    """Load KEY=VALUE pairs from the repo .env into os.environ (no deps)."""
    env_path = os.path.join(HERE, "..", ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            # Don't override anything already set in the real environment.
            if key and key not in os.environ:
                os.environ[key] = value


# LocalStack needs fake creds present; load them before importing boto3 code.
_load_dotenv()
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")
# Pin the region to where Terraform created the resources. This must override
# any real AWS_DEFAULT_REGION set on the machine (e.g. ap-south-1), otherwise
# boto3 looks for the tables in the wrong region and they appear non-existent.
os.environ["AWS_DEFAULT_REGION"] = os.environ.get("TF_REGION", "us-east-1")

sys.path.insert(0, os.path.join(HERE, "..", "src"))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

from common import aws, config  # noqa: E402
import _client  # noqa: E402  (resolves the API base URL from terraform output)

PORT = int(os.environ.get("DASHBOARD_PORT", "8080"))

# Resolve the live API base URL once at startup.
try:
    API_BASE = _client.api_base_url()
except Exception as exc:  # noqa: BLE001
    API_BASE = None
    print(f"[dashboard] warning: could not resolve API URL yet ({exc})")


def _ddb_to_plain(item):
    out = {}
    for key, val in item.items():
        (tag, raw), = val.items()
        if tag == "S":
            out[key] = raw
        elif tag == "N":
            out[key] = int(raw) if raw.isdigit() else float(raw)
        elif tag == "BOOL":
            out[key] = raw
        elif tag == "L":
            out[key] = [list(v.values())[0] for v in raw]
        else:
            out[key] = raw
    return out


def list_files():
    """Scan the verdicts table directly and return rows newest-first."""
    ddb = aws.client("dynamodb")
    resp = ddb.scan(TableName=config.VERDICTS_TABLE)
    rows = [_ddb_to_plain(i) for i in resp.get("Items", [])]
    rows.sort(key=lambda r: r.get("uploaded_at", ""), reverse=True)
    return rows


def clear_files():
    """Delete all verdict rows and remove the stored objects from every bucket.

    This is a demo convenience ("Clear records" in the dashboard). It empties the
    verdicts table and the clean/quarantine/incoming buckets so the console starts
    fresh. The known-hashes cache is left intact so idempotency still demonstrates.
    """
    ddb = aws.client("dynamodb")
    s3 = aws.client("s3")

    rows = list_files()
    deleted = 0
    for row in rows:
        fid = row.get("file_id")
        if fid:
            ddb.delete_item(
                TableName=config.VERDICTS_TABLE,
                Key={"file_id": {"S": fid}},
            )
            deleted += 1

    # Empty the object buckets too, so nothing lingers in storage.
    for bucket in (config.INCOMING_BUCKET, config.CLEAN_BUCKET, config.QUARANTINE_BUCKET):
        try:
            listing = s3.list_objects_v2(Bucket=bucket)
        except Exception:  # noqa: BLE001
            continue
        objs = [{"Key": o["Key"]} for o in listing.get("Contents", [])]
        if objs:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": objs})

    return deleted


def forward(method, path, body=None):
    """Forward a request to the deployed API Gateway and return (status, bytes)."""
    global API_BASE
    if not API_BASE:
        API_BASE = _client.api_base_url()
    url = f"{API_BASE}{path}"
    data = body if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, payload, content_type="application/json"):
        if isinstance(payload, (dict, list)):
            payload = json.dumps(payload).encode()
        elif isinstance(payload, str):
            payload = payload.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _serve_static(self, name, content_type):
        path = os.path.join(HERE, name)
        if not os.path.isfile(path):
            self._send(404, {"error": "not found"})
            return
        with open(path, "rb") as fh:
            self._send(200, fh.read(), content_type)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._serve_static("index.html", "text/html; charset=utf-8")
        if self.path == "/app.js":
            return self._serve_static("app.js", "text/javascript")
        if self.path == "/styles.css":
            return self._serve_static("styles.css", "text/css")
        if self.path == "/api/files":
            try:
                return self._send(200, {"files": list_files()})
            except Exception as exc:  # noqa: BLE001
                return self._send(500, {"error": str(exc)})
        if self.path.startswith("/api/files/"):
            fid = self.path.rsplit("/", 1)[-1]
            status, raw = forward("GET", f"/files/{fid}")
            return self._send(status, raw)
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/api/upload":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            status, raw = forward("POST", "/upload", body=body)
            return self._send(status, raw)
        if self.path == "/api/clear":
            try:
                removed = clear_files()
                return self._send(200, {"cleared": removed})
            except Exception as exc:  # noqa: BLE001
                return self._send(500, {"error": str(exc)})
        self._send(404, {"error": "not found"})

    def log_message(self, *_args):
        pass  # quiet


def main():
    print(f"[dashboard] API base: {API_BASE}")
    print(f"[dashboard] open http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()

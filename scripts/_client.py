"""Shared helpers for the demo/utility scripts.

Resolves the API base URL from `terraform output` (falling back to discovering
the REST API id via the LocalStack apigateway listing), and wraps upload/status.
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

ENDPOINT = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
TERRAFORM_DIR = os.path.join(os.path.dirname(__file__), "..", "terraform")


def _terraform_output(name):
    try:
        out = subprocess.run(
            ["terraform", f"-chdir={TERRAFORM_DIR}", "output", "-raw", name],
            capture_output=True, text=True, check=True,
        )
        value = out.stdout.strip()
        return value or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _discover_api_id():
    """Fallback: ask LocalStack for the first REST API id."""
    url = f"{ENDPOINT}/_aws/execute-api"  # not used; placeholder for clarity
    try:
        with urllib.request.urlopen(f"{ENDPOINT}/restapis") as resp:
            data = json.loads(resp.read().decode())
            items = data.get("item") or data.get("items") or []
            if items:
                return items[0].get("id")
    except (urllib.error.URLError, ValueError, KeyError):
        return None
    return None


def api_base_url():
    url = _terraform_output("api_url")
    if url:
        return url
    api_id = _discover_api_id()
    if api_id:
        return f"{ENDPOINT}/restapis/{api_id}/v1/_user_request_"
    raise RuntimeError(
        "Could not resolve the API URL. Run `terraform apply` first, or check "
        "that LocalStack is running."
    )


def _request(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or "{}"
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw}


def upload(base_url, filename, content_b64):
    return _request("POST", f"{base_url}/upload",
                    {"filename": filename, "content_b64": content_b64})


def status(base_url, file_id):
    return _request("GET", f"{base_url}/files/{file_id}")


def wait_for_scanned(base_url, file_id, timeout=30, interval=1.5):
    """Poll status until scan_state == SCANNED or timeout. Returns the record."""
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        code, body = status(base_url, file_id)
        if code == 200:
            last = body
            if body.get("scan_state") == "SCANNED":
                return body
        time.sleep(interval)
    return last

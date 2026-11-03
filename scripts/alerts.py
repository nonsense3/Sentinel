"""Print SECURITY ALERT lines written by the alerts Lambda.

LocalStack stores Lambda output in CloudWatch Logs, not in the container's
stdout, so this reads the /aws/lambda/sentinel-alerts log group directly.
"""
import os
import sys

os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")
# Resources live in us-east-1; ignore a machine-wide region such as ap-south-1.
os.environ["AWS_DEFAULT_REGION"] = os.environ.get("TF_REGION", "us-east-1")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from common import aws  # noqa: E402

LOG_GROUP = "/aws/lambda/sentinel-alerts"


def main():
    logs = aws.client("logs")
    try:
        resp = logs.filter_log_events(logGroupName=LOG_GROUP, filterPattern="SECURITY")
    except logs.exceptions.ResourceNotFoundException:
        print("no alerts yet (the alerts Lambda has not run)")
        return

    lines = [e["message"].strip() for e in resp.get("events", [])
             if "SECURITY ALERT" in e.get("message", "")]
    if not lines:
        print("no alerts yet")
        return
    for line in lines:
        print(line)
    print(f"\n{len(lines)} alert(s)")


if __name__ == "__main__":
    main()

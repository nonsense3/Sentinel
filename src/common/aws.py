"""boto3 client factory that honors LocalStack endpoints.

Inside a LocalStack Lambda container the handler reaches the gateway via
AWS_ENDPOINT_URL (set through LAMBDA_DOCKER_FLAGS) or the LOCALSTACK_HOSTNAME
variable LocalStack injects. Local scripts use AWS_ENDPOINT_URL from .env.
"""
import os

import boto3


def _endpoint_url():
    # Explicit endpoint wins (local scripts, and the value we inject into Lambda).
    endpoint = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:
        return endpoint
    # LocalStack injects LOCALSTACK_HOSTNAME inside Lambda containers.
    host = os.environ.get("LOCALSTACK_HOSTNAME")
    if host:
        return f"http://{host}:4566"
    return None


def _region():
    return os.environ.get("AWS_DEFAULT_REGION", "us-east-1")


def client(service):
    """Return a boto3 client wired to LocalStack when an endpoint is known."""
    kwargs = {"region_name": _region()}
    endpoint = _endpoint_url()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client(service, **kwargs)


def resource(service):
    kwargs = {"region_name": _region()}
    endpoint = _endpoint_url()
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.resource(service, **kwargs)

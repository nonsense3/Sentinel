# Sentinel: Implementation Plan

## 1. Goal
Show judges a believable, reliable, event-driven backend that runs from a fresh clone with one command.
Score is driven by: working end-to-end flow, clean IaC, reliability features, and a smooth demo.

## 2. Scope

**Must have (MVP)**
- Upload API -> S3 -> SQS -> scanner Lambda -> clean/quarantine buckets + DynamoDB verdict
- Status API
- Checks: hash, magic bytes, double extension, patterns (incl. EICAR)
- Terraform for everything, docker-compose, one-command setup, README

**Should have**
- Entropy, archive inspection, risk scoring with reasons
- DLQ + retries, idempotency, alerts queue + consumer
- Unit tests, demo script with PASS/FAIL table

**Nice to have (stretch)**
- ClamAV container as a second engine
- YARA rules folder
- Pre-signed S3 upload URLs (large files)
- Tiny dashboard listing files and verdicts
- GitHub Actions running the tests and `terraform validate`

**Out of scope**: real malware samples, authentication, production hardening.

## 3. Data model

`sentinel-verdicts` (key: `file_id`): `filename`, `scan_state` (PENDING|SCANNED), `verdict`, `risk_score`,
`reasons[]`, `sha256`, `size_bytes`, `stored_at`, `cache_hit`, `uploaded_at`, `scanned_at`

`sentinel-known-hashes` (key: `sha256`): `verdict`, `risk_score`, `reasons[]`, `source` (seed|cache)

Object keys: `{file_id}/{filename}` in each of the three buckets.

## 4. Milestones

| # | Milestone | Done when |
|---|---|---|
| M0 | Environment | `docker compose up` healthy, `awslocal s3 mb s3://test` works, token set |
| M1 | Infrastructure | `terraform apply` creates 3 buckets, 3 queues, 2 tables, 4 Lambdas, API |
| M2 | Happy path | Upload via API ends in `SCANNED` with a verdict |
| M3 | Detection | All sample files produce expected verdicts (`make test` and `make demo` pass) |
| M4 | Reliability | `crash-me.txt` lands in DLQ; duplicate upload shows `cache_hit=true`; EICAR triggers an alert log |
| M5 | Polish | README, architecture diagram image, clean-clone test, demo recording |
| M6 | Stretch | ClamAV / YARA / dashboard, only if M5 is solid |

## 5. Suggested timeline (compress or stretch to your deadline)

1. **Setup and infra** (M0, M1): LocalStack running, Terraform applying cleanly.
2. **Core flow** (M2): upload, queue, scan, move, store.
3. **Detection and tests** (M3): all checks, scoring, unit tests.
4. **Reliability** (M4): DLQ, idempotency, alerts.
5. **Polish** (M5): README, diagram, fresh-clone test, demo video.
6. **Buffer / stretch** (M6).

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| LocalStack version or licensing behaves differently than expected | Pin an image tag once it works; document `LOCALSTACK_IMAGE` fallback |
| API Gateway URL format differs by LocalStack version | `terraform output api_url`; fall back to `awslocal apigateway get-rest-apis` and the `{id}.execute-api.localhost.localstack.cloud:4566` style |
| Lambda cannot reach LocalStack from its container | Mount Docker socket; handlers read `AWS_ENDPOINT_URL` / `LOCALSTACK_HOSTNAME` |
| Terraform apply races (S3 notification before queue policy) | Already handled with `depends_on` |
| Antivirus deletes the EICAR sample | Samples are generated at runtime; mention in README |
| Works on my machine only | Test from a fresh clone in an empty folder before submitting |

## 7. Demo script (about 3 minutes)

1. `cp .env.example .env && make up` (show it is one command)
2. `make demo` and walk through the table: clean file, EICAR (malicious), disguised exe, macro doc, double extension, PDF JavaScript, zip bomb
3. Point at the `reasons` for one verdict (explainability)
4. Re-upload EICAR: `cache_hit = true`
5. `crash-me.txt`: retries, then the DLQ message count
6. `docker compose logs localstack | grep "SECURITY ALERT"`: the alert pipeline
7. Show `terraform/` and the architecture diagram

## 8. Submission checklist

- [ ] Fresh clone -> `make up && make demo` passes
- [ ] `.env` is not committed; `.env.example` is
- [ ] README has diagram, prerequisites, quick start, troubleshooting
- [ ] Tests pass (`make test`)
- [ ] Repo description and topics set (localstack, serverless, terraform, security)
- [ ] Demo video or screenshots linked in the README

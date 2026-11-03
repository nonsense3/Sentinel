# --- Packaging -------------------------------------------------------------
# Each function needs its own handler plus the shared `common` package. We zip
# the whole src/ tree once and point every function at it with a distinct
# handler path (e.g. "upload/handler.handler"). This keeps `import common...`
# working inside every Lambda with zero build step.

data "archive_file" "src" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/build/sentinel_src.zip"
}

locals {
  # Environment shared by every function so handlers resolve resource names.
  common_env = {
    INCOMING_BUCKET    = aws_s3_bucket.incoming.bucket
    CLEAN_BUCKET       = aws_s3_bucket.clean.bucket
    QUARANTINE_BUCKET  = aws_s3_bucket.quarantine.bucket
    VERDICTS_TABLE     = aws_dynamodb_table.verdicts.name
    KNOWN_HASHES_TABLE = aws_dynamodb_table.known_hashes.name
    ALERTS_QUEUE_URL   = aws_sqs_queue.alerts.id
  }
}

# --- Functions -------------------------------------------------------------

resource "aws_lambda_function" "upload" {
  function_name    = "${var.name_prefix}-upload"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.11"
  handler          = "upload/handler.handler"
  filename         = data.archive_file.src.output_path
  source_code_hash = data.archive_file.src.output_base64sha256
  timeout          = 30

  environment {
    variables = local.common_env
  }
}

resource "aws_lambda_function" "status" {
  function_name    = "${var.name_prefix}-status"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.11"
  handler          = "status/handler.handler"
  filename         = data.archive_file.src.output_path
  source_code_hash = data.archive_file.src.output_base64sha256
  timeout          = 30

  environment {
    variables = local.common_env
  }
}

resource "aws_lambda_function" "scanner" {
  function_name    = "${var.name_prefix}-scanner"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.11"
  handler          = "scanner/handler.handler"
  filename         = data.archive_file.src.output_path
  source_code_hash = data.archive_file.src.output_base64sha256
  timeout          = 90

  environment {
    variables = local.common_env
  }
}

resource "aws_lambda_function" "alerts" {
  function_name    = "${var.name_prefix}-alerts"
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.11"
  handler          = "alerts/handler.handler"
  filename         = data.archive_file.src.output_path
  source_code_hash = data.archive_file.src.output_base64sha256
  timeout          = 30

  environment {
    variables = local.common_env
  }
}

# --- Event source mappings -------------------------------------------------
# Batch size 1 gives deterministic per-file retry/DLQ behavior for the demo.

resource "aws_lambda_event_source_mapping" "scan" {
  event_source_arn = aws_sqs_queue.scan.arn
  function_name    = aws_lambda_function.scanner.arn
  batch_size       = 1
  enabled          = true
}

resource "aws_lambda_event_source_mapping" "alerts" {
  event_source_arn = aws_sqs_queue.alerts.arn
  function_name    = aws_lambda_function.alerts.arn
  batch_size       = 1
  enabled          = true
}

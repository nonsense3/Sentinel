# Dead-letter queue for scans that fail max_receive_count times.
resource "aws_sqs_queue" "scan_dlq" {
  name = "${var.name_prefix}-scan-dlq"
}

# Main scan queue. S3 notifications land here; the scanner Lambda consumes it.
resource "aws_sqs_queue" "scan" {
  name                       = "${var.name_prefix}-scan-queue"
  visibility_timeout_seconds = 120 # >= scanner Lambda timeout

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.scan_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

# Alerts queue: scanner publishes malicious verdicts, alerts Lambda consumes.
resource "aws_sqs_queue" "alerts" {
  name = "${var.name_prefix}-alerts"
}

# Allow the incoming bucket to publish notifications to the scan queue.
resource "aws_sqs_queue_policy" "scan_from_s3" {
  queue_url = aws_sqs_queue.scan.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.scan.arn
      Condition = {
        ArnLike = { "aws:SourceArn" = aws_s3_bucket.incoming.arn }
      }
    }]
  })
}

# Wire the bucket -> queue notification. depends_on ensures the queue policy
# exists first, avoiding the classic S3-notification race.
resource "aws_s3_bucket_notification" "incoming_to_scan" {
  bucket = aws_s3_bucket.incoming.id

  queue {
    queue_arn = aws_sqs_queue.scan.arn
    events    = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_sqs_queue_policy.scan_from_s3]
}

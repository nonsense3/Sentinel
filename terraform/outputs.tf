# LocalStack serves API Gateway at:
#   http://localhost:4566/restapis/{rest_api_id}/{stage}/_user_request_
output "api_url" {
  description = "Base URL for the Sentinel REST API on LocalStack."
  value       = "${var.localstack_endpoint}/restapis/${aws_api_gateway_rest_api.sentinel.id}/${aws_api_gateway_stage.v1.stage_name}/_user_request_"
}

output "rest_api_id" {
  value = aws_api_gateway_rest_api.sentinel.id
}

output "incoming_bucket" {
  value = aws_s3_bucket.incoming.bucket
}

output "clean_bucket" {
  value = aws_s3_bucket.clean.bucket
}

output "quarantine_bucket" {
  value = aws_s3_bucket.quarantine.bucket
}

output "scan_queue_url" {
  value = aws_sqs_queue.scan.id
}

output "scan_dlq_url" {
  value = aws_sqs_queue.scan_dlq.id
}

output "alerts_queue_url" {
  value = aws_sqs_queue.alerts.id
}

output "verdicts_table" {
  value = aws_dynamodb_table.verdicts.name
}

output "known_hashes_table" {
  value = aws_dynamodb_table.known_hashes.name
}

# REST API with two routes:
#   POST /upload        -> upload Lambda
#   GET  /files/{id}    -> status Lambda
# Both use AWS_PROXY integration so the Lambda sees the raw request/response.

resource "aws_api_gateway_rest_api" "sentinel" {
  name = "${var.name_prefix}-api"
}

# --- /upload ---------------------------------------------------------------
resource "aws_api_gateway_resource" "upload" {
  rest_api_id = aws_api_gateway_rest_api.sentinel.id
  parent_id   = aws_api_gateway_rest_api.sentinel.root_resource_id
  path_part   = "upload"
}

resource "aws_api_gateway_method" "upload_post" {
  rest_api_id   = aws_api_gateway_rest_api.sentinel.id
  resource_id   = aws_api_gateway_resource.upload.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "upload" {
  rest_api_id             = aws_api_gateway_rest_api.sentinel.id
  resource_id             = aws_api_gateway_resource.upload.id
  http_method             = aws_api_gateway_method.upload_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.upload.invoke_arn
}

# --- /files/{id} -----------------------------------------------------------
resource "aws_api_gateway_resource" "files" {
  rest_api_id = aws_api_gateway_rest_api.sentinel.id
  parent_id   = aws_api_gateway_rest_api.sentinel.root_resource_id
  path_part   = "files"
}

resource "aws_api_gateway_resource" "file_id" {
  rest_api_id = aws_api_gateway_rest_api.sentinel.id
  parent_id   = aws_api_gateway_resource.files.id
  path_part   = "{id}"
}

resource "aws_api_gateway_method" "file_get" {
  rest_api_id   = aws_api_gateway_rest_api.sentinel.id
  resource_id   = aws_api_gateway_resource.file_id.id
  http_method   = "GET"
  authorization = "NONE"

  request_parameters = {
    "method.request.path.id" = true
  }
}

resource "aws_api_gateway_integration" "status" {
  rest_api_id             = aws_api_gateway_rest_api.sentinel.id
  resource_id             = aws_api_gateway_resource.file_id.id
  http_method             = aws_api_gateway_method.file_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.status.invoke_arn
}

# --- Deployment + stage ----------------------------------------------------
resource "aws_api_gateway_deployment" "sentinel" {
  rest_api_id = aws_api_gateway_rest_api.sentinel.id

  # Redeploy when any integration/method changes.
  triggers = {
    redeploy = sha1(jsonencode([
      aws_api_gateway_integration.upload.id,
      aws_api_gateway_integration.status.id,
      aws_api_gateway_method.upload_post.id,
      aws_api_gateway_method.file_get.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.upload,
    aws_api_gateway_integration.status,
  ]
}

resource "aws_api_gateway_stage" "v1" {
  rest_api_id   = aws_api_gateway_rest_api.sentinel.id
  deployment_id = aws_api_gateway_deployment.sentinel.id
  stage_name    = "v1"
}

# --- Lambda invoke permissions for API Gateway -----------------------------
resource "aws_lambda_permission" "upload" {
  statement_id  = "AllowAPIGatewayUpload"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.upload.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.sentinel.execution_arn}/*/*"
}

resource "aws_lambda_permission" "status" {
  statement_id  = "AllowAPIGatewayStatus"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.status.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.sentinel.execution_arn}/*/*"
}

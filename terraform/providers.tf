terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

# All AWS calls are redirected to LocalStack. Credentials are fake; the
# validation/metadata skips keep the provider from reaching real AWS.
provider "aws" {
  region                      = var.aws_region
  access_key                  = "test"
  secret_key                  = "test"
  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    s3         = var.localstack_endpoint
    sqs        = var.localstack_endpoint
    lambda     = var.localstack_endpoint
    dynamodb   = var.localstack_endpoint
    apigateway = var.localstack_endpoint
    iam        = var.localstack_endpoint
    sts        = var.localstack_endpoint
    logs       = var.localstack_endpoint
  }
}

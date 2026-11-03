variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "localstack_endpoint" {
  type    = string
  default = "http://localhost:4566"
}

variable "name_prefix" {
  type    = string
  default = "sentinel"
}

# Number of receives before a scan message is dead-lettered.
variable "max_receive_count" {
  type    = number
  default = 3
}

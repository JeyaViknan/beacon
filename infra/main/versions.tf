terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0" # 6.x: aws_lambda_permission.invoked_via_function_url (ADR 0012)
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

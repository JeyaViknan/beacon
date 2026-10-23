terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  # Bootstrap keeps LOCAL state on purpose: it creates the bucket that every other stack uses.
  # Keep infra/bootstrap/terraform.tfstate safe (it is gitignored); everything here can be
  # re-imported if it is ever lost.
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { project = "beacon", stack = "bootstrap" }
  }
}

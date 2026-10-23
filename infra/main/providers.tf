locals {
  default_tags = { project = var.project, stack = "main" }
}

provider "aws" {
  region = var.home_region
  default_tags {
    tags = local.default_tags
  }
}

# Terraform cannot create providers in a for_each, so every supported probe region has a fixed
# alias and its probe module is switched on with count (see probes.tf).
provider "aws" {
  alias  = "singapore"
  region = "ap-southeast-1"
  default_tags {
    tags = local.default_tags
  }
}

provider "aws" {
  alias  = "virginia"
  region = "us-east-1"
  default_tags {
    tags = local.default_tags
  }
}

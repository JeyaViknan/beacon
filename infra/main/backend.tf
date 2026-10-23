# The bucket name is account-specific, so it is passed at init time:
#   terraform init -backend-config="bucket=beacon-tfstate-<account id>"
# use_lockfile = true gives native S3 state locking (Terraform >= 1.10), no DynamoDB lock table.
terraform {
  backend "s3" {
    key          = "beacon/main.tfstate"
    region       = "ap-south-1"
    encrypt      = true
    use_lockfile = true
  }
}

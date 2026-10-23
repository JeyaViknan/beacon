# Lambda code is uploaded to S3 once and Lambda pulls it from S3 inside AWS.
# Sending zips inline in CreateFunction failed on a slow uplink: a new account's first attempts
# are rejected while IAM roles propagate, and every retry re-sent the whole zip (ADR 0013).
resource "aws_s3_bucket" "artifacts" {
  bucket        = "beacon-artifacts-${data.aws_caller_identity.current.account_id}"
  force_destroy = true # build output only; everything here can be rebuilt from Git
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

locals {
  lambda_packages = toset(concat(keys(local.functions), ["probe"]))
}

resource "aws_s3_object" "lambda" {
  for_each    = local.lambda_packages
  bucket      = aws_s3_bucket.artifacts.id
  key         = "lambda/${each.key}.zip"
  source      = "${var.dist_dir}/${each.key}.zip"
  source_hash = filemd5("${var.dist_dir}/${each.key}.zip") # re-upload only when the zip changes

  depends_on = [aws_s3_bucket_public_access_block.artifacts]
}

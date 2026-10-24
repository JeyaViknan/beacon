data "aws_caller_identity" "current" {}

locals {
  account_id   = data.aws_caller_identity.current.account_id
  state_bucket = "beacon-tfstate-${local.account_id}"
}

# --------------------------------------------------------------------------- Terraform state bucket

resource "aws_s3_bucket" "state" {
  bucket = local.state_bucket

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # SSE-S3: free (a customer-managed KMS key is not)
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    id     = "expire-old-state-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

data "aws_iam_policy_document" "state_tls_only" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "state" {
  bucket = aws_s3_bucket.state.id
  policy = data.aws_iam_policy_document.state_tls_only.json
}

# --------------------------------------------------------------------------- GitHub OIDC + deploy role

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "deploy_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Only jobs that run in the protected `production` environment of this exact repo (pinned by
    # owner and repo ID, not just name) can assume the role. Pull requests and forks cannot.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["${var.github_oidc_sub_prefix}:environment:production"]
    }
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "beacon-github-deploy"
  description          = "Assumed by GitHub Actions (OIDC) to deploy Beacon"
  assume_role_policy   = data.aws_iam_policy_document.deploy_trust.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "deploy" {
  statement {
    sid       = "TerraformState"
    actions   = ["s3:ListBucket", "s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [aws_s3_bucket.state.arn, "${aws_s3_bucket.state.arn}/*"]
  }

  statement {
    sid = "BeaconScopedServices"
    actions = [
      "lambda:*",
      "dynamodb:*",
      "sqs:*",
      "sns:*",
      "scheduler:*",
      "logs:*",
      "ssm:*",
    ]
    resources = [
      "arn:aws:lambda:*:${local.account_id}:function:beacon-*",
      "arn:aws:lambda:*:${local.account_id}:event-source-mapping:*",
      "arn:aws:dynamodb:*:${local.account_id}:table/beacon",
      "arn:aws:dynamodb:*:${local.account_id}:table/beacon/*",
      "arn:aws:sqs:*:${local.account_id}:beacon-*",
      "arn:aws:sns:*:${local.account_id}:beacon-*",
      "arn:aws:scheduler:*:${local.account_id}:schedule/default/beacon-*",
      "arn:aws:logs:*:${local.account_id}:log-group:/aws/lambda/beacon-*",
      "arn:aws:logs:*:${local.account_id}:log-group:/aws/lambda/beacon-*:*",
      "arn:aws:ssm:*:${local.account_id}:parameter/beacon/*",
    ]
  }

  statement {
    sid = "ListAndDescribe"
    # These APIs do not support resource-level permissions.
    actions = [
      "lambda:GetAccountSettings",
      "lambda:ListFunctions",
      "lambda:CreateEventSourceMapping",
      "lambda:GetEventSourceMapping",
      "lambda:ListEventSourceMappings",
      "logs:DescribeLogGroups",
      "ssm:DescribeParameters",
      "sns:ListTopics",
      "sqs:ListQueues",
      "dynamodb:ListTables",
      "dynamodb:DescribeLimits",
      "scheduler:ListSchedules",
      "cloudwatch:*",
      "cloudfront:*",
      "xray:*",
      "sts:GetCallerIdentity",
      "budgets:ViewBudget",
    ]
    resources = ["*"]
  }

  statement {
    sid     = "WebAndArtifactBuckets"
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::beacon-web-${local.account_id}",
      "arn:aws:s3:::beacon-web-${local.account_id}/*",
      "arn:aws:s3:::beacon-artifacts-${local.account_id}",
      "arn:aws:s3:::beacon-artifacts-${local.account_id}/*",
    ]
  }

  statement {
    sid = "BeaconRoles"
    actions = [
      "iam:GetRole", "iam:CreateRole", "iam:DeleteRole", "iam:UpdateRole", "iam:TagRole", "iam:UntagRole",
      "iam:UpdateAssumeRolePolicy", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies",
      "iam:GetRolePolicy", "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:ListInstanceProfilesForRole",
      "iam:PassRole",
    ]
    resources = ["arn:aws:iam::${local.account_id}:role/beacon-*"]
  }

  statement {
    sid       = "NoSelfEscalation"
    effect    = "Deny"
    actions   = ["iam:*"]
    resources = [aws_iam_role.deploy.arn]
  }
}

resource "aws_iam_role_policy" "deploy" {
  name   = "beacon-deploy"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}

# --------------------------------------------------------------------------- cost guardrail

resource "aws_budgets_budget" "monthly" {
  name         = "beacon-monthly"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_usd
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 50
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.alert_email]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.alert_email]
  }
}

# --------------------------------------------------------------------------- ops PagerDuty URL
# Created here (not in infra/main) so infra/main can read it with a data source at plan time and
# decide whether to subscribe PagerDuty to the ops topic. Jeya sets the real value in M7.

resource "aws_ssm_parameter" "pagerduty_ops_url" {
  name        = "/beacon/pagerduty_ops_url"
  description = "PagerDuty CloudWatch integration URL for the Beacon Platform service ('unset' = none)"
  type        = "SecureString"
  value       = "unset"

  lifecycle {
    ignore_changes = [value]
  }
}

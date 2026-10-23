# Home-region Lambdas. Each gets its own role with only what it needs (least privilege),
# an explicit log group with 7-day retention, arm64, and X-Ray tracing.
# The probe lives in modules/probe because it can run in several regions.

resource "random_password" "origin_verify" {
  length  = 48
  special = false
}

locals {
  table_arns = [aws_dynamodb_table.beacon.arn, "${aws_dynamodb_table.beacon.arn}/index/*"]
  ssm_arn    = "arn:aws:ssm:${var.home_region}:${data.aws_caller_identity.current.account_id}:parameter/beacon"

  common_env = {
    TABLE_NAME                   = aws_dynamodb_table.beacon.name
    HOME_REGION                  = var.home_region
    BEACON_VERSION               = var.app_version
    POWERTOOLS_METRICS_NAMESPACE = "Beacon"
    POWERTOOLS_LOG_LEVEL         = "INFO"
  }

  functions = {
    api = {
      description = "Beacon API (behind CloudFront /api/*)"
      memory      = 256
      timeout     = 20 # "Test now" may wait up to a 15 s check timeout
      env = {
        ORIGIN_VERIFY_SECRET     = random_password.origin_verify.result
        PRODUCT_ALERTS_TOPIC_ARN = aws_sns_topic.product_alerts.arn
        EMAIL_CONFIGURED         = "true"
      }
    }
    processor = {
      description = "Beacon processor: probe results -> state, rollups, incidents, alerts"
      memory      = 256
      timeout     = 30
      env         = { PRODUCT_ALERTS_TOPIC_ARN = aws_sns_topic.product_alerts.arn }
    }
    notifier = {
      description = "Beacon notifier: Web Push + PagerDuty"
      memory      = 128
      timeout     = 15
      env         = {}
    }
    maintenance = {
      description = "Beacon daily maintenance: TLS expiry + daily summary"
      memory      = 256
      timeout     = 120
      env         = { PRODUCT_ALERTS_TOPIC_ARN = aws_sns_topic.product_alerts.arn }
    }
    demo_target = {
      description = "Beacon demo target: 200 or 503 from SSM /beacon/demo/healthy"
      memory      = 128
      timeout     = 5
      env         = {}
    }
  }
}

resource "aws_cloudwatch_log_group" "fn" {
  for_each          = local.functions
  name              = "/aws/lambda/beacon-${replace(each.key, "_", "-")}"
  retention_in_days = var.log_retention_days
}

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "fn" {
  for_each           = local.functions
  name               = "beacon-${replace(each.key, "_", "-")}"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

# --------------------------------------------------------------------------- per-function policies

data "aws_iam_policy_document" "base" {
  for_each = local.functions
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.fn[each.key].arn}:*"]
  }
  statement {
    sid       = "Tracing"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"]
  }
}

data "aws_iam_policy_document" "api" {
  source_policy_documents = [data.aws_iam_policy_document.base["api"].json]
  statement {
    sid = "Table"
    actions = [
      "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem",
      "dynamodb:Query",
    ]
    resources = local.table_arns
  }
  statement {
    sid     = "ReadParams"
    actions = ["ssm:GetParameter"]
    resources = [for p in [
      "admin_password_hash", "jwt_secret", "vapid_private_key", "pagerduty_routing_key",
      "healthchecks_ping_url", "demo/healthy", "app_url",
    ] : "${local.ssm_arn}/${p}"]
  }
  statement {
    sid       = "ToggleDemo"
    actions   = ["ssm:PutParameter"]
    resources = ["${local.ssm_arn}/demo/healthy"]
  }
  statement {
    sid       = "Alerts"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.product_alerts.arn]
  }
}

data "aws_iam_policy_document" "processor" {
  source_policy_documents = [data.aws_iam_policy_document.base["processor"].json]
  statement {
    sid = "Table"
    # TransactWriteItems is authorised per underlying Put/Update.
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"]
    resources = local.table_arns
  }
  statement {
    sid       = "Queue"
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility"]
    resources = [aws_sqs_queue.results.arn]
  }
  statement {
    sid       = "Params"
    actions   = ["ssm:GetParameter"]
    resources = ["${local.ssm_arn}/healthchecks_ping_url", "${local.ssm_arn}/app_url"]
  }
  statement {
    sid       = "Alerts"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.product_alerts.arn]
  }
}

data "aws_iam_policy_document" "notifier" {
  source_policy_documents = [data.aws_iam_policy_document.base["notifier"].json]
  statement {
    sid       = "Table"
    actions   = ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:DeleteItem"]
    resources = [aws_dynamodb_table.beacon.arn]
    condition {
      test     = "ForAllValues:StringEquals"
      variable = "dynamodb:LeadingKeys"
      values   = ["PUSHSUB", "CONFIG"]
    }
  }
  statement {
    sid     = "Params"
    actions = ["ssm:GetParameter"]
    resources = [for p in ["vapid_private_key", "vapid_subject", "pagerduty_routing_key", "app_url"] :
    "${local.ssm_arn}/${p}"]
  }
}

data "aws_iam_policy_document" "maintenance" {
  source_policy_documents = [data.aws_iam_policy_document.base["maintenance"].json]
  statement {
    sid       = "Table"
    actions   = ["dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:Query"]
    resources = local.table_arns
  }
  statement {
    sid       = "Params"
    actions   = ["ssm:GetParameter"]
    resources = ["${local.ssm_arn}/app_url"]
  }
  statement {
    sid       = "Alerts"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.product_alerts.arn]
  }
}

data "aws_iam_policy_document" "demo_target" {
  source_policy_documents = [data.aws_iam_policy_document.base["demo_target"].json]
  statement {
    sid       = "Param"
    actions   = ["ssm:GetParameter"]
    resources = ["${local.ssm_arn}/demo/healthy"]
  }
}

locals {
  policies = {
    api         = data.aws_iam_policy_document.api.json
    processor   = data.aws_iam_policy_document.processor.json
    notifier    = data.aws_iam_policy_document.notifier.json
    maintenance = data.aws_iam_policy_document.maintenance.json
    demo_target = data.aws_iam_policy_document.demo_target.json
  }
}

resource "aws_iam_role_policy" "fn" {
  for_each = local.functions
  name     = "beacon-${replace(each.key, "_", "-")}"
  role     = aws_iam_role.fn[each.key].id
  policy   = local.policies[each.key]
}

# --------------------------------------------------------------------------- functions

resource "aws_lambda_function" "fn" {
  for_each         = local.functions
  function_name    = "beacon-${replace(each.key, "_", "-")}"
  description      = each.value.description
  role             = aws_iam_role.fn[each.key].arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "${each.key}.app.handler"
  s3_bucket        = aws_s3_object.lambda[each.key].bucket
  s3_key           = aws_s3_object.lambda[each.key].key
  source_code_hash = filebase64sha256("${var.dist_dir}/${each.key}.zip")
  memory_size      = each.value.memory
  timeout          = each.value.timeout

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = merge(local.common_env, each.value.env, {
      POWERTOOLS_SERVICE_NAME = "beacon-${replace(each.key, "_", "-")}"
    })
  }

  depends_on = [aws_cloudwatch_log_group.fn, aws_iam_role_policy.fn]
}

# Processor: SQS trigger with partial batch failure reporting. maximum_concurrency = 2 keeps
# optimistic-lock conflicts rare and DynamoDB writes well inside provisioned capacity.
resource "aws_lambda_event_source_mapping" "processor" {
  event_source_arn                   = aws_sqs_queue.results.arn
  function_name                      = aws_lambda_function.fn["processor"].arn
  batch_size                         = 10
  maximum_batching_window_in_seconds = 0
  function_response_types            = ["ReportBatchItemFailures"]

  scaling_config {
    maximum_concurrency = 2
  }
}

# Notifier is invoked asynchronously by SNS: retry twice, then give up after an hour.
resource "aws_lambda_function_event_invoke_config" "notifier" {
  function_name                = aws_lambda_function.fn["notifier"].function_name
  maximum_retry_attempts       = 2
  maximum_event_age_in_seconds = 3600
}

# --------------------------------------------------------------------------- function URLs
# Public (auth NONE) URLs need two resource-policy statements since Oct 2025:
# InvokeFunctionUrl, and InvokeFunction restricted to calls made via the function URL.

locals {
  public_urls = toset(["api", "demo_target"])
}

resource "aws_lambda_function_url" "fn" {
  for_each           = local.public_urls
  function_name      = aws_lambda_function.fn[each.key].function_name
  authorization_type = "NONE" # API: protected by the CloudFront origin secret + JWT
}

resource "aws_lambda_permission" "url_invoke_url" {
  for_each               = local.public_urls
  statement_id           = "FunctionURLAllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.fn[each.key].function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "url_invoke_function" {
  for_each                 = local.public_urls
  statement_id             = "FunctionURLInvokeAllowPublicAccess"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.fn[each.key].function_name
  principal                = "*"
  invoked_via_function_url = true
}

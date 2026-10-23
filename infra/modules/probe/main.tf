# One probe = Lambda + IAM role + log group + 1-minute schedule, in ONE region.
# Remote-region probes read the snapshot from and send results to the home region.

locals {
  name = "beacon-probe"
  # IAM is global, so role names carry the region to stay unique.
  role_name = "beacon-probe-${var.region}"
}

resource "aws_cloudwatch_log_group" "probe" {
  name              = "/aws/lambda/${local.name}"
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

resource "aws_iam_role" "probe" {
  name               = local.role_name
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "probe" {
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.probe.arn}:*"]
  }
  statement {
    sid       = "ReadSnapshot"
    actions   = ["dynamodb:GetItem"]
    resources = [var.table_arn]
    condition {
      test     = "ForAllValues:StringEquals"
      variable = "dynamodb:LeadingKeys"
      values   = ["CONFIG"]
    }
  }
  statement {
    sid       = "SendResults"
    actions   = ["sqs:SendMessage"]
    resources = [var.queue_arn]
  }
  statement {
    sid       = "Tracing"
    actions   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "probe" {
  name   = local.role_name
  role   = aws_iam_role.probe.id
  policy = data.aws_iam_policy_document.probe.json
}

resource "aws_lambda_function" "probe" {
  function_name    = local.name
  description      = "Beacon probe (${var.region}): runs due checks every minute"
  role             = aws_iam_role.probe.arn
  runtime          = "python3.12"
  architectures    = ["arm64"]
  handler          = "probe.app.handler"
  filename         = var.zip_path
  source_code_hash = filebase64sha256(var.zip_path)
  memory_size      = 256
  timeout          = 50

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      TABLE_NAME                   = var.table_name
      HOME_REGION                  = var.home_region
      RESULTS_QUEUE_URL            = var.queue_url
      PROBE_REGION                 = var.region
      PROBE_BUDGET_S               = "45"
      BEACON_VERSION               = var.app_version
      POWERTOOLS_SERVICE_NAME      = "beacon-probe"
      POWERTOOLS_METRICS_NAMESPACE = "Beacon"
      POWERTOOLS_LOG_LEVEL         = "INFO"
    }
  }

  depends_on = [aws_cloudwatch_log_group.probe, aws_iam_role_policy.probe]
}

# --------------------------------------------------------------------------- schedule

data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "beacon-probe-scheduler-${var.region}"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

resource "aws_iam_role_policy" "scheduler" {
  name = "invoke-probe"
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.probe.arn
    }]
  })
}

resource "aws_scheduler_schedule" "probe" {
  name                = "beacon-probe-every-minute"
  description         = "Runs the Beacon probe once a minute"
  schedule_expression = "rate(1 minute)"

  flexible_time_window {
    mode = "OFF" # run on the minute, not "sometime in a window"
  }

  target {
    arn      = aws_lambda_function.probe.arn
    role_arn = aws_iam_role.scheduler.arn
    # Scheduler fills in the scheduled minute; the probe uses it as runAt.
    input = jsonencode({ scheduledTime = "<aws.scheduler.scheduled-time>" })

    retry_policy {
      # A probe run that is a minute late is useless: the next run is already due.
      maximum_event_age_in_seconds = 60
      maximum_retry_attempts       = 0
    }
  }
}

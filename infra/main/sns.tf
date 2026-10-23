# Two deliberately separate streams (ADR 0009):
#   beacon-product-alerts: a product Beacon watches is down / recovered / slow.
#   beacon-ops-alerts:     Beacon itself is unhealthy (CloudWatch alarms).

resource "aws_sns_topic" "product_alerts" {
  name = "beacon-product-alerts"
}

resource "aws_sns_topic_subscription" "product_email" {
  topic_arn           = aws_sns_topic.product_alerts.arn
  protocol            = "email"
  endpoint            = var.alert_email
  filter_policy_scope = "MessageAttributes"
  # Email only for critical/warning alerts (and TEST), and only while email is enabled in Settings.
  filter_policy = jsonencode({
    email = ["on"]
    "$or" = [
      { severity = ["critical", "warning"] },
      { event = ["TEST"] },
    ]
  })
}

resource "aws_sns_topic_subscription" "product_notifier" {
  topic_arn = aws_sns_topic.product_alerts.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.fn["notifier"].arn
}

resource "aws_lambda_permission" "notifier_from_sns" {
  statement_id  = "AllowSnsInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fn["notifier"].function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.product_alerts.arn
}

resource "aws_sns_topic" "ops_alerts" {
  name = "beacon-ops-alerts"
}

data "aws_caller_identity" "current" {}

resource "aws_sns_topic_policy" "ops_alerts" {
  arn = aws_sns_topic.ops_alerts.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "CloudWatchAlarms"
      Effect    = "Allow"
      Principal = { Service = "cloudwatch.amazonaws.com" }
      Action    = "sns:Publish"
      Resource  = aws_sns_topic.ops_alerts.arn
      Condition = { StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id } }
    }]
  })
}

resource "aws_sns_topic_subscription" "ops_email" {
  topic_arn = aws_sns_topic.ops_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# PagerDuty "Beacon Platform" service: subscribed only once Jeya has stored the CloudWatch
# integration URL in SSM (created by infra/bootstrap with the value "unset").
# No Beacon code sits in this path, so a broken Beacon can still page.
data "aws_ssm_parameter" "pagerduty_ops_url" {
  name = "/beacon/pagerduty_ops_url"
}

locals {
  # Whether it is set is not secret; the URL itself stays sensitive.
  pagerduty_ops_enabled = nonsensitive(data.aws_ssm_parameter.pagerduty_ops_url.value) != "unset"
}

resource "aws_sns_topic_subscription" "ops_pagerduty" {
  count                  = local.pagerduty_ops_enabled ? 1 : 0
  topic_arn              = aws_sns_topic.ops_alerts.arn
  protocol               = "https"
  endpoint               = data.aws_ssm_parameter.pagerduty_ops_url.value
  endpoint_auto_confirms = true
}

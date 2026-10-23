# Alarms on Beacon's own health (HANDOVER §15). 9 alarms, 10 alarm metrics (ddb-throttles uses
# two metrics) = exactly the CloudWatch free tier. All notify beacon-ops-alerts on ALARM and OK,
# so PagerDuty incidents auto-resolve.

locals {
  ops_topic = [aws_sns_topic.ops_alerts.arn]
  lambda_alarms = {
    "probe-errors" = {
      fn      = "beacon-probe", metric = "Errors", stat = "Sum", threshold = 1, period = 60, evals = 5, datapoints = 3
      missing = "notBreaching", op = "GreaterThanOrEqualToThreshold"
      desc    = "Probe Lambda erroring in 3 of the last 5 minutes. Runbook: docs/runbooks/probe-errors.md"
    }
    "probe-not-running" = {
      fn      = "beacon-probe", metric = "Invocations", stat = "Sum", threshold = 1, period = 300, evals = 1, datapoints = 1
      missing = "breaching", op = "LessThanThreshold"
      desc    = "No probe invocations for 5 minutes: nothing is being checked. Runbook: docs/runbooks/probe-not-running.md"
    }
    "processor-errors" = {
      fn      = "beacon-processor", metric = "Errors", stat = "Sum", threshold = 1, period = 300, evals = 1, datapoints = 1
      missing = "notBreaching", op = "GreaterThanOrEqualToThreshold"
      desc    = "Processor Lambda errors. Runbook: docs/runbooks/processor-errors.md"
    }
    "notifier-errors" = {
      fn      = "beacon-notifier", metric = "Errors", stat = "Sum", threshold = 1, period = 300, evals = 1, datapoints = 1
      missing = "notBreaching", op = "GreaterThanOrEqualToThreshold"
      desc    = "Notifier failing: alerts may not reach the phone or PagerDuty. Runbook: docs/runbooks/notifier-errors.md"
    }
    "api-errors" = {
      fn      = "beacon-api", metric = "Errors", stat = "Sum", threshold = 5, period = 300, evals = 1, datapoints = 1
      missing = "notBreaching", op = "GreaterThanOrEqualToThreshold"
      desc    = "API Lambda errors (5+ in 5 min). Runbook: docs/runbooks/api-errors.md"
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "lambda" {
  for_each            = local.lambda_alarms
  alarm_name          = "beacon-${each.key}"
  alarm_description   = each.value.desc
  namespace           = "AWS/Lambda"
  metric_name         = each.value.metric
  dimensions          = { FunctionName = each.value.fn }
  statistic           = each.value.stat
  period              = each.value.period
  evaluation_periods  = each.value.evals
  datapoints_to_alarm = each.value.datapoints
  threshold           = each.value.threshold
  comparison_operator = each.value.op
  treat_missing_data  = each.value.missing
  alarm_actions       = local.ops_topic
  ok_actions          = local.ops_topic

  depends_on = [module.probe_mumbai, aws_lambda_function.fn]
}

resource "aws_cloudwatch_metric_alarm" "results_queue_age" {
  alarm_name          = "beacon-results-queue-age"
  alarm_description   = "Oldest probe result waiting > 3 min: the processor is not keeping up. Runbook: docs/runbooks/results-queue-age.md"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  dimensions          = { QueueName = aws_sqs_queue.results.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  datapoints_to_alarm = 3
  threshold           = 180
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.ops_topic
  ok_actions          = local.ops_topic
}

resource "aws_cloudwatch_metric_alarm" "dlq_not_empty" {
  alarm_name          = "beacon-dlq-not-empty"
  alarm_description   = "Probe results failed 5 times and landed in the DLQ. Runbook: docs/runbooks/dlq-not-empty.md"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.results_dlq.name }
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.ops_topic
  ok_actions          = local.ops_topic
}

resource "aws_cloudwatch_metric_alarm" "ddb_throttles" {
  alarm_name          = "beacon-ddb-throttles"
  alarm_description   = "DynamoDB throttled reads or writes: provisioned capacity exceeded. Runbook: docs/runbooks/ddb-throttles.md"
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.ops_topic
  ok_actions          = local.ops_topic

  metric_query {
    id          = "throttles"
    expression  = "FILL(reads, 0) + FILL(writes, 0)"
    label       = "Throttle events"
    return_data = true
  }
  metric_query {
    id = "reads"
    metric {
      namespace   = "AWS/DynamoDB"
      metric_name = "ReadThrottleEvents"
      dimensions  = { TableName = aws_dynamodb_table.beacon.name }
      stat        = "Sum"
      period      = 300
    }
  }
  metric_query {
    id = "writes"
    metric {
      namespace   = "AWS/DynamoDB"
      metric_name = "WriteThrottleEvents"
      dimensions  = { TableName = aws_dynamodb_table.beacon.name }
      stat        = "Sum"
      period      = 300
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "processor_duration" {
  alarm_name          = "beacon-processor-duration"
  alarm_description   = "Processor p95 duration > 20 s for 10 min (timeout is 30 s). Runbook: docs/runbooks/processor-duration.md"
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  dimensions          = { FunctionName = aws_lambda_function.fn["processor"].function_name }
  extended_statistic  = "p95"
  period              = 300
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 20000
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.ops_topic
  ok_actions          = local.ops_topic
}

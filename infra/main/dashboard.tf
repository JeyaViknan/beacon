# beacon-ops dashboard (1 of 3 free).
locals {
  fn_names = ["beacon-probe", "beacon-processor", "beacon-notifier", "beacon-api", "beacon-maintenance"]
  region   = var.home_region

  lambda_widget = { for m in ["Invocations", "Errors", "Duration"] : m => {
    type   = "metric"
    width  = 8
    height = 6
    properties = {
      title   = "Lambda ${m}"
      region  = local.region
      view    = "timeSeries"
      stat    = m == "Duration" ? "p95" : "Sum"
      period  = 300
      metrics = [for f in local.fn_names : ["AWS/Lambda", m, "FunctionName", f]]
    }
  } }
}

resource "aws_cloudwatch_dashboard" "ops" {
  dashboard_name = "beacon-ops"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "text"
        width  = 24
        height = 2
        properties = {
          markdown = "## Beacon ops\nProbe -> SQS -> processor -> DynamoDB/SNS -> notifier. Runbooks: `docs/runbooks/`. Alarms notify `beacon-ops-alerts`."
        }
      },
      local.lambda_widget["Invocations"],
      local.lambda_widget["Errors"],
      local.lambda_widget["Duration"],
      {
        type   = "metric"
        width  = 8
        height = 6
        properties = {
          title  = "Results queue"
          region = local.region
          stat   = "Maximum"
          period = 60
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.results.name],
            ["AWS/SQS", "ApproximateAgeOfOldestMessage", "QueueName", aws_sqs_queue.results.name, { yAxis = "right" }],
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.results_dlq.name, { label = "DLQ depth" }],
          ]
        }
      },
      {
        type   = "metric"
        width  = 8
        height = 6
        properties = {
          title  = "DynamoDB capacity (per second)"
          region = local.region
          period = 300
          metrics = [
            [{ expression = "consumedW / 300", label = "Consumed WCU/s", id = "cw" }],
            [{ expression = "consumedR / 300", label = "Consumed RCU/s", id = "cr" }],
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", aws_dynamodb_table.beacon.name, { id = "consumedW", stat = "Sum", visible = false }],
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", aws_dynamodb_table.beacon.name, { id = "consumedR", stat = "Sum", visible = false }],
            ["AWS/DynamoDB", "ProvisionedWriteCapacityUnits", "TableName", aws_dynamodb_table.beacon.name, { stat = "Maximum", label = "Provisioned WCU" }],
            ["AWS/DynamoDB", "WriteThrottleEvents", "TableName", aws_dynamodb_table.beacon.name, { stat = "Sum", yAxis = "right" }],
          ]
        }
      },
      {
        type   = "metric"
        width  = 8
        height = 6
        properties = {
          title  = "Checks and incidents (Beacon custom metrics)"
          region = local.region
          stat   = "Sum"
          period = 300
          metrics = [
            ["Beacon", "ChecksRun", "service", "beacon-probe"],
            ["Beacon", "ChecksFailed", "service", "beacon-probe"],
            ["Beacon", "IncidentsOpened", "service", "beacon-processor"],
            ["Beacon", "IncidentsResolved", "service", "beacon-processor"],
            ["Beacon", "NotificationsSent", "service", "beacon-notifier"],
            ["Beacon", "NotificationsFailed", "service", "beacon-notifier"],
          ]
        }
      },
      {
        type   = "alarm"
        width  = 24
        height = 4
        properties = {
          title = "Alarms"
          alarms = concat(
            [for a in aws_cloudwatch_metric_alarm.lambda : a.arn],
            [
              aws_cloudwatch_metric_alarm.results_queue_age.arn,
              aws_cloudwatch_metric_alarm.dlq_not_empty.arn,
              aws_cloudwatch_metric_alarm.ddb_throttles.arn,
              aws_cloudwatch_metric_alarm.processor_duration.arn,
            ],
          )
        }
      },
    ]
  })
}

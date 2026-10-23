# Daily maintenance at 09:00 IST (the probe schedules live in modules/probe).
data "aws_iam_policy_document" "scheduler_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "maintenance_scheduler" {
  name               = "beacon-maintenance-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_trust.json
}

resource "aws_iam_role_policy" "maintenance_scheduler" {
  name = "invoke-maintenance"
  role = aws_iam_role.maintenance_scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.fn["maintenance"].arn
    }]
  })
}

resource "aws_scheduler_schedule" "maintenance" {
  name                         = "beacon-maintenance-daily"
  description                  = "TLS expiry checks and the daily summary push"
  schedule_expression          = "cron(0 9 * * ? *)"
  schedule_expression_timezone = "Asia/Kolkata"

  flexible_time_window {
    mode                      = "FLEXIBLE"
    maximum_window_in_minutes = 5
  }

  target {
    arn      = aws_lambda_function.fn["maintenance"].arn
    role_arn = aws_iam_role.maintenance_scheduler.arn
    retry_policy {
      maximum_retry_attempts       = 2
      maximum_event_age_in_seconds = 3600
    }
  }
}

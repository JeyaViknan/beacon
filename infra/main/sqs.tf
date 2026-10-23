resource "aws_sqs_queue" "results_dlq" {
  name                      = "beacon-results-dlq"
  message_retention_seconds = 1209600 # 14 days: time to investigate and redrive
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "results" {
  name                       = "beacon-results"
  visibility_timeout_seconds = 6 * 30 # 6 x processor timeout (AWS guidance for Lambda consumers)
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 20
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.results_dlq.arn
    maxReceiveCount     = 5
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "results_dlq" {
  queue_url = aws_sqs_queue.results_dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.results.arn]
  })
}

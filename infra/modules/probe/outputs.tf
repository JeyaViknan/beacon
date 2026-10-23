output "function_name" {
  value = aws_lambda_function.probe.function_name
}

output "function_arn" {
  value = aws_lambda_function.probe.arn
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.probe.name
}

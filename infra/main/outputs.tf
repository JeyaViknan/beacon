output "cloudfront_url" {
  description = "Open this on the iPhone."
  value       = "https://${aws_cloudfront_distribution.site.domain_name}"
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "web_bucket" {
  value = aws_s3_bucket.web.bucket
}

output "api_function_url" {
  description = "Direct calls return 403 (no origin header): use the CloudFront URL."
  value       = aws_lambda_function_url.fn["api"].function_url
}

output "demo_target_url" {
  description = "Check URL for the 'Beacon Demo Target' product (scripts/seed_demo.py)."
  value       = aws_lambda_function_url.fn["demo_target"].function_url
}

output "table_name" {
  value = aws_dynamodb_table.beacon.name
}

output "queue_url" {
  value = aws_sqs_queue.results.url
}

output "dlq_url" {
  value = aws_sqs_queue.results_dlq.url
}

output "probe_regions" {
  value = var.probe_regions
}

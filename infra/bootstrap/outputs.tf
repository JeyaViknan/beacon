output "state_bucket" {
  description = "Set as the GitHub repo variable TF_STATE_BUCKET and pass to `make plan`."
  value       = aws_s3_bucket.state.bucket
}

output "deploy_role_arn" {
  description = "Set as the GitHub repo variable AWS_DEPLOY_ROLE_ARN."
  value       = aws_iam_role.deploy.arn
}

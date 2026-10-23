# Secrets live in SSM Parameter Store (standard tier = free; ADR 0008). Terraform creates them
# with placeholders and never touches the value again; Jeya sets real values with
# scripts/put_secrets.sh AFTER the first apply.
locals {
  secret_params = {
    admin_password_hash   = { type = "SecureString", description = "argon2id hash of the admin password" }
    jwt_secret            = { type = "SecureString", description = "HS256 signing key for API tokens" }
    vapid_private_key     = { type = "SecureString", description = "Web Push VAPID private key (base64url)" }
    vapid_subject         = { type = "String", description = "VAPID subject, mailto:<email>" }
    pagerduty_routing_key = { type = "SecureString", description = "PagerDuty Events v2 routing key ('unset' = off)" }
    healthchecks_ping_url = { type = "SecureString", description = "healthchecks.io ping URL ('unset' = off)" }
  }
}

resource "aws_ssm_parameter" "secret" {
  for_each    = local.secret_params
  name        = "/beacon/${each.key}"
  type        = each.value.type
  description = each.value.description
  value       = "unset"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "demo_healthy" {
  name        = "/beacon/demo/healthy"
  type        = "String"
  description = "Demo target health; flipped by the app's Break/Fix buttons"
  value       = "true"

  lifecycle {
    ignore_changes = [value]
  }
}

# Read at runtime (not an env var) to avoid a dependency cycle:
# API function -> function URL -> CloudFront -> domain -> API env.
resource "aws_ssm_parameter" "app_url" {
  name        = "/beacon/app_url"
  type        = "String"
  description = "Public URL of the Beacon app (CloudFront)"
  value       = "https://${aws_cloudfront_distribution.site.domain_name}"
}

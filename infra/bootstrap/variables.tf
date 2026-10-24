variable "region" {
  description = "Home region for Beacon."
  type        = string
  default     = "ap-south-1"
}

variable "github_repo" {
  description = "owner/name of the GitHub repository allowed to deploy (for reference and outputs)."
  type        = string
  default     = "JeyaViknan/beacon"
}

variable "github_oidc_sub_prefix" {
  description = <<-EOT
    Subject prefix GitHub puts in this repo's OIDC tokens. Repos using GitHub's immutable subject
    format embed the owner and repo IDs (owner@id/repo@id), so a deleted-and-recreated repo with the
    same name can never assume the role. Look it up with:
      gh api repos/<owner>/<repo>/actions/oidc/customization/sub --jq .sub_claim_prefix
  EOT
  type        = string
  default     = "repo:JeyaViknan@157094732/beacon@1431377621"
}

variable "alert_email" {
  description = "Email address for AWS Budget alerts."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly cost budget; alerts at 50% and 100% of actual spend."
  type        = string
  default     = "1"
}

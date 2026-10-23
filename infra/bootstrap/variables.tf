variable "region" {
  description = "Home region for Beacon."
  type        = string
  default     = "ap-south-1"
}

variable "github_repo" {
  description = "owner/name of the GitHub repository allowed to deploy."
  type        = string
  default     = "JeyaViknan/beacon"
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

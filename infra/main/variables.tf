variable "project" {
  type    = string
  default = "beacon"
}

variable "home_region" {
  description = "Region for everything except optional remote probes."
  type        = string
  default     = "ap-south-1"
}

variable "probe_regions" {
  description = "Regions that run a probe. Extra regions are opt-in (small cross-region cost, ADR 0006)."
  type        = list(string)
  default     = ["ap-south-1"]

  validation {
    condition     = length(var.probe_regions) > 0 && alltrue([for r in var.probe_regions : contains(["ap-south-1", "ap-southeast-1", "us-east-1"], r)])
    error_message = "probe_regions must be a non-empty subset of ap-south-1, ap-southeast-1, us-east-1."
  }
}

variable "alert_email" {
  description = "Jeya's email for product alerts and ops alarms (SNS email subscriptions)."
  type        = string
}

variable "app_version" {
  description = "Git SHA being deployed; shown in the app and /api/health."
  type        = string
  default     = "dev"
}

variable "dist_dir" {
  description = "Directory containing the Lambda zips built by scripts/build_lambdas.sh."
  type        = string
  default     = "../../dist"
}

variable "log_retention_days" {
  type    = number
  default = 7
}

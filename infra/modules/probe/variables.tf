variable "region" {
  description = "Region this probe runs in (must match the provider passed to the module)."
  type        = string
}

variable "home_region" {
  description = "Region of the DynamoDB table and the results queue."
  type        = string
}

variable "zip_path" {
  description = "Path to dist/probe.zip (hashed to detect code changes; uploaded directly when s3_bucket is null)."
  type        = string
}

variable "s3_bucket" {
  description = "Bucket holding the probe zip. Must be in the probe's region; null = upload the zip directly."
  type        = string
  default     = null
}

variable "s3_key" {
  description = "Key of the probe zip in s3_bucket."
  type        = string
  default     = null
}

variable "table_name" {
  type = string
}

variable "table_arn" {
  type = string
}

variable "queue_url" {
  type = string
}

variable "queue_arn" {
  type = string
}

variable "app_version" {
  type = string
}

variable "log_retention_days" {
  type    = number
  default = 7
}

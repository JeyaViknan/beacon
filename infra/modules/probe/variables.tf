variable "region" {
  description = "Region this probe runs in (must match the provider passed to the module)."
  type        = string
}

variable "home_region" {
  description = "Region of the DynamoDB table and the results queue."
  type        = string
}

variable "zip_path" {
  description = "Path to dist/probe.zip."
  type        = string
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

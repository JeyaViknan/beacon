# One probe module per supported region, switched on by var.probe_regions (ADR 0006).
locals {
  probe_common = {
    home_region        = var.home_region
    zip_path           = "${var.dist_dir}/probe.zip"
    table_name         = aws_dynamodb_table.beacon.name
    table_arn          = aws_dynamodb_table.beacon.arn
    queue_url          = aws_sqs_queue.results.url
    queue_arn          = aws_sqs_queue.results.arn
    app_version        = var.app_version
    log_retention_days = var.log_retention_days
  }
}

module "probe_mumbai" {
  source = "../modules/probe"
  count  = contains(var.probe_regions, "ap-south-1") ? 1 : 0

  region             = "ap-south-1"
  home_region        = local.probe_common.home_region
  zip_path           = local.probe_common.zip_path
  table_name         = local.probe_common.table_name
  table_arn          = local.probe_common.table_arn
  queue_url          = local.probe_common.queue_url
  queue_arn          = local.probe_common.queue_arn
  app_version        = local.probe_common.app_version
  log_retention_days = local.probe_common.log_retention_days
}

module "probe_singapore" {
  source    = "../modules/probe"
  count     = contains(var.probe_regions, "ap-southeast-1") ? 1 : 0
  providers = { aws = aws.singapore }

  region             = "ap-southeast-1"
  home_region        = local.probe_common.home_region
  zip_path           = local.probe_common.zip_path
  table_name         = local.probe_common.table_name
  table_arn          = local.probe_common.table_arn
  queue_url          = local.probe_common.queue_url
  queue_arn          = local.probe_common.queue_arn
  app_version        = local.probe_common.app_version
  log_retention_days = local.probe_common.log_retention_days
}

module "probe_virginia" {
  source    = "../modules/probe"
  count     = contains(var.probe_regions, "us-east-1") ? 1 : 0
  providers = { aws = aws.virginia }

  region             = "us-east-1"
  home_region        = local.probe_common.home_region
  zip_path           = local.probe_common.zip_path
  table_name         = local.probe_common.table_name
  table_arn          = local.probe_common.table_arn
  queue_url          = local.probe_common.queue_url
  queue_arn          = local.probe_common.queue_arn
  app_version        = local.probe_common.app_version
  log_retention_days = local.probe_common.log_retention_days
}

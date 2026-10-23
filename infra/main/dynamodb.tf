# Single table (ADR 0003). Provisioned capacity inside the always-free 25 RCU / 25 WCU:
# table 15/15 + GSI1 5/5 = 20/20.
resource "aws_dynamodb_table" "beacon" {
  name                        = "beacon"
  billing_mode                = "PROVISIONED"
  read_capacity               = 15
  write_capacity              = 15
  hash_key                    = "PK"
  range_key                   = "SK"
  deletion_protection_enabled = true

  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }
  attribute {
    name = "GSI1PK"
    type = "S"
  }
  attribute {
    name = "GSI1SK"
    type = "S"
  }

  global_secondary_index {
    name            = "GSI1"
    projection_type = "ALL"
    read_capacity   = 5
    write_capacity  = 5

    key_schema {
      attribute_name = "GSI1PK"
      key_type       = "HASH"
    }
    key_schema {
      attribute_name = "GSI1SK"
      key_type       = "RANGE"
    }
  }

  # Raw checks and rollups expire on their own; TTL deletes are free.
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }
}

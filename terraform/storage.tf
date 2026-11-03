# Three buckets: landing, released, quarantined.
resource "aws_s3_bucket" "incoming" {
  bucket        = "${var.name_prefix}-incoming"
  force_destroy = true
}

resource "aws_s3_bucket" "clean" {
  bucket        = "${var.name_prefix}-clean"
  force_destroy = true
}

resource "aws_s3_bucket" "quarantine" {
  bucket        = "${var.name_prefix}-quarantine"
  force_destroy = true
}

# Two tables: per-file verdicts and a hash cache / seed list.
resource "aws_dynamodb_table" "verdicts" {
  name         = "${var.name_prefix}-verdicts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "file_id"

  attribute {
    name = "file_id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "known_hashes" {
  name         = "${var.name_prefix}-known-hashes"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "sha256"

  attribute {
    name = "sha256"
    type = "S"
  }
}

# Seed the known EICAR hash so a brand-new scan can resolve it via the cache
# path too. The scanner also catches EICAR by content pattern, so this is a
# demonstration of the seed source, not a correctness dependency.
resource "aws_dynamodb_table_item" "eicar_seed" {
  table_name = aws_dynamodb_table.known_hashes.name
  hash_key   = aws_dynamodb_table.known_hashes.hash_key

  item = jsonencode({
    sha256     = { S = "275a021bbfb6489e54d471899f7db9d1663fc695ec2fe2a2c4538aabf651fd0f" }
    verdict    = { S = "malicious" }
    risk_score = { N = "100" }
    reasons    = { L = [{ S = "known-bad hash (EICAR test file)" }] }
    source     = { S = "seed" }
  })
}

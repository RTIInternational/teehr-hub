resource "aws_s3_bucket" "teehr_iceberg_warehouse" {
	bucket        = "${var.environment}-${var.project_name}-iceberg-warehouse"

	tags = {
		Name        = "${var.environment}-${var.project_name}-iceberg-warehouse"
		Environment = var.environment
		Project     = var.project_name
	}
}

resource "aws_s3_bucket_public_access_block" "teehr_iceberg_warehouse_public_access_block" {
    bucket = aws_s3_bucket.teehr_iceberg_warehouse.id

    block_public_acls        = true
    block_public_policy      = true
    # block_public_policy      = false
    ignore_public_acls       = true
    restrict_public_buckets  = true
    # restrict_public_buckets  = false
}

# resource "aws_s3_bucket_policy" "public_read" {
#   bucket = aws_s3_bucket.teehr_iceberg_warehouse.id

#   policy = jsonencode({
#     Version = "2012-10-17"
#     Statement = [
#       {
#         Effect = "Allow"
#         Principal = "*"
#         Action = "s3:GetObject"
#         Resource = "${aws_s3_bucket.teehr_iceberg_warehouse.arn}/*"
#       }
#     ]
#   })
# }


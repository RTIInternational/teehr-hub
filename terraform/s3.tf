data "aws_iam_policy_document" "prefect_job_trust_policy" {
    statement {
        effect  = "Allow"
        actions = ["sts:AssumeRoleWithWebIdentity"]

        principals {
            type        = "Federated"
            identifiers = [module.eks.oidc_provider_arn]
        }

        condition {
            test     = "StringEquals"
            variable = "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:sub"
            values   = ["system:serviceaccount:teehr-hub:prefect-job"]
        }
    }
}

resource "aws_iam_role" "prefect_job_irsa" {
    name               = "teehr-hub-prefect-job-irsa"
    assume_role_policy = data.aws_iam_policy_document.prefect_job_trust_policy.json
    tags               = {
        "teehr-hub/role" = "prefect-job"
    }
}

data "aws_iam_policy_document" "prefect_job_s3_rw" {
    statement {
        effect = "Allow"
        actions = [
            "s3:GetObject",
            "s3:PutObject",
            "s3:DeleteObject",
            "s3:ListBucket"
        ]
        resources = [
            aws_s3_bucket.teehr_iceberg_warehouse.arn,
            "${aws_s3_bucket.teehr_iceberg_warehouse.arn}/*"
        ]
    }
}

resource "aws_iam_policy" "prefect_job_s3_rw" {
    name   = "teehr-hub-prefect-job-s3-rw"
    policy = data.aws_iam_policy_document.prefect_job_s3_rw.json
}

resource "aws_iam_role_policy_attachment" "prefect_job_s3_rw" {
    role       = aws_iam_role.prefect_job_irsa.name
    policy_arn = aws_iam_policy.prefect_job_s3_rw.arn
}
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


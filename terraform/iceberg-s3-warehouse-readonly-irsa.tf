# Read-only access for Spark and Jupyter service accounts
data "aws_iam_policy_document" "iceberg_s3_warehouse_readonly_trust_policy" {
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
            values   = [
                "system:serviceaccount:teehr-hub:spark",
                "system:serviceaccount:teehr-hub:jupyter"
            ]
        }
    }
}

resource "aws_iam_role" "iceberg_s3_warehouse_readonly_irsa" {
    name               = "teehr-hub-iceberg-s3-warehouse-readonly-irsa"
    assume_role_policy = data.aws_iam_policy_document.iceberg_s3_warehouse_readonly_trust_policy.json
    tags               = {
        "teehr-hub/role" = "iceberg-s3-warehouse-readonly"
    }
}

data "aws_iam_policy_document" "iceberg_s3_warehouse_readonly" {
    statement {
        effect = "Allow"
        actions = [
            "s3:GetObject",
            "s3:ListBucket"
        ]
        resources = [
            aws_s3_bucket.teehr_iceberg_warehouse.arn,
            "${aws_s3_bucket.teehr_iceberg_warehouse.arn}/*"
        ]
    }
}

resource "aws_iam_policy" "iceberg_s3_warehouse_readonly" {
    name   = "teehr-hub-iceberg-s3-warehouse-readonly"
    policy = data.aws_iam_policy_document.iceberg_s3_warehouse_readonly.json
}

resource "aws_iam_role_policy_attachment" "iceberg_s3_warehouse_readonly" {
    role       = aws_iam_role.iceberg_s3_warehouse_readonly_irsa.name
    policy_arn = aws_iam_policy.iceberg_s3_warehouse_readonly.arn
}
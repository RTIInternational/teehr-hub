data "aws_iam_policy_document" "icechunk_s3_warehouse_rw" {
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket"
    ]
    resources = [
      aws_s3_bucket.teehr_icechunk_warehouse.arn,
      "${aws_s3_bucket.teehr_icechunk_warehouse.arn}/*"
    ]
  }
}

resource "aws_iam_policy" "icechunk_s3_warehouse_rw" {
  name   = "teehr-hub-icechunk-s3-warehouse-rw"
  policy = data.aws_iam_policy_document.icechunk_s3_warehouse_rw.json
}

resource "aws_iam_role_policy_attachment" "icechunk_s3_warehouse_rw" {
  role       = aws_iam_role.iceberg_s3_warehouse_irsa.name
  policy_arn = aws_iam_policy.icechunk_s3_warehouse_rw.arn
}

data "aws_iam_policy_document" "icechunk_s3_warehouse_readonly" {
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket"
    ]
    resources = [
      aws_s3_bucket.teehr_icechunk_warehouse.arn,
      "${aws_s3_bucket.teehr_icechunk_warehouse.arn}/*"
    ]
  }
}

resource "aws_iam_policy" "icechunk_s3_warehouse_readonly" {
  name   = "teehr-hub-icechunk-s3-warehouse-readonly"
  policy = data.aws_iam_policy_document.icechunk_s3_warehouse_readonly.json
}

resource "aws_iam_role_policy_attachment" "icechunk_s3_warehouse_readonly" {
  role       = aws_iam_role.iceberg_s3_warehouse_readonly_irsa.name
  policy_arn = aws_iam_policy.icechunk_s3_warehouse_readonly.arn
}

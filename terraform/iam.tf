resource "aws_iam_group" "teehr_hub_admins" {
  name = "TeehrHubAdmins"
}

resource "aws_iam_group_policy" "teehr_hub_admins_assume_role" {
  name  = "TeehrHubAdminsAssumeRole"
  group = aws_iam_group.teehr_hub_admins.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Resource = aws_iam_role.teehr_hub_admin.arn
      }
    ]
  })
}

resource "aws_iam_role" "teehr_hub_admin" {
  name = "${local.cluster_name}-teehr-hub-admin"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = [
            "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root",
          ]
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
  tags = {
    "teehr-hub/role" = "admin"
  }
}
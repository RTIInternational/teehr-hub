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

# GitHub Actions OIDC Provider
resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  
  tags = {
    "teehr-hub/purpose" = "github-actions-oidc"
  }
}



# IAM role for GitHub Actions to deploy with Garden
resource "aws_iam_role" "github_actions_garden_deploy" {
  name = "${local.cluster_name}-github-actions-garden-deploy"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github_actions.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:RTIInternational/teehr-hub:*"
          }
        }
      }
    ]
  })
  
  tags = {
    "teehr-hub/role" = "github-actions-garden-deploy"
    "teehr-hub/purpose" = "cicd"
  }
}

# Policy for GitHub Actions Garden deploy role
resource "aws_iam_role_policy" "github_actions_garden_deploy" {
  name = "github-actions-garden-deploy-policy"
  role = aws_iam_role.github_actions_garden_deploy.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "eks:DescribeCluster",
          "eks:AccessKubernetesApi"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = "sts:AssumeRole"
        Resource = aws_iam_role.teehr_hub_admin.arn
      }
    ]
  })
}
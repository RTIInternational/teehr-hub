# IRSA for Cluster Autoscaler

# 1. Trust policy for the Cluster Autoscaler service account
data "aws_iam_policy_document" "cluster_autoscaler_trust_policy" {
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
      values   = ["system:serviceaccount:kube-system:cluster-autoscaler"]
    }
  }
}


# Create the IAM policy document for Cluster Autoscaler
data "aws_iam_policy_document" "cluster_autoscaler" {
  statement {
    effect    = "Allow"
    actions   = [
      "autoscaling:DescribeAutoScalingGroups",
      "autoscaling:DescribeAutoScalingInstances",
      "autoscaling:DescribeLaunchConfigurations",
      "autoscaling:DescribeTags",
      "autoscaling:SetDesiredCapacity",
      "autoscaling:TerminateInstanceInAutoScalingGroup",
      "ec2:DescribeLaunchTemplateVersions",
      "ec2:DescribeInstanceTypes",
      "eks:DescribeNodegroup",
      "eks:ListNodegroups",
      "eks:ListClusters"
    ]
    resources = ["*"]
  }
}

# Create the IAM policy for Cluster Autoscaler
resource "aws_iam_policy" "cluster_autoscaler_policy" {
  name_prefix = "ClusterAutoscalerPolicy"
  description = "EKS cluster-autoscaler policy for cluster ${local.cluster_name}"
  policy      = data.aws_iam_policy_document.cluster_autoscaler.json
}

# 2. IAM role for Cluster Autoscaler
resource "aws_iam_role" "cluster_autoscaler_irsa" {
  name               = "ClusterAutoscalerIRSA"
  assume_role_policy = data.aws_iam_policy_document.cluster_autoscaler_trust_policy.json
  tags               = local.tags
}

# 3. Attach the Cluster Autoscaler policy
resource "aws_iam_role_policy_attachment" "cluster_autoscaler" {
  role       = aws_iam_role.cluster_autoscaler_irsa.name
  policy_arn = aws_iam_policy.cluster_autoscaler_policy.arn
}

# 4. Helm chart config:
# Set the serviceAccount.annotations in your Helm values:
# serviceAccount:
#   annotations:
#     eks.amazonaws.com/role-arn: arn:aws:iam::<account_id>:role/ClusterAutoscalerIRSA
#
# And set serviceAccount.name: cluster-autoscaler

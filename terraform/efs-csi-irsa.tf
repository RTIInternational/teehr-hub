# IRSA for EFS CSI Driver

# 1. Trust policy for the EFS CSI service account

data "aws_iam_policy_document" "efs_csi_trust_policy" {
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
      values   = ["system:serviceaccount:kube-system:efs-csi-controller-sa"]
    }
  }
}

# 2. IAM role for EFS CSI driver
resource "aws_iam_role" "efs_csi_irsa" {
  name               = "AmazonEKS_EFS_CSI_DriverRole"
  assume_role_policy = data.aws_iam_policy_document.efs_csi_trust_policy.json
  tags               = local.tags
}

# 3. Attach the EFS CSI driver policy
resource "aws_iam_role_policy_attachment" "efs_csi_driver" {
  role       = aws_iam_role.efs_csi_irsa.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonElasticFileSystemClientFullAccess"
}

# 4. Pass the role ARN to the EKS addon (update your EKS module's addons block)
# addons = {
#   aws-efs-csi-driver = {
#     resolve_conflicts_on_create = "OVERWRITE"
#     resolve_conflicts_on_update = "OVERWRITE"
#     service_account_role_arn    = aws_iam_role.efs_csi_irsa.arn
#   }
#   ...existing code...
# }

# IRSA for EBS CSI Driver

# 1. Trust policy for the EBS CSI service account
data "aws_iam_policy_document" "ebs_csi_trust_policy" {
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
      values   = ["system:serviceaccount:kube-system:ebs-csi-controller-sa"]
    }
  }
}

# 2. IAM role for EBS CSI driver
resource "aws_iam_role" "ebs_csi_irsa" {
  name               = "AmazonEKS_EBS_CSI_DriverRole"
  assume_role_policy = data.aws_iam_policy_document.ebs_csi_trust_policy.json
  tags               = local.tags
}

# 3. Attach the EBS CSI driver policy
resource "aws_iam_role_policy_attachment" "ebs_csi_driver" {
  role       = aws_iam_role.ebs_csi_irsa.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

# 4. Pass the role ARN to the EKS addon (update your EKS module's addons block)
# addons = {
#   aws-ebs-csi-driver = {
#     resolve_conflicts_on_create = "OVERWRITE"
#     resolve_conflicts_on_update = "OVERWRITE"
#     service_account_role_arn    = aws_iam_role.ebs_csi_irsa.arn
#   }
#   ...existing code...
# }

output "nfs_server_dns" {
  value = aws_efs_file_system.datadir.dns_name
}

output "cluster_arn" {
  value = module.eks.cluster_arn
}

output "github_actions_role_arn" {
  value       = aws_iam_role.github_actions_garden_deploy.arn
  description = "ARN of the GitHub Actions role for Garden deployments"
}

output "github_actions_role_name" {
  value       = aws_iam_role.github_actions_garden_deploy.name
  description = "Name of the GitHub Actions role for Garden deployments"
}

output "s3_vpc_endpoint_id" {
  value       = aws_vpc_endpoint.s3.id
  description = "ID of the S3 VPC Gateway Endpoint for cost-free S3 access"
}
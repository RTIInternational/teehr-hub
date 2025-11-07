output "nfs_server_dns" {
  value = aws_efs_file_system.datadir.dns_name
}

output "cluster_arn" {
  value = module.eks.cluster_arn
}
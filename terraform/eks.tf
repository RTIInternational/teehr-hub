locals {
  eks_node_group_defaults = {
    ami_type       = "AL2_x86_64"
    use_name_prefix = true
    block_device_mappings = {
      xvda = {
        device_name = "/dev/xvda"
        ebs = {
          volume_size           = 80
          volume_type           = "gp3"
          iops                  = 3000
          throughput            = 150
          delete_on_termination = true
        }
      }
    }
    vpc_security_group_ids = [ aws_security_group.efs-sg.id ]
    subnet_ids = [module.vpc.private_subnets[0]]
    iam_role_additional_policies = {
      ecr_power_user          = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser"
    }
    metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "optional"
        http_put_response_hop_limit = 1
      }
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.0"

  name                   = var.cluster_name
  kubernetes_version     = var.cluster_version

  endpoint_public_access = true
  authentication_mode    = "API_AND_CONFIG_MAP"

  # Optional: Adds the current caller identity as an administrator via cluster access entry
  # enable_cluster_creator_admin_permissions = true

  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets

  iam_role_name   = "${local.cluster_name}-cluster-role"
  node_security_group_name = "${local.cluster_name}-node-security-group"
  security_group_name = "${local.cluster_name}-cluster-security-group"

  access_entries = {
    admin = {
      principal_arn     = aws_iam_role.teehr_hub_admin.arn
      type              = "STANDARD"
      policy_associations = {
        admin_policy = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = {
            type = "cluster"
          }
        }
      }
    }
  }

  addons = {
    coredns = {
      resolve_conflicts_on_create = "OVERWRITE"
      resolve_conflicts_on_update = "OVERWRITE"
    }
    kube-proxy = {
      resolve_conflicts_on_create = "OVERWRITE"
      resolve_conflicts_on_update = "OVERWRITE"
    }
    vpc-cni = {
      # before_compute = true
    }
    aws-ebs-csi-driver = {
      resolve_conflicts_on_create = "OVERWRITE"
      resolve_conflicts_on_update = "OVERWRITE"
      service_account_role_arn    = aws_iam_role.ebs_csi_irsa.arn
    }
    aws-efs-csi-driver = {
      resolve_conflicts_on_create = "OVERWRITE"
      resolve_conflicts_on_update = "OVERWRITE"
      service_account_role_arn    = aws_iam_role.efs_csi_irsa.arn
    }
    # eks-pod-identity-agent = {
    #   resolve_conflicts_on_create = "OVERWRITE"
    #   resolve_conflicts_on_update = "OVERWRITE"
    # }
  }

  # Extend cluster security group rules
  security_group_additional_rules = {
    egress_all = {
      description      = "Cluster all egress"
      protocol         = "-1"
      from_port        = 0
      to_port          = 0
      type             = "egress"
      cidr_blocks      = ["0.0.0.0/0"]
      ipv6_cidr_blocks = ["::/0"]
    }
  }

  # Extend node-to-node security group rules
  node_security_group_additional_rules = {
    ingress_self_all = {
      description = "Node to node all ports/protocols"
      protocol    = "-1"
      from_port   = 0
      to_port     = 0
      type        = "ingress"
      self        = true
    }
  }

  eks_managed_node_groups = {
    core-a = merge(local.eks_node_group_defaults, {
      name            = "core-a"
      iam_role_name   = "${local.cluster_name}-core"

      min_size        = 1
      max_size        = 6
      desired_size    = 1

      instance_types  = ["r5.xlarge"]
      labels = {
        "teehr-hub/nodegroup-name"         = "core-a"
        "hub.jupyter.org/node-purpose"     = "core"
        "k8s.dask.org/node-purpose"        = "core"
        "node.kubernetes.io/instance-type" = "r5.xlarge"
      }
      taints = {}
      tags = {
        "k8s.io/cluster-autoscaler/enabled"                                              = "true"
        "k8s.io/cluster-autoscaler/${local.cluster_name}"                                = "owned"
        "k8s.io/cluster-autoscaler/node-template/label/hub.jupyter.org/node-purpose"     = "core"
        "k8s.io/cluster-autoscaler/node-template/label/k8s.dask.org/node-purpose"        = "core"
        "k8s.io/cluster-autoscaler/node-template/label/node.kubernetes.io/instance-type" = "r5.xlarge"
        "teehr-hub/nodegroup-name"                                                       = "core-a"
      }
    })

    nb-r5-xlarge = merge(local.eks_node_group_defaults, {
      name            = "nb-r5-xlarge"
      iam_role_name   = "${local.cluster_name}-nb-r5-xlarge"

      min_size        = 0
      max_size        = 400
      desired_size    = 0

      instance_types  = ["r5.xlarge"]
      labels = {
        "teehr-hub/nodegroup-name"         = "nb-r5-xlarge"
        "hub.jupyter.org/node-purpose"     = "user"
        "k8s.dask.org/node-purpose"        = "scheduler"
        "node.kubernetes.io/instance-type" = "r5.xlarge"
      }
      taints = {
        dedicated = {
          key    = "hub.jupyter.org/dedicated"
          value  = "user"
          effect = "NO_SCHEDULE"
        }
        dedicated_alt = {
          key    = "hub.jupyter.org_dedicated"
          value  = "user"
          effect = "NO_SCHEDULE"
        }
      }
      tags = {
        "k8s.io/cluster-autoscaler/enabled"                                              = "true"
        "k8s.io/cluster-autoscaler/${local.cluster_name}"                                = "owned"
        "k8s.io/cluster-autoscaler/node-template/label/hub.jupyter.org/node-purpose"     = "user"
        "k8s.io/cluster-autoscaler/node-template/label/k8s.dask.org/node-purpose"        = "scheduler"
        "k8s.io/cluster-autoscaler/node-template/label/node.kubernetes.io/instance-type" = "r5.xlarge"
        "k8s.io/cluster-autoscaler/node-template/taint/hub.jupyter.org/dedicated"        = "user:NoSchedule"
        "k8s.io/cluster-autoscaler/node-template/taint/hub.jupyter.org_dedicated"        = "user:NoSchedule"
        "teehr-hub/nodegroup-name"                                                       = "nb-r5-xlarge"
      }
    })

    nb-r5-4xlarge = merge(local.eks_node_group_defaults, {
      name            = "nb-r5-4xlarge"
      iam_role_name   = "${local.cluster_name}-nb-r5-4xlarge"

      min_size        = 0
      max_size        = 400
      desired_size    = 0

      instance_types  = ["r5.4xlarge"]
      labels = {
        "teehr-hub/nodegroup-name"         = "nb-r5-4xlarge"
        "hub.jupyter.org/node-purpose"     = "user"
        "k8s.dask.org/node-purpose"        = "scheduler"
        "node.kubernetes.io/instance-type" = "r5.4xlarge"
      }
      taints = {
        dedicated = {
          key    = "hub.jupyter.org/dedicated"
          value  = "user"
          effect = "NO_SCHEDULE"
        }
        dedicated_alt = {
          key    = "hub.jupyter.org_dedicated"
          value  = "user"
          effect = "NO_SCHEDULE"
        }
      }
      tags = {
        "k8s.io/cluster-autoscaler/enabled"                                              = "true"
        "k8s.io/cluster-autoscaler/${local.cluster_name}"                                = "owned"
        "k8s.io/cluster-autoscaler/node-template/label/hub.jupyter.org/node-purpose"     = "user"
        "k8s.io/cluster-autoscaler/node-template/label/k8s.dask.org/node-purpose"        = "scheduler"
        "k8s.io/cluster-autoscaler/node-template/label/node.kubernetes.io/instance-type" = "r5.4xlarge"
        "k8s.io/cluster-autoscaler/node-template/taint/hub.jupyter.org/dedicated"        = "user:NoSchedule"
        "k8s.io/cluster-autoscaler/node-template/taint/hub.jupyter.org_dedicated"        = "user:NoSchedule"
        "teehr-hub/nodegroup-name"                                                       = "nb-r5-4xlarge"
      }
    })

    spark-r5-4xlarge = merge(local.eks_node_group_defaults, {
      name            = "spark-r5-4xlarge"
      iam_role_name   = "${local.cluster_name}-spark-r5-4xlarge"

      min_size        = 0
      max_size        = 400
      desired_size    = 0

      instance_types  = ["r5.4xlarge"]
      labels = {
        "teehr-hub/nodegroup-name"         = "spark-r5-4xlarge"
        "node.kubernetes.io/instance-type" = "r5.4xlarge"
      }
      taints = {
        dedicated = {
          key    = "teehr-hub/dedicated"
          value  = "worker"
          effect = "NO_SCHEDULE"
        }
        dedicated_alt = {
          key    = "teehr-hub_dedicated"
          value  = "worker"
          effect = "NO_SCHEDULE"
        }
      }
      tags = {
        "k8s.io/cluster-autoscaler/enabled"                                                 = "true"
        "k8s.io/cluster-autoscaler/${local.cluster_name}"                                   = "owned"
        "k8s.io/cluster-autoscaler/node-template/label/teehr-hub/node-purpose/node-purpose" = "worker"
        "k8s.io/cluster-autoscaler/node-template/label/node.kubernetes.io/instance-type"    = "r5.4xlarge"
        "k8s.io/cluster-autoscaler/node-template/taint/teehr-hub/dedicated"                 = "worker:NoSchedule"
        "k8s.io/cluster-autoscaler/node-template/taint/teehr-hub_dedicated"                 = "worker:NoSchedule"
        "teehr-hub/nodegroup-name"                                                          = "spark-r5-4xlarge"
      }
    })

    spark-r5-4xlarge-spot = merge(local.eks_node_group_defaults, {
      name            = "spark-r5-4xlarge-spot"
      iam_role_name   = "${local.cluster_name}-spark-r5-4xlarge-spot"

      capacity_type   = "SPOT"

      min_size        = 0
      max_size        = 400
      desired_size    = 0

      instance_types  = ["r5.4xlarge", "r5a.4xlarge", "r5n.4xlarge"]
      labels = {
        "teehr-hub/nodegroup-name"         = "spark-r5-4xlarge-spot"
        "node.kubernetes.io/instance-type" = "r5.4xlarge"
      }
      taints = {
        dedicated = {
          key    = "teehr-hub/dedicated"
          value  = "worker"
          effect = "NO_SCHEDULE"
        }
        dedicated_alt = {
          key    = "teehr-hub_dedicated"
          value  = "worker"
          effect = "NO_SCHEDULE"
        }
      }
      tags = {
        "k8s.io/cluster-autoscaler/enabled"                                              = "true"
        "k8s.io/cluster-autoscaler/${local.cluster_name}"                                = "owned"
        "k8s.io/cluster-autoscaler/node-template/label/node.kubernetes.io/instance-type" = "r5.4xlarge"
        "k8s.io/cluster-autoscaler/node-template/taint/teehr-hub/dedicated"             = "worker:NoSchedule"
        "k8s.io/cluster-autoscaler/node-template/taint/teehr-hub_dedicated"             = "worker:NoSchedule"
        "teehr-hub/nodegroup-name"                                                       = "spark-r5-4xlarge-spot"
      }
    })

  }

  tags = local.tags
}
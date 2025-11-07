resource "aws_ecr_repository" "repos" {
  for_each = { for repo in local.ecr_repos : repo.name => repo }
  name     = each.value.name
  image_scanning_configuration {
    scan_on_push = true
  }
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true
  encryption_configuration {
    encryption_type = "KMS"
  }
  lifecycle {
    prevent_destroy = false
  }
  tags = local.tags
}

resource "aws_ecr_lifecycle_policy" "repos" {
  for_each   = aws_ecr_repository.repos
  repository = each.key

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only the last N images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = lookup({ for repo in local.ecr_repos : repo.name => repo.max_image_count }, each.key, 10)
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
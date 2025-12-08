locals {
#   ecr_policy = [
#     {
#       actions = [
#         "ecr:GetAuthorizationToken",
#         "ecr:BatchCheckLayerAvailability",
#         "ecr:GetDownloadUrlForLayer",
#         "ecr:GetRepositoryPolicy",
#         "ecr:DescribeRepositories",
#         "ecr:ListImages",
#         "ecr:DescribeImages",
#         "ecr:BatchGetImage",
#         "ecr:GetLifecyclePolicy",
#         "ecr:GetLifecyclePolicyPreview",
#         "ecr:ListTagsForResource",
#         "ecr:DescribeImageScanFindings",
#         "ecr:InitiateLayerUpload",
#         "ecr:UploadLayerPart",
#         "ecr:CompleteLayerUpload",
#         "ecr:PutImage"
#       ]
#       resources = []
#     },
#     {
#       actions   = ["ecr:GetAuthorizationToken"]
#       resources = ["*"]
#     }
#   ]

  ecr_repos = [
    {
      name            = "teehr-hub/jupyter-driver"
      max_image_count = 10
    },
    {
      name            = "teehr-hub/spark-executor"
      max_image_count = 10
    },
    {
      name            = "teehr-hub/teehr-prefect"
      max_image_count = 10
    },
    {
      name            = "teehr-hub/panel-dashboards"
      max_image_count = 10
    },
    {
      name            = "teehr-hub/teehr-api"
      max_image_count = 10
    },
    {
      name            = "teehr-hub/teehr-dashboards"
      max_image_count = 10
    },
    {
      name            = "teehr-hub/teehr-frontend"
      max_image_count = 10
    }
  ]
}

variable "aws_region" {
  type    = string
  default = "ap-south-1"
}
variable "project_name" {
  type    = string
  default = "cloudpilot-demo"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.project_name))
    error_message = "Use 3–31 lowercase letters, numbers or hyphens, starting with a letter."
  }
}
resource "aws_ecr_repository" "app" {
  for_each             = toset(["backend", "frontend"])
  name                 = "${var.project_name}/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  encryption_configuration {
    encryption_type = "AES256"
  }
  image_scanning_configuration {
    scan_on_push = true
  }
}
resource "aws_ecr_lifecycle_policy" "untagged" {
  for_each   = aws_ecr_repository.app
  repository = each.value.name
  policy = jsonencode({ rules = [{ rulePriority = 1, description = "Expire untagged images after 14 days", selection = {
    tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = 14
  }, action = { type = "expire" } }] })
}
# Only the secret container is managed by Terraform. Values never enter its state.
resource "aws_secretsmanager_secret" "runtime" {
  name                    = "${var.project_name}/runtime"
  description             = "Demo gateway bcrypt credentials and Qwen API configuration; populate outside Terraform."
  recovery_window_in_days = 7
}
output "aws_region" { value = var.aws_region }
output "backend_repository_url" { value = aws_ecr_repository.app["backend"].repository_url }
output "frontend_repository_url" { value = aws_ecr_repository.app["frontend"].repository_url }
output "runtime_secret_arn" { value = aws_secretsmanager_secret.runtime.arn }

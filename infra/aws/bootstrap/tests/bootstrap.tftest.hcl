mock_provider "aws" {}
run "registry_and_secret_boundary" {
  command = apply
  assert {
    condition     = aws_ecr_repository.app["backend"].image_tag_mutability == "IMMUTABLE" && aws_ecr_repository.app["frontend"].image_tag_mutability == "IMMUTABLE"
    error_message = "Versioned image tags must be immutable for predictable rollback."
  }
  assert {
    condition     = aws_ecr_repository.app["backend"].force_delete == false && aws_secretsmanager_secret.runtime.recovery_window_in_days == 7
    error_message = "Registry deletion and secret recovery must retain their safeguards."
  }
}

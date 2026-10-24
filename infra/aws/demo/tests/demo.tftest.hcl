mock_provider "aws" {
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/mock-demo" }
  }
  mock_resource "aws_sns_topic" {
    defaults = { arn = "arn:aws:sns:ap-south-1:123456789012:mock-operations" }
  }
  mock_resource "aws_ebs_volume" {
    defaults = { id = "vol-0123456789abcdef0", arn = "arn:aws:ec2:ap-south-1:123456789012:volume/vol-0123456789abcdef0" }
  }
  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:ap-south-1:123456789012:log-group:/cloudpilot-demo/containers" }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_availability_zones" {
    defaults = { names = ["ap-south-1a"] }
  }
  mock_data "aws_ssm_parameter" {
    defaults = { value = "ami-0123456789abcdef0" }
  }
}
variables {
  domain_name        = "demo.example.com"
  acme_email         = "founder@example.com"
  backend_image      = "123456789012.dkr.ecr.ap-south-1.amazonaws.com/cloudpilot-demo/backend:release-1"
  frontend_image     = "123456789012.dkr.ecr.ap-south-1.amazonaws.com/cloudpilot-demo/frontend:release-1"
  runtime_secret_arn = "arn:aws:secretsmanager:ap-south-1:123456789012:secret:cloudpilot-demo/runtime-AbCdEf"
}
run "protected_persistent_demo" {
  command = plan
  assert {
    condition     = aws_instance.demo.metadata_options[0].http_tokens == "required" && aws_instance.demo.metadata_options[0].http_put_response_hop_limit == 1
    error_message = "Require IMDSv2 and prevent bridge-network containers accessing instance credentials."
  }
  assert {
    condition     = aws_ebs_volume.data.encrypted && aws_instance.demo.root_block_device[0].encrypted && aws_volume_attachment.data.stop_instance_before_detaching
    error_message = "Encrypt both disks and stop the old host before detaching persistent data."
  }
  assert {
    condition     = aws_vpc_security_group_ingress_rule.http.from_port == 80 && alltrue([for rule in aws_vpc_security_group_ingress_rule.https : rule.from_port == 443])
    error_message = "Only HTTP certificate validation/redirects and authenticated HTTPS may be exposed."
  }
  assert {
    condition     = local.runtime_policy_statements[0].Resource == var.runtime_secret_arn && contains(local.runtime_policy_statements[2].Resource, "arn:aws:ecr:ap-south-1:123456789012:repository/cloudpilot-demo/backend")
    error_message = "The instance must be restricted to its runtime secret and exact image repositories."
  }
  assert {
    condition     = aws_backup_vault.demo.name == one(aws_backup_plan.demo.rule).target_vault_name
    error_message = "Daily backup rules must target the configured backup vault."
  }
}
run "reject_latest_image" {
  command = plan
  variables {
    backend_image = "123456789012.dkr.ecr.ap-south-1.amazonaws.com/cloudpilot-demo/backend:latest"
  }
  expect_failures = [var.backend_image]
}

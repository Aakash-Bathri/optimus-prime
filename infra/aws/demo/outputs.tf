output "demo_url" { value = "https://${var.domain_name}" }
output "public_ip" { value = aws_eip.demo.public_ip }
output "instance_id" { value = aws_instance.demo.id }
output "data_volume_id" { value = aws_ebs_volume.data.id }
output "region" { value = var.aws_region }
output "ssm_connect_command" { value = "aws ssm start-session --region ${var.aws_region} --target ${aws_instance.demo.id}" }
output "log_group" { value = aws_cloudwatch_log_group.app.name }
output "operations_topic_arn" {
  value       = aws_sns_topic.operations.arn
  description = "Subscribe via the AWS console and confirm the subscription to receive infrastructure alarms."
}

output "ami_id" { value = aws_instance.demo.ami }

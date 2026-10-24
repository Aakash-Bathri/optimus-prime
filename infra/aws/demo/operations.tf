resource "aws_backup_vault" "demo" { name = "${var.project_name}-data" }
resource "aws_iam_role" "backup" {
  name_prefix = "${var.project_name}-backup-"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "backup.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}
resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}
resource "aws_backup_plan" "demo" {
  name = "${var.project_name}-daily"
  rule {
    rule_name         = "daily-encrypted-data-volume"
    target_vault_name = aws_backup_vault.demo.name
    schedule          = "cron(0 3 * * ? *)"
    start_window      = 60
    completion_window = 180
    lifecycle { delete_after = var.backup_retention_days }
  }
}
resource "aws_backup_selection" "data" {
  name         = "${var.project_name}-data"
  plan_id      = aws_backup_plan.demo.id
  iam_role_arn = aws_iam_role.backup.arn
  resources    = [aws_ebs_volume.data.arn]
  depends_on   = [aws_iam_role_policy_attachment.backup]
}
resource "aws_sns_topic" "operations" { name = "${var.project_name}-operations" }
resource "aws_cloudwatch_metric_alarm" "status" {
  alarm_name          = "${var.project_name}-instance-status"
  alarm_description   = "EC2 status check failure; subscribe to the operations SNS topic to receive notifications."
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "missing"
  dimensions          = { InstanceId = aws_instance.demo.id }
  alarm_actions       = [aws_sns_topic.operations.arn]
  ok_actions          = [aws_sns_topic.operations.arn]
}
resource "aws_cloudwatch_metric_alarm" "cpu" {
  alarm_name          = "${var.project_name}-high-cpu"
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  comparison_operator = "GreaterThanThreshold"
  threshold           = 85
  treat_missing_data  = "missing"
  dimensions          = { InstanceId = aws_instance.demo.id }
  alarm_actions       = [aws_sns_topic.operations.arn]
}

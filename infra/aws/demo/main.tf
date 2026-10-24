data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" { state = "available" }
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}
locals {
  az       = data.aws_availability_zones.available.names[0]
  registry = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
  # Preserve nested repository names when constructing least-privilege IAM ARNs.
  repository_paths = toset([for image in [var.backend_image, var.frontend_image] : split("@", split(":", join("/", slice(split("/", image), 1, length(split("/", image)))))[0])[0]])
}
resource "aws_vpc" "demo" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = var.project_name }
}
resource "aws_internet_gateway" "demo" { vpc_id = aws_vpc.demo.id }
resource "aws_subnet" "demo" {
  vpc_id                  = aws_vpc.demo.id
  cidr_block              = "10.42.1.0/24"
  availability_zone       = local.az
  map_public_ip_on_launch = false
}
resource "aws_route_table" "demo" {
  vpc_id = aws_vpc.demo.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.demo.id
  }
}
resource "aws_route_table_association" "demo" {
  subnet_id      = aws_subnet.demo.id
  route_table_id = aws_route_table.demo.id
}
resource "aws_security_group" "demo" {
  name_prefix = "${var.project_name}-"
  description = "Only the HTTPS gateway and HTTP certificate validation; management uses SSM."
  vpc_id      = aws_vpc.demo.id
}
resource "aws_vpc_security_group_ingress_rule" "http" {
  security_group_id = aws_security_group.demo.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  description       = "ACME HTTP-01 validation and HTTPS redirects; app never served on HTTP."
}
resource "aws_vpc_security_group_ingress_rule" "https" {
  for_each          = toset(var.https_allowed_cidrs)
  security_group_id = aws_security_group.demo.id
  cidr_ipv4         = each.value
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}
resource "aws_vpc_security_group_egress_rule" "outbound" {
  security_group_id = aws_security_group.demo.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "ECR, SSM, OS packages, ACME, logging and the configured Qwen endpoint."
}
resource "aws_iam_role" "instance" {
  name_prefix = "${var.project_name}-ec2-"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" }, Action = "sts:AssumeRole"
  }] })
}
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_cloudwatch_log_group" "app" {
  name              = "/${var.project_name}/containers"
  retention_in_days = 14
}
locals {
  runtime_policy_statements = [
    { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = var.runtime_secret_arn },
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"],
    Resource = [for repository in local.repository_paths : "arn:aws:ecr:${var.aws_region}:${data.aws_caller_identity.current.account_id}:repository/${repository}"] },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.app.arn}:*" }
  ]
}
resource "aws_iam_role_policy" "runtime" {
  role   = aws_iam_role.instance.id
  policy = jsonencode({ Version = "2012-10-17", Statement = local.runtime_policy_statements })
}
resource "aws_iam_instance_profile" "demo" { role = aws_iam_role.instance.name }
resource "aws_ebs_volume" "data" {
  availability_zone = local.az
  size              = var.data_volume_gib
  type              = "gp3"
  encrypted         = true
  tags              = { Name = "${var.project_name}-data" }
  lifecycle { prevent_destroy = true }
}
resource "aws_instance" "demo" {
  ami                         = coalesce(var.ami_id, nonsensitive(data.aws_ssm_parameter.al2023.value))
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.demo.id
  vpc_security_group_ids      = [aws_security_group.demo.id]
  iam_instance_profile        = aws_iam_instance_profile.demo.name
  associate_public_ip_address = true
  user_data_replace_on_change = true
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }
  credit_specification {
    cpu_credits = "standard"
  }
  root_block_device {
    volume_size           = 20
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }
  user_data_base64 = base64gzip(templatefile("${path.module}/templates/cloud-init.sh.tftpl", {
    volume_id = replace(aws_ebs_volume.data.id, "-", "")
    compose = base64encode(templatefile("${path.module}/templates/compose.yaml.tftpl", {
      backend_image  = var.backend_image
      frontend_image = var.frontend_image
      domain_name    = var.domain_name
      region         = var.aws_region
      log_group      = aws_cloudwatch_log_group.app.name
    }))
    caddyfile = base64encode(templatefile("${path.module}/templates/Caddyfile.tftpl", {
      domain_name = var.domain_name, acme_email = var.acme_email
    }))
    configuration = base64encode(jsonencode({
      region = var.aws_region, secret_arn = var.runtime_secret_arn, registry = local.registry
    }))
    secret_loader = filebase64("${path.module}/templates/load-secrets.py")
    deploy_script = filebase64("${path.module}/templates/deploy.sh")
    backup_script = filebase64("${path.module}/templates/backup.py")
  }))
  tags       = { Name = var.project_name }
  depends_on = [aws_route_table_association.demo, aws_iam_role_policy.runtime, aws_iam_role_policy_attachment.ssm]
  lifecycle {
    precondition {
      condition     = alltrue([for image in [var.backend_image, var.frontend_image] : startswith(image, "${local.registry}/")]) && startswith(var.runtime_secret_arn, "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:")
      error_message = "Images and runtime secret must belong to this AWS account and region."
    }
  }
}
resource "aws_volume_attachment" "data" {
  stop_instance_before_detaching = true
  device_name                    = "/dev/sdf"
  volume_id                      = aws_ebs_volume.data.id
  instance_id                    = aws_instance.demo.id
}
resource "aws_eip" "demo" { domain = "vpc" }
resource "aws_eip_association" "demo" {
  instance_id   = aws_instance.demo.id
  allocation_id = aws_eip.demo.id
}
resource "aws_route53_record" "demo" {
  count   = var.route53_zone_id == null ? 0 : 1
  zone_id = var.route53_zone_id
  name    = var.domain_name
  type    = "A"
  ttl     = 300
  records = [aws_eip.demo.public_ip]
}

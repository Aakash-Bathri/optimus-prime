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
variable "domain_name" {
  description = "Public DNS hostname you own, without https://. Must resolve to the output Elastic IP for automatic HTTPS."
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9.-]*[a-z0-9])?\\.[a-z]{2,}$", var.domain_name)) && !strcontains(var.domain_name, "..")
    error_message = "Provide a lowercase public hostname such as demo.yourcompany.com."
  }
}
variable "acme_email" {
  type        = string
  description = "Email for certificate expiration and ACME account notices."
  validation {
    condition     = can(regex("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$", var.acme_email))
    error_message = "Provide a valid email address."
  }
}
variable "route53_zone_id" {
  description = "Optional existing public Route53 zone. If null, create the A record yourself at your DNS provider."
  type        = string
  default     = null
}
variable "backend_image" {
  description = "Immutable private ECR backend image tag or digest from bootstrap, in this account and region."
  type        = string
  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.[a-z0-9-]+\\.amazonaws\\.com/[a-z0-9/_-]+(:[A-Za-z0-9_.-]+|@sha256:[a-f0-9]{64})$", var.backend_image)) && !endswith(var.backend_image, ":latest")
    error_message = "Use a private ECR image with a versioned tag or sha256 digest; latest is not allowed."
  }
}
variable "frontend_image" {
  type        = string
  description = "Immutable private ECR frontend image tag or digest from bootstrap, in this account and region."
  validation {
    condition     = can(regex("^[0-9]{12}\\.dkr\\.ecr\\.[a-z0-9-]+\\.amazonaws\\.com/[a-z0-9/_-]+(:[A-Za-z0-9_.-]+|@sha256:[a-f0-9]{64})$", var.frontend_image)) && !endswith(var.frontend_image, ":latest")
    error_message = "Use a private ECR image with a versioned tag or sha256 digest; latest is not allowed."
  }
}
variable "runtime_secret_arn" {
  description = "Bootstrap runtime secret ARN. Populate its JSON value before starting the app."
  type        = string
  validation {
    condition     = can(regex("^arn:aws:secretsmanager:[a-z0-9-]+:[0-9]{12}:secret:", var.runtime_secret_arn))
    error_message = "Use the Secrets Manager ARN from bootstrap outputs."
  }
}
variable "instance_type" {
  type    = string
  default = "t3.medium"
  validation {
    condition     = contains(["t3.medium", "t3.large", "t3.xlarge"], var.instance_type)
    error_message = "Choose a supported x86 instance with at least 4 GiB memory."
  }
}
variable "ami_id" {
  description = "Optional pinned Amazon Linux 2023 x86_64 AMI; otherwise the current regional AL2023 AMI is used."
  type        = string
  default     = null
}
variable "https_allowed_cidrs" {
  description = "IPv4 ranges allowed to reach the password-protected HTTPS gateway. Narrow for private demos if desired."
  type        = list(string)
  default     = ["0.0.0.0/0"]
  validation {
    condition     = length(var.https_allowed_cidrs) > 0 && alltrue([for cidr in var.https_allowed_cidrs : can(cidrnetmask(cidr))])
    error_message = "Provide at least one valid IPv4 CIDR."
  }
}
variable "data_volume_gib" {
  type    = number
  default = 30
  validation {
    condition     = var.data_volume_gib >= 20 && floor(var.data_volume_gib) == var.data_volume_gib
    error_message = "Use an integer volume size of at least 20 GiB."
  }
}
variable "backup_retention_days" {
  type    = number
  default = 7
  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 35 && floor(var.backup_retention_days) == var.backup_retention_days
    error_message = "Choose 1–35 days of backup retention."
  }
}

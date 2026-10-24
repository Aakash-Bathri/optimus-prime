terraform {
  required_version = ">= 1.10, < 2.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.70.0"
    }
  }
}

provider "aws" {
  region                      = "us-east-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    ec2 = "http://127.0.0.1:4566"
    sts = "http://127.0.0.1:4566"
  }
}

variable "api_instance_type" {
  description = "Demo production API instance type; CloudPilot proposes m5.xlarge after checking demand."
  type        = string
  default     = "m5.2xlarge"
  validation {
    condition     = contains(["m5.large", "m5.xlarge", "m5.2xlarge"], var.api_instance_type)
    error_message = "Use one of the three explicitly supported demo sizes."
  }
}

resource "aws_instance" "production_api" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = var.api_instance_type

  tags = {
    Name               = "cloudpilot-production-api"
    CloudPilotDemo     = "true"
    CloudPilotId       = "demo-api-01"
    Management         = "terraform"
    Environment        = "production"
    Team               = "platform"
    Owner              = "demo-engineer"
    IllustrativeRegion = "Noida"
  }
}

output "api_instance_id" {
  description = "LocalStack instance corresponding to the mapped Terraform resource."
  value       = aws_instance.production_api.id
}

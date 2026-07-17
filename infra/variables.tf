variable "aws_region" {
  description = "AWS region to deploy ShopSense AI"
  type        = string
  default     = "ap-south-1"   # Mumbai — closest to you
}

variable "project_name" {
  description = "Project name used for tagging and naming all resources"
  type        = string
  default     = "shopsense-ai"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "production"
}

variable "instance_type" {
  description = "EC2 instance type — t3.medium gives 2 vCPU + 4GB RAM for Ollama on CPU"
  type        = string
  default     = "t3.medium"
}

variable "ami_id" {
  description = "Ubuntu 22.04 LTS AMI for ap-south-1"
  type        = string
  default     = "ami-0f58b397bc5c1f2e8"   # Ubuntu 22.04 LTS — ap-south-1
}

variable "key_pair_name" {
  description = "EC2 Key Pair name for SSH access — must already exist in your AWS account"
  type        = string
  # Set this via terraform.tfvars or -var flag
  # e.g. key_pair_name = "shopsense-key"
}

variable "allowed_ssh_cidr" {
  description = "Your IP address for SSH access (format: x.x.x.x/32)"
  type        = string
  default     = "0.0.0.0/0"   # restrict this to your IP in production
}

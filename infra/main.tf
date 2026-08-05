terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment this block after creating the S3 bucket manually once
  # to store Terraform state remotely — good practice for team projects
  # backend "s3" {
  #   bucket = "shopsense-ai-tfstate"
  #   key    = "terraform.tfstate"
  #   region = "ap-south-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ── Data sources ───────────────────────────────────────────────────────────

# Fetch the default VPC — no custom VPC needed for this project
data "aws_vpc" "default" {
  default = true
}

# ── S3 Bucket — logs and knowledge base backups ────────────────────────────
resource "aws_s3_bucket" "shopsense_bucket" {
  bucket = "${var.project_name}-store-${random_id.suffix.hex}"

  lifecycle {
    prevent_destroy = false
  }
}

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "shopsense_versioning" {
  bucket = aws_s3_bucket.shopsense_bucket.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "shopsense_sse" {
  bucket = aws_s3_bucket.shopsense_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block all public access to the bucket
resource "aws_s3_bucket_public_access_block" "shopsense_bucket_public_access" {
  bucket                  = aws_s3_bucket.shopsense_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── IAM Role — EC2 can write logs to S3 ───────────────────────────────────
resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "ec2_s3_policy" {
  name = "${var.project_name}-s3-policy"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.shopsense_bucket.arn,
          "${aws_s3_bucket.shopsense_bucket.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# ── Security Group ─────────────────────────────────────────────────────────
resource "aws_security_group" "shopsense_sg" {
  name        = "${var.project_name}-sg"
  description = "Security group for ShopSense AI EC2 instance"
  vpc_id      = data.aws_vpc.default.id

  # SSH — restricted to your IP
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # Streamlit frontend
  ingress {
    description = "Streamlit"
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # FastAPI backend
  ingress {
    description = "FastAPI"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # All outbound traffic allowed
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ── EC2 Instance ───────────────────────────────────────────────────────────
resource "aws_instance" "shopsense_ec2" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  key_name               = var.key_pair_name
  vpc_security_group_ids = [aws_security_group.shopsense_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  # Root volume — 30GB to accommodate Docker images + Ollama models
  root_block_device {
    volume_size           = 50
    volume_type           = "gp3"
    delete_on_termination = true
  }

  # User data — runs once on first boot
  # Installs Docker, Docker Compose, pulls the repo, and starts the app
  user_data = <<-EOF
    #!/bin/bash
    set -e

    # Update system
    apt-get update -y
    apt-get upgrade -y

    # Install Docker
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker ubuntu
    systemctl enable docker
    systemctl start docker

    # Install Docker Compose plugin
    apt-get install -y docker-compose-plugin

    # Install git and curl
    apt-get install -y git curl awscli

    # Create app directory
    mkdir -p /home/ubuntu/shopsense-ai
    chown ubuntu:ubuntu /home/ubuntu/shopsense-ai

    echo "✅ ShopSense AI instance ready. Deploy via GitHub Actions."
  EOF

  tags = {
    Name = "${var.project_name}-server"
  }
}

# ── Elastic IP — keeps the public IP stable across restarts ───────────────
resource "aws_eip" "shopsense_eip" {
  instance = aws_instance.shopsense_ec2.id
  domain   = "vpc"
}

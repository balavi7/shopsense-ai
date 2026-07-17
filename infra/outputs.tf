# ── Outputs ────────────────────────────────────────────────────────────────
# These values print after terraform apply
# GitHub Actions uses these to SSH into the server and deploy

output "ec2_public_ip" {
  description = "Elastic IP of the ShopSense AI server"
  value       = aws_eip.shopsense_eip.public_ip
}

output "ec2_instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.shopsense_ec2.id
}

output "s3_bucket_name" {
  description = "S3 bucket for logs and knowledge base backups"
  value       = aws_s3_bucket.shopsense_bucket.bucket
}

output "streamlit_url" {
  description = "Public URL for the Streamlit frontend"
  value       = "http://${aws_eip.shopsense_eip.public_ip}:8501"
}

output "fastapi_url" {
  description = "Public URL for the FastAPI backend"
  value       = "http://${aws_eip.shopsense_eip.public_ip}:8000"
}

output "fastapi_docs_url" {
  description = "FastAPI auto-generated docs"
  value       = "http://${aws_eip.shopsense_eip.public_ip}:8000/docs"
}

output "ssh_command" {
  description = "SSH command to connect to the server"
  value       = "ssh -i ~/.ssh/${var.key_pair_name}.pem ubuntu@${aws_eip.shopsense_eip.public_ip}"
}

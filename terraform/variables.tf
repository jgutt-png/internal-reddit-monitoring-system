# Terraform Variables for Reddit Automation

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-2"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "reddit-automation"
}

variable "environment" {
  description = "Environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

# Database
variable "db_name" {
  description = "Database name"
  type        = string
  default     = "reddit_automation"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "reddit_admin"
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

# Reddit API
variable "reddit_client_id" {
  description = "Reddit API client ID"
  type        = string
  sensitive   = true
}

variable "reddit_client_secret" {
  description = "Reddit API client secret"
  type        = string
  sensitive   = true
}

variable "reddit_username" {
  description = "Reddit username (optional, for authenticated actions)"
  type        = string
  default     = ""
}

variable "reddit_password" {
  description = "Reddit password (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

# Slack
variable "slack_bot_token" {
  description = "Slack bot OAuth token"
  type        = string
  sensitive   = true
}

variable "slack_channel_id" {
  description = "Slack channel ID for notifications"
  type        = string
}

variable "slack_signing_secret" {
  description = "Slack signing secret for verifying requests"
  type        = string
  sensitive   = true
}

# Lambda
variable "lambda_memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 512
}

variable "lambda_timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 300
}

# Scanner
variable "scan_interval_minutes" {
  description = "How often to scan subreddits"
  type        = number
  default     = 30
}

variable "min_relevance_score" {
  description = "Minimum relevance score to post to Slack"
  type        = number
  default     = 0.6
}

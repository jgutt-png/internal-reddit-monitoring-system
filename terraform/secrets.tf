# AWS Secrets Manager for Reddit Automation

resource "aws_secretsmanager_secret" "reddit_automation" {
  name        = "${local.name_prefix}-secrets"
  description = "Secrets for Reddit automation (Reddit API, Slack, Database)"

  tags = {
    Name = "${local.name_prefix}-secrets"
  }
}

resource "aws_secretsmanager_secret_version" "reddit_automation" {
  secret_id = aws_secretsmanager_secret.reddit_automation.id

  secret_string = jsonencode({
    # Reddit API
    reddit_client_id     = var.reddit_client_id
    reddit_client_secret = var.reddit_client_secret
    reddit_username      = var.reddit_username
    reddit_password      = var.reddit_password

    # Slack
    slack_bot_token      = var.slack_bot_token
    slack_channel_id     = var.slack_channel_id
    slack_signing_secret = var.slack_signing_secret

    # Database
    db_host     = aws_rds_cluster.main.endpoint
    db_name     = var.db_name
    db_user     = var.db_username
    db_password = var.db_password
  })

  depends_on = [aws_rds_cluster.main]
}

# Output secret ARN for Lambda
output "secrets_arn" {
  description = "ARN of the secrets manager secret"
  value       = aws_secretsmanager_secret.reddit_automation.arn
}

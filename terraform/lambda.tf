# Lambda Functions for Reddit Automation

# IAM Role for Lambda
resource "aws_iam_role" "lambda" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${local.name_prefix}-lambda-role"
  }
}

# Lambda Policy
resource "aws_iam_role_policy" "lambda" {
  name = "${local.name_prefix}-lambda-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.reddit_automation.arn
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "arn:aws:bedrock:${local.region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
      },
      {
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface",
          "ec2:AssignPrivateIpAddresses",
          "ec2:UnassignPrivateIpAddresses"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda Layer for dependencies
resource "aws_lambda_layer_version" "dependencies" {
  filename            = "${path.module}/../lambda_layer.zip"
  layer_name          = "${local.name_prefix}-dependencies"
  compatible_runtimes = ["python3.11"]
  description         = "Dependencies for Reddit automation Lambda"

  # Skip if layer zip doesn't exist yet
  lifecycle {
    create_before_destroy = true
  }
}

# Scanner Lambda Function
resource "aws_lambda_function" "scanner" {
  filename         = "${path.module}/../lambda_scanner.zip"
  function_name    = "${local.name_prefix}-scanner"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.11"
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size

  layers = [aws_lambda_layer_version.dependencies.arn]

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      SECRETS_ARN       = aws_secretsmanager_secret.reddit_automation.arn
      MIN_RELEVANCE_SCORE = tostring(var.min_relevance_score)
      AWS_REGION_NAME   = var.aws_region
    }
  }

  tags = {
    Name = "${local.name_prefix}-scanner"
  }

  depends_on = [
    aws_iam_role_policy.lambda,
    aws_rds_cluster_instance.main
  ]
}

# Slack Interaction Handler Lambda
resource "aws_lambda_function" "slack_handler" {
  filename         = "${path.module}/../lambda_slack.zip"
  function_name    = "${local.name_prefix}-slack-handler"
  role             = aws_iam_role.lambda.arn
  handler          = "handlers.lambda_handler"
  runtime          = "python3.11"
  timeout          = 30
  memory_size      = 256

  layers = [aws_lambda_layer_version.dependencies.arn]

  vpc_config {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      SECRETS_ARN = aws_secretsmanager_secret.reddit_automation.arn
    }
  }

  tags = {
    Name = "${local.name_prefix}-slack-handler"
  }

  depends_on = [aws_iam_role_policy.lambda]
}

# Lambda Function URL for Slack webhooks (alternative to API Gateway)
resource "aws_lambda_function_url" "slack_handler" {
  function_name      = aws_lambda_function.slack_handler.function_name
  authorization_type = "NONE"
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "scanner" {
  name              = "/aws/lambda/${aws_lambda_function.scanner.function_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "slack_handler" {
  name              = "/aws/lambda/${aws_lambda_function.slack_handler.function_name}"
  retention_in_days = 14
}

# Outputs
output "scanner_lambda_arn" {
  description = "Scanner Lambda ARN"
  value       = aws_lambda_function.scanner.arn
}

output "slack_handler_url" {
  description = "Slack handler function URL"
  value       = aws_lambda_function_url.slack_handler.function_url
}

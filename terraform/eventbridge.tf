# EventBridge Scheduler for Reddit Automation

# EventBridge Rule for scheduled scanning
resource "aws_cloudwatch_event_rule" "scanner_schedule" {
  name                = "${local.name_prefix}-scanner-schedule"
  description         = "Trigger Reddit scanner every ${var.scan_interval_minutes} minutes"
  schedule_expression = "rate(${var.scan_interval_minutes} minutes)"

  tags = {
    Name = "${local.name_prefix}-scanner-schedule"
  }
}

# EventBridge Target for Scanner Lambda
resource "aws_cloudwatch_event_target" "scanner" {
  rule      = aws_cloudwatch_event_rule.scanner_schedule.name
  target_id = "reddit-scanner"
  arn       = aws_lambda_function.scanner.arn

  input = jsonencode({
    source            = "eventbridge"
    min_score         = var.min_relevance_score
    max_slack_posts   = 10
  })
}

# Lambda permission for EventBridge
resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.scanner_schedule.arn
}

# Daily digest EventBridge rule (runs at 9 AM EST)
resource "aws_cloudwatch_event_rule" "daily_digest" {
  name                = "${local.name_prefix}-daily-digest"
  description         = "Trigger daily digest summary at 9 AM EST"
  schedule_expression = "cron(0 14 * * ? *)"  # 14:00 UTC = 9 AM EST

  tags = {
    Name = "${local.name_prefix}-daily-digest"
  }
}

resource "aws_cloudwatch_event_target" "daily_digest" {
  rule      = aws_cloudwatch_event_rule.daily_digest.name
  target_id = "daily-digest"
  arn       = aws_lambda_function.scanner.arn

  input = jsonencode({
    source       = "daily_digest"
    action       = "send_digest"
  })
}

resource "aws_lambda_permission" "daily_digest" {
  statement_id  = "AllowDailyDigestInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_digest.arn
}

# Output schedule info
output "scanner_schedule" {
  description = "Scanner schedule expression"
  value       = aws_cloudwatch_event_rule.scanner_schedule.schedule_expression
}

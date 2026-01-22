"""AWS Lambda handler for Reddit scanner."""

import json
import os
from typing import Dict, Any, List
import structlog
import boto3

# Configure logging
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger(__name__)


def get_secrets() -> Dict[str, str]:
    """Retrieve secrets from AWS Secrets Manager."""
    client = boto3.client("secretsmanager")
    secret_name = os.environ.get("SECRETS_ARN", "reddit-automation-secrets")

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response["SecretString"])
    except Exception as e:
        logger.error("secrets_fetch_error", error=str(e))
        raise


def configure_environment(secrets: Dict[str, str]) -> None:
    """Set environment variables from secrets."""
    env_mappings = {
        "REDDIT_CLIENT_ID": "reddit_client_id",
        "REDDIT_CLIENT_SECRET": "reddit_client_secret",
        "REDDIT_USERNAME": "reddit_username",
        "REDDIT_PASSWORD": "reddit_password",
        "SLACK_BOT_TOKEN": "slack_bot_token",
        "SLACK_CHANNEL_ID": "slack_channel_id",
        "DB_HOST": "db_host",
        "DB_NAME": "db_name",
        "DB_USER": "db_user",
        "DB_PASSWORD": "db_password",
    }

    for env_var, secret_key in env_mappings.items():
        if secret_key in secrets:
            os.environ[env_var] = secrets[secret_key]


def scan_and_notify(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main scanning logic.

    Args:
        event: Lambda event

    Returns:
        Result summary
    """
    # Import here to allow environment configuration first
    from src.scanner.subreddit_monitor import SubredditMonitor
    from src.database.queries import OpportunityQueries
    from slack.bot import SlackBot

    # Initialize components
    monitor = SubredditMonitor()
    opp_queries = OpportunityQueries()
    slack_bot = SlackBot()

    # Get configuration from event or defaults
    subreddits = event.get("subreddits", None)  # None = use config defaults
    min_score = event.get("min_score", 0.5)
    max_slack_posts = event.get("max_slack_posts", 10)

    results = {
        "subreddits_scanned": 0,
        "posts_scanned": 0,
        "opportunities_found": 0,
        "notifications_sent": 0,
        "errors": []
    }

    all_opportunities = []

    # Scan each subreddit
    for scan_result in monitor.scan_all_subreddits(subreddits=subreddits, min_score=min_score):
        results["subreddits_scanned"] += 1
        results["posts_scanned"] += scan_result.posts_scanned

        if scan_result.errors:
            results["errors"].append({
                "subreddit": scan_result.subreddit,
                "error": scan_result.errors
            })
            continue

        # Process opportunities
        for opp in scan_result.opportunities:
            # Check if already exists
            if opp_queries.exists(opp["reddit_id"]):
                logger.debug("opportunity_exists", reddit_id=opp["reddit_id"])
                continue

            # Save to database
            opp_id = opp_queries.create(opp)

            if opp_id:
                opp["id"] = opp_id
                all_opportunities.append(opp)
                results["opportunities_found"] += 1

    # Sort by score and post top opportunities to Slack
    all_opportunities.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    posted_count = 0
    for opp in all_opportunities[:max_slack_posts]:
        ts = slack_bot.post_opportunity(opp)
        if ts:
            # Update opportunity with Slack message timestamp
            opp_queries.update_slack_ts(opp["id"], ts)
            posted_count += 1

    results["notifications_sent"] = posted_count

    # Expire old opportunities
    expired = opp_queries.expire_old_opportunities(hours=48)
    results["opportunities_expired"] = expired

    logger.info("scan_complete", **results)

    return results


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda entry point.

    Args:
        event: Lambda event (can include custom subreddits, min_score, etc.)
        context: Lambda context

    Returns:
        API Gateway compatible response
    """
    logger.info("lambda_invoked", event_type=event.get("source", "manual"))

    try:
        # Load secrets and configure environment
        secrets = get_secrets()
        configure_environment(secrets)

        # Run the scan
        results = scan_and_notify(event)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "success": True,
                "results": results
            })
        }

    except Exception as e:
        logger.error("lambda_error", error=str(e), error_type=type(e).__name__)

        return {
            "statusCode": 500,
            "body": json.dumps({
                "success": False,
                "error": str(e)
            })
        }


# For local testing
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Test event
    test_event = {
        "subreddits": ["wholesaling"],  # Test with one subreddit
        "min_score": 0.4,
        "max_slack_posts": 3
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))

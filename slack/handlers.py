"""Handle Slack interactive button clicks."""

import json
from typing import Dict, Any, Optional
import structlog

from src.database.queries import OpportunityQueries
from .bot import SlackBot

logger = structlog.get_logger(__name__)


class SlackInteractionHandler:
    """Handle Slack button interactions for opportunities."""

    def __init__(
        self,
        bot: Optional[SlackBot] = None,
        queries: Optional[OpportunityQueries] = None
    ):
        self.bot = bot or SlackBot()
        self.queries = queries or OpportunityQueries()

    def handle_interaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle an incoming Slack interaction.

        Args:
            payload: Slack interaction payload

        Returns:
            Response to send back to Slack
        """
        action = payload.get("actions", [{}])[0]
        action_id = action.get("action_id", "")
        reddit_id = action.get("value", "")
        user = payload.get("user", {}).get("id", "unknown")
        user_name = payload.get("user", {}).get("username", "unknown")
        channel = payload.get("channel", {}).get("id")
        message_ts = payload.get("message", {}).get("ts")

        logger.info(
            "slack_interaction_received",
            action_id=action_id,
            reddit_id=reddit_id,
            user=user_name
        )

        if action_id == "mark_reviewed":
            return self._handle_reviewed(reddit_id, user, user_name, channel, message_ts)
        elif action_id == "dismiss_opportunity":
            return self._handle_dismiss(reddit_id, user, user_name, channel, message_ts)
        elif action_id == "view_reddit":
            # External link, no action needed
            return {"response_type": "in_channel"}
        else:
            logger.warning("unknown_action", action_id=action_id)
            return {"response_type": "ephemeral", "text": "Unknown action"}

    def _handle_reviewed(
        self,
        reddit_id: str,
        user_id: str,
        user_name: str,
        channel: str,
        message_ts: str
    ) -> Dict[str, Any]:
        """Handle mark reviewed button click."""
        opportunity = self.queries.get_by_reddit_id(reddit_id)

        if not opportunity:
            return {
                "response_type": "ephemeral",
                "text": f"Post {reddit_id} not found in database."
            }

        # Update status
        self.queries.update_status(opportunity["id"], "reviewed", reviewed_by=user_name)

        # Update Slack message
        if message_ts:
            self.bot.update_message(
                ts=message_ts,
                status="reviewed",
                user=user_id,
                channel=channel,
                title=opportunity.get("title", "")
            )

        logger.info("opportunity_reviewed", reddit_id=reddit_id, user=user_name)

        return {
            "response_type": "ephemeral",
            "text": f":white_check_mark: Marked as reviewed!"
        }

    def _handle_dismiss(
        self,
        reddit_id: str,
        user_id: str,
        user_name: str,
        channel: str,
        message_ts: str
    ) -> Dict[str, Any]:
        """Handle dismiss button click."""
        opportunity = self.queries.get_by_reddit_id(reddit_id)

        if not opportunity:
            return {
                "response_type": "ephemeral",
                "text": f"Post {reddit_id} not found."
            }

        # Update status
        self.queries.update_status(opportunity["id"], "dismissed", reviewed_by=user_name)

        # Update Slack message
        if message_ts:
            self.bot.update_message(
                ts=message_ts,
                status="dismissed",
                user=user_id,
                channel=channel,
                title=opportunity.get("title", "")
            )

        logger.info("opportunity_dismissed", reddit_id=reddit_id, user=user_name)

        return {
            "response_type": "ephemeral",
            "text": ":x: Post dismissed."
        }


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for Slack interactions.

    This is called when users click buttons in Slack messages.
    """
    import urllib.parse

    # Parse the payload
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode("utf-8")

    # Parse URL-encoded payload
    params = urllib.parse.parse_qs(body)
    payload_str = params.get("payload", ["{}"])[0]
    payload = json.loads(payload_str)

    # Handle the interaction
    handler = SlackInteractionHandler()
    response = handler.handle_interaction(payload)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response)
    }

"""Slack bot for Reddit opportunity notifications and interaction."""

from typing import Dict, Any, Optional, List
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import structlog

from src.config import SlackConfig, load_config
from src.database.queries import OpportunityQueries
from .message_builder import MessageBuilder

logger = structlog.get_logger(__name__)


class SlackBot:
    """Slack bot for posting and managing Reddit opportunities."""

    def __init__(self, config: Optional[SlackConfig] = None):
        self.config = config or load_config().slack
        self._client: Optional[WebClient] = None
        self.message_builder = MessageBuilder()

    @property
    def client(self) -> WebClient:
        """Lazy initialization of Slack client."""
        if self._client is None:
            self._client = WebClient(token=self.config.bot_token)
            logger.info("slack_client_initialized")
        return self._client

    def post_opportunity(
        self,
        opportunity: Dict[str, Any],
        channel: Optional[str] = None
    ) -> Optional[str]:
        """
        Post an opportunity to Slack.

        Args:
            opportunity: Opportunity dictionary
            channel: Channel ID (default from config)

        Returns:
            Message timestamp (ts) for updates, or None on failure
        """
        channel = channel or self.config.channel_id

        try:
            message = self.message_builder.build_opportunity_message(opportunity)

            response = self.client.chat_postMessage(
                channel=channel,
                blocks=message["blocks"],
                text=message["text"],
                unfurl_links=False,
                unfurl_media=False
            )

            ts = response.get("ts")
            logger.info(
                "opportunity_posted_to_slack",
                reddit_id=opportunity.get("reddit_id"),
                channel=channel,
                ts=ts
            )

            return ts

        except SlackApiError as e:
            logger.error(
                "slack_post_error",
                error=str(e),
                reddit_id=opportunity.get("reddit_id")
            )
            return None

    def update_message(
        self,
        ts: str,
        status: str,
        user: str,
        channel: Optional[str] = None,
        title: str = ""
    ) -> bool:
        """
        Update an existing message with new status.

        Args:
            ts: Original message timestamp
            status: New status
            user: User who took action
            channel: Channel ID
            title: Original post title

        Returns:
            True on success
        """
        channel = channel or self.config.channel_id

        try:
            # Add status update as a thread reply
            update = self.message_builder.build_status_update(
                reddit_id="",
                status=status,
                user=user,
                original_title=title
            )

            self.client.chat_postMessage(
                channel=channel,
                thread_ts=ts,
                blocks=update["blocks"],
                text=update["text"]
            )

            # Also add a reaction to the original message
            emoji = {
                "approved": "white_check_mark",
                "rejected": "x",
                "responded": "rocket"
            }.get(status, "question")

            self.client.reactions_add(
                channel=channel,
                timestamp=ts,
                name=emoji
            )

            logger.info("slack_message_updated", ts=ts, status=status)
            return True

        except SlackApiError as e:
            logger.error("slack_update_error", error=str(e), ts=ts)
            return False

    def post_batch(
        self,
        opportunities: List[Dict[str, Any]],
        channel: Optional[str] = None,
        max_posts: int = 10
    ) -> List[str]:
        """
        Post multiple opportunities to Slack.

        Args:
            opportunities: List of opportunity dictionaries
            channel: Channel ID
            max_posts: Maximum posts to send

        Returns:
            List of message timestamps
        """
        timestamps = []

        for opp in opportunities[:max_posts]:
            ts = self.post_opportunity(opp, channel)
            if ts:
                timestamps.append(ts)

        logger.info("batch_posted_to_slack", count=len(timestamps))
        return timestamps

    def post_daily_digest(
        self,
        stats: Dict[str, Any],
        top_opportunities: List[Dict],
        channel: Optional[str] = None
    ) -> Optional[str]:
        """
        Post daily digest summary.

        Args:
            stats: Statistics dictionary
            top_opportunities: List of top pending opportunities
            channel: Channel ID

        Returns:
            Message timestamp or None
        """
        channel = channel or self.config.channel_id

        try:
            message = self.message_builder.build_daily_digest(stats, top_opportunities)

            response = self.client.chat_postMessage(
                channel=channel,
                blocks=message["blocks"],
                text=message["text"]
            )

            logger.info("daily_digest_posted", channel=channel)
            return response.get("ts")

        except SlackApiError as e:
            logger.error("slack_digest_error", error=str(e))
            return None

    def send_alert(
        self,
        title: str,
        message: str,
        level: str = "info",
        channel: Optional[str] = None
    ) -> bool:
        """
        Send a simple alert message.

        Args:
            title: Alert title
            message: Alert message
            level: Alert level (info, warning, error)
            channel: Channel ID

        Returns:
            True on success
        """
        channel = channel or self.config.channel_id

        emoji = {
            "info": ":information_source:",
            "warning": ":warning:",
            "error": ":x:"
        }.get(level, ":bell:")

        try:
            self.client.chat_postMessage(
                channel=channel,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{emoji} *{title}*\n{message}"
                        }
                    }
                ],
                text=f"{title}: {message}"
            )
            return True

        except SlackApiError as e:
            logger.error("slack_alert_error", error=str(e))
            return False

    def test_connection(self) -> bool:
        """Test Slack API connection."""
        try:
            response = self.client.auth_test()
            logger.info(
                "slack_connection_test_passed",
                team=response.get("team"),
                user=response.get("user")
            )
            return True
        except SlackApiError as e:
            logger.error("slack_connection_test_failed", error=str(e))
            return False

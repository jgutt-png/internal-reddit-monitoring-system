"""Build Slack Block Kit messages for opportunities."""

from typing import Dict, Any, List


class MessageBuilder:
    """Build Slack Block Kit messages for Reddit opportunities."""

    @staticmethod
    def build_opportunity_message(opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a Slack message with blocks for an opportunity.

        Args:
            opportunity: Opportunity dictionary with post data

        Returns:
            Slack message payload
        """
        reddit_id = opportunity.get("reddit_id", "unknown")
        subreddit = opportunity.get("subreddit", "unknown")
        title = opportunity.get("title", "No title")[:100]
        body = opportunity.get("body", "")[:500]
        permalink = opportunity.get("permalink", "")
        upvotes = opportunity.get("upvotes", 0)
        comments = opportunity.get("comment_count", 0)
        age_hours = opportunity.get("post_age_hours", 0)
        relevance_score = opportunity.get("relevance_score", 0)
        engagement_level = opportunity.get("engagement_potential", "medium")
        matched_keywords = opportunity.get("matched_keywords", [])

        # Emoji for engagement level
        level_emoji = {
            "high": ":fire:",
            "medium": ":star:",
            "low": ":small_blue_diamond:"
        }.get(engagement_level, ":small_blue_diamond:")

        # Score color indicator
        score_pct = int(relevance_score * 100)
        if relevance_score >= 0.7:
            score_indicator = f":green_circle: {score_pct}%"
        elif relevance_score >= 0.5:
            score_indicator = f":large_yellow_circle: {score_pct}%"
        else:
            score_indicator = f":red_circle: {score_pct}%"

        # Format matched keywords
        keyword_list = ", ".join([k.get("phrase", "") for k in matched_keywords[:5]]) if matched_keywords else "none"

        blocks = [
            # Header
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{level_emoji} New Post - r/{subreddit}",
                    "emoji": True
                }
            },
            # Title with link
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*<{permalink}|{title}>*"
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":link: View on Reddit",
                        "emoji": True
                    },
                    "url": permalink,
                    "action_id": "view_reddit"
                }
            },
            # Stats row
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":arrow_up: {upvotes}  |  :speech_balloon: {comments} comments  |  :clock1: {age_hours:.1f}h ago  |  {score_indicator} match"
                    }
                ]
            },
            {"type": "divider"},
            # Post content preview
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Post:*\n>{body[:400]}{'...' if len(body) > 400 else ''}"
                }
            },
            # Matched keywords
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f":mag: *Matched:* {keyword_list}"
                    }
                ]
            },
            {"type": "divider"},
            # Action buttons
            {
                "type": "actions",
                "block_id": f"opportunity_actions_{reddit_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": ":white_check_mark: Mark Reviewed",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": "mark_reviewed",
                        "value": reddit_id
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": ":x: Dismiss",
                            "emoji": True
                        },
                        "action_id": "dismiss_opportunity",
                        "value": reddit_id
                    }
                ]
            }
        ]

        return {
            "blocks": blocks,
            "text": f"New post in r/{subreddit}: {title}"  # Fallback text
        }

    @staticmethod
    def build_status_update(
        reddit_id: str,
        status: str,
        user: str,
        original_title: str = ""
    ) -> Dict[str, Any]:
        """Build a status update message."""
        status_emoji = {
            "reviewed": ":white_check_mark:",
            "dismissed": ":x:",
            "expired": ":hourglass:"
        }.get(status, ":question:")

        return {
            "blocks": [
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"{status_emoji} *{status.upper()}* by <@{user}> | {original_title[:50]}"
                        }
                    ]
                }
            ],
            "text": f"Opportunity {status} by {user}"
        }

    @staticmethod
    def build_daily_digest(stats: Dict[str, Any], top_opportunities: List[Dict]) -> Dict[str, Any]:
        """Build a daily digest message."""
        total = stats.get("total", 0)
        pending = stats.get("pending", 0)
        reviewed = stats.get("reviewed", 0)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":chart_with_upwards_trend: Daily Reddit Digest",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Total Found:*\n{total}"},
                    {"type": "mrkdwn", "text": f"*Pending:*\n{pending}"},
                    {"type": "mrkdwn", "text": f"*Reviewed:*\n{reviewed}"}
                ]
            },
            {"type": "divider"}
        ]

        if top_opportunities:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*:star2: Top Pending Posts:*"
                }
            })

            for i, opp in enumerate(top_opportunities[:5], 1):
                title = opp.get("title", "")[:60]
                score = opp.get("relevance_score", 0)
                permalink = opp.get("permalink", "")

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{i}. <{permalink}|{title}> ({int(score*100)}%)"
                    }
                })

        return {
            "blocks": blocks,
            "text": f"Daily digest: {total} posts found, {pending} pending"
        }

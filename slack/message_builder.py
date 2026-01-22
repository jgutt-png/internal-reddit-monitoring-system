"""Build Slack Block Kit messages for opportunities."""

from typing import Dict, Any, List


class MessageBuilder:
    """Build Slack Block Kit messages for Reddit opportunities."""

    @staticmethod
    def build_opportunity_message(opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build a Slack message with blocks for an opportunity.

        Args:
            opportunity: Opportunity dictionary with post data and analysis

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
        suggested_response = opportunity.get("suggested_response", "")
        ai_analysis = opportunity.get("ai_analysis", {})

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

        blocks = [
            # Header
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{level_emoji} AcqAtlas Opportunity - r/{subreddit}",
                    "emoji": True
                }
            },
            # Title and stats
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
                        "text": f":arrow_up: {upvotes} upvotes  |  :speech_balloon: {comments} comments  |  :clock1: {age_hours:.1f}h ago  |  {score_indicator} relevance"
                    }
                ]
            },
            {"type": "divider"},
            # Post content preview
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Post Content:*\n>{body[:400]}{'...' if len(body) > 400 else ''}"
                }
            },
        ]

        # Add AI analysis if available
        if ai_analysis:
            user_intent = ai_analysis.get("user_intent", "")
            suggested_angle = ai_analysis.get("suggested_angle", "")
            reasoning = ai_analysis.get("reasoning", "")

            if user_intent or suggested_angle:
                blocks.append({"type": "divider"})
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*:brain: AI Analysis:*\n• *Intent:* {user_intent}\n• *Angle:* {suggested_angle}"
                    }
                })

            # Red flags warning
            red_flags = ai_analysis.get("red_flags", [])
            if red_flags:
                flags_text = ", ".join(red_flags)
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f":warning: *Red Flags:* {flags_text}"
                        }
                    ]
                })

        # Suggested response section
        if suggested_response:
            blocks.append({"type": "divider"})
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*:memo: Suggested Response:*\n```{suggested_response[:1500]}```"
                }
            })

        # Action buttons
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "actions",
            "block_id": f"opportunity_actions_{reddit_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":white_check_mark: Approve & Copy",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "approve_opportunity",
                    "value": reddit_id
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":x: Reject",
                        "emoji": True
                    },
                    "style": "danger",
                    "action_id": "reject_opportunity",
                    "value": reddit_id
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": ":pencil: Edit Response",
                        "emoji": True
                    },
                    "action_id": "edit_response",
                    "value": reddit_id
                }
            ]
        })

        return {
            "blocks": blocks,
            "text": f"New opportunity in r/{subreddit}: {title}"  # Fallback text
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
            "approved": ":white_check_mark:",
            "rejected": ":x:",
            "responded": ":rocket:",
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
        approved = stats.get("approved", 0)
        responded = stats.get("responded", 0)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":chart_with_upwards_trend: AcqAtlas Daily Reddit Digest",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Total Found:*\n{total}"},
                    {"type": "mrkdwn", "text": f"*Pending Review:*\n{pending}"},
                    {"type": "mrkdwn", "text": f"*Approved:*\n{approved}"},
                    {"type": "mrkdwn", "text": f"*Responded:*\n{responded}"}
                ]
            },
            {"type": "divider"}
        ]

        if top_opportunities:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*:star2: Top Pending Opportunities:*"
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
            "text": f"Daily digest: {total} opportunities found, {pending} pending"
        }

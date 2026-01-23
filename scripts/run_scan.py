#!/usr/bin/env python3
"""Run a scan and post opportunities to Slack."""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.scanner.subreddit_monitor import SubredditMonitor
from src.database.queries import OpportunityQueries
from slack.bot import SlackBot
import structlog

logger = structlog.get_logger(__name__)


def main():
    """Run scan and post to Slack."""
    print("Starting Reddit scan...")

    # Initialize components
    monitor = SubredditMonitor()
    opp_queries = OpportunityQueries()
    slack_bot = SlackBot()

    # Configuration
    max_slack_posts = int(os.getenv("MAX_SLACK_POSTS", "10"))
    min_score = float(os.getenv("MIN_SCORE", "0.4"))

    results = {
        "posts_scanned": 0,
        "opportunities_found": 0,
        "notifications_sent": 0,
    }

    all_opportunities = []

    # Run scan
    for scan_result in monitor.scan_all_subreddits(min_score=min_score):
        results["posts_scanned"] += scan_result.posts_scanned

        if scan_result.errors:
            print(f"Error during scan: {scan_result.errors}")
            continue

        # Process opportunities
        for opp in scan_result.opportunities:
            # Check if already exists
            if opp_queries.exists(opp["reddit_id"]):
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
            opp_queries.update_slack_ts(opp["id"], ts)
            posted_count += 1
            print(f"  Posted: {opp['title'][:50]}...")

    results["notifications_sent"] = posted_count

    # Expire old opportunities
    expired = opp_queries.expire_old_opportunities(hours=48)
    results["opportunities_expired"] = expired

    print(f"\nScan complete!")
    print(f"  Posts scanned: {results['posts_scanned']}")
    print(f"  New opportunities: {results['opportunities_found']}")
    print(f"  Slack notifications: {results['notifications_sent']}")
    print(f"  Expired: {expired}")


if __name__ == "__main__":
    main()

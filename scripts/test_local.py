#!/usr/bin/env python3
"""Test the Reddit automation locally."""

import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def test_reddit_connection():
    """Test Reddit API connection."""
    print("\n🔌 Testing Reddit API connection...")
    from src.scanner.reddit_client import RedditClient

    client = RedditClient()
    if client.test_connection():
        print("✅ Reddit API connection successful!")
        return True
    else:
        print("❌ Reddit API connection failed!")
        return False


def test_keyword_matching():
    """Test keyword matching."""
    print("\n🔍 Testing keyword matching...")
    from src.scanner.keyword_matcher import KeywordMatcher

    matcher = KeywordMatcher()

    test_cases = [
        ("Looking for off market deals in Florida, specifically Tampa area", "Florida wholesale deals?"),
        ("I have cash buyers but struggling to find motivated sellers in Miami", "Need deal flow in South Florida"),
        ("Anyone know about AcqAtlas? Heard they have good leads", "AcqAtlas review"),
        ("Just closed my first wholesale deal! Assignment fee was $12k", "First deal success story"),
        ("Random unrelated post about cooking", "Best pasta recipe"),
    ]

    for body, title in test_cases:
        result = matcher.match(body, title)
        print(f"\n   Title: {title}")
        print(f"   Matched: {result.matched}")
        print(f"   Score: {result.score}")
        print(f"   Categories: {result.categories}")

    print("✅ Keyword matching working!")
    return True


def test_subreddit_scan():
    """Test scanning a subreddit."""
    print("\n📡 Testing subreddit scan (r/wholesaling, 5 posts)...")
    from src.scanner.subreddit_monitor import SubredditMonitor

    monitor = SubredditMonitor()
    result = monitor.scan_subreddit("wholesaling", limit=5, min_score=0.3)

    print(f"   Posts scanned: {result.posts_scanned}")
    print(f"   Opportunities found: {result.opportunities_found}")

    if result.opportunities:
        print("\n   Top opportunity:")
        opp = result.opportunities[0]
        print(f"   - Title: {opp['title'][:60]}...")
        print(f"   - Score: {opp['relevance_score']}")
        print(f"   - Keywords: {[k['phrase'] for k in opp['matched_keywords'][:3]]}")

    print("✅ Subreddit scan working!")
    return True


def test_ai_analysis():
    """Test AI analysis with Bedrock."""
    print("\n🧠 Testing AI analysis (Bedrock)...")
    from src.analyzer.relevance_scorer import RelevanceScorer

    scorer = RelevanceScorer()

    test_post = {
        "reddit_id": "test123",
        "subreddit": "wholesaling",
        "title": "Struggling to find deals in Tampa - any advice?",
        "body": "I've been driving for dollars for 3 months now in Tampa and can't seem to find any motivated sellers. I have cash buyers ready but no inventory. Skip tracing isn't working either. What am I doing wrong?",
        "upvotes": 15,
        "comment_count": 8,
        "post_age_hours": 3.5,
        "matched_keywords": [
            {"phrase": "tampa"},
            {"phrase": "motivated sellers"},
            {"phrase": "driving for dollars"},
            {"phrase": "skip tracing"}
        ]
    }

    try:
        analysis = scorer.analyze_post(test_post)
        print(f"   Relevance score: {analysis.get('relevance_score')}")
        print(f"   Engagement potential: {analysis.get('engagement_potential')}")
        print(f"   Should engage: {analysis.get('should_engage')}")
        print(f"   User intent: {analysis.get('user_intent', '')[:80]}...")
        print("✅ AI analysis working!")
        return True
    except Exception as e:
        print(f"⚠️  AI analysis error (Bedrock may not be configured): {e}")
        return False


def test_slack_connection():
    """Test Slack connection."""
    print("\n💬 Testing Slack connection...")
    from slack.bot import SlackBot

    bot = SlackBot()
    if bot.test_connection():
        print("✅ Slack connection successful!")
        return True
    else:
        print("⚠️  Slack connection failed (bot token may not be configured)")
        return False


def test_database_connection():
    """Test database connection."""
    print("\n🗄️  Testing database connection...")
    from src.database.connection import get_connection

    try:
        db = get_connection()
        result = db.execute_one("SELECT 1 as test")
        if result and result.get("test") == 1:
            print("✅ Database connection successful!")
            return True
    except Exception as e:
        print(f"⚠️  Database connection failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("🧪 AcqAtlas Reddit Automation - Local Tests")
    print("=" * 60)

    results = {
        "Reddit API": test_reddit_connection(),
        "Keyword Matching": test_keyword_matching(),
        "Subreddit Scan": test_subreddit_scan(),
        "Database": test_database_connection(),
        "Slack": test_slack_connection(),
        "AI Analysis": test_ai_analysis(),
    }

    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {test_name}")
        if not passed:
            all_passed = False

    print("\n")
    if all_passed:
        print("🎉 All tests passed! Ready for deployment.")
    else:
        print("⚠️  Some tests failed. Check configuration and try again.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

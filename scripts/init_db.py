#!/usr/bin/env python3
"""Initialize the database schema."""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.database.connection import get_connection


def main():
    """Initialize the database schema."""
    print("🗄️  Initializing database schema...")

    try:
        db = get_connection()
        db.init_schema()
        print("✅ Database schema initialized successfully!")

        # Verify tables
        result = db.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """, fetch=True)

        print("\n📋 Created tables:")
        for row in result:
            print(f"   - {row['table_name']}")

        # Check subreddit count
        subreddit_count = db.execute_one(
            "SELECT COUNT(*) as count FROM subreddits WHERE is_active = true"
        )
        print(f"\n🎯 Active subreddits: {subreddit_count['count']}")

        # Check keyword count
        keyword_count = db.execute_one(
            "SELECT COUNT(*) as count FROM keywords WHERE is_active = true"
        )
        print(f"🔑 Active keywords: {keyword_count['count']}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

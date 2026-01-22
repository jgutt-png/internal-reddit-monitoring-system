"""Database queries for opportunities and related tables."""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import structlog

from .connection import DatabaseConnection, get_connection

logger = structlog.get_logger(__name__)


class OpportunityQueries:
    """Queries for the opportunities table."""

    def __init__(self, db: Optional[DatabaseConnection] = None):
        self.db = db or get_connection()

    def create(self, opportunity: Dict[str, Any]) -> Optional[int]:
        """Create a new opportunity. Returns the ID or None if duplicate."""
        query = """
            INSERT INTO opportunities (
                reddit_id, subreddit, post_type, title, body, author,
                permalink, url, upvotes, comment_count, post_age_hours,
                relevance_score, engagement_potential, matched_keywords,
                ai_analysis, suggested_response, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (reddit_id) DO NOTHING
            RETURNING id
        """
        params = (
            opportunity.get("reddit_id"),
            opportunity.get("subreddit"),
            opportunity.get("post_type", "post"),
            opportunity.get("title"),
            opportunity.get("body"),
            opportunity.get("author"),
            opportunity.get("permalink"),
            opportunity.get("url"),
            opportunity.get("upvotes", 0),
            opportunity.get("comment_count", 0),
            opportunity.get("post_age_hours"),
            opportunity.get("relevance_score"),
            opportunity.get("engagement_potential"),
            json.dumps(opportunity.get("matched_keywords", [])),
            json.dumps(opportunity.get("ai_analysis")) if opportunity.get("ai_analysis") else None,
            opportunity.get("suggested_response"),
            opportunity.get("status", "pending"),
        )

        result = self.db.execute_one(query, params)
        if result:
            logger.info("opportunity_created", id=result["id"], reddit_id=opportunity.get("reddit_id"))
            return result["id"]
        return None

    def exists(self, reddit_id: str) -> bool:
        """Check if an opportunity already exists."""
        query = "SELECT 1 FROM opportunities WHERE reddit_id = %s"
        result = self.db.execute_one(query, (reddit_id,))
        return result is not None

    def get_by_id(self, opportunity_id: int) -> Optional[Dict]:
        """Get an opportunity by ID."""
        query = "SELECT * FROM opportunities WHERE id = %s"
        return self.db.execute_one(query, (opportunity_id,))

    def get_by_reddit_id(self, reddit_id: str) -> Optional[Dict]:
        """Get an opportunity by Reddit ID."""
        query = "SELECT * FROM opportunities WHERE reddit_id = %s"
        return self.db.execute_one(query, (reddit_id,))

    def get_pending(self, limit: int = 50) -> List[Dict]:
        """Get pending opportunities sorted by relevance score."""
        query = """
            SELECT * FROM opportunities
            WHERE status = 'pending'
            ORDER BY relevance_score DESC, created_at DESC
            LIMIT %s
        """
        return self.db.execute(query, (limit,), fetch=True) or []

    def get_by_status(self, status: str, limit: int = 100) -> List[Dict]:
        """Get opportunities by status."""
        query = """
            SELECT * FROM opportunities
            WHERE status = %s
            ORDER BY created_at DESC
            LIMIT %s
        """
        return self.db.execute(query, (status, limit), fetch=True) or []

    def update_status(
        self,
        opportunity_id: int,
        status: str,
        reviewed_by: Optional[str] = None
    ) -> bool:
        """Update opportunity status."""
        query = """
            UPDATE opportunities
            SET status = %s, reviewed_at = %s, reviewed_by = %s
            WHERE id = %s
        """
        self.db.execute(query, (status, datetime.now(), reviewed_by, opportunity_id))
        logger.info("opportunity_status_updated", id=opportunity_id, status=status)
        return True

    def update_slack_ts(self, opportunity_id: int, slack_ts: str) -> bool:
        """Update Slack message timestamp for an opportunity."""
        query = "UPDATE opportunities SET slack_message_ts = %s WHERE id = %s"
        self.db.execute(query, (slack_ts, opportunity_id))
        return True

    def mark_responded(
        self,
        opportunity_id: int,
        response_text: str,
        reddit_comment_id: Optional[str] = None,
        posted_by: Optional[str] = None
    ) -> int:
        """Mark opportunity as responded and create response record."""
        # Update opportunity status
        self.update_status(opportunity_id, "responded")

        # Create response record
        query = """
            INSERT INTO responses (opportunity_id, response_text, reddit_comment_id, posted_by)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """
        result = self.db.execute_one(query, (opportunity_id, response_text, reddit_comment_id, posted_by))
        return result["id"] if result else None

    def expire_old_opportunities(self, hours: int = 48) -> int:
        """Mark old pending opportunities as expired."""
        query = """
            UPDATE opportunities
            SET status = 'expired'
            WHERE status = 'pending'
            AND created_at < NOW() - INTERVAL '%s hours'
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(query, (hours,))
            count = cursor.rowcount
            logger.info("opportunities_expired", count=count)
            return count

    def get_stats(self) -> Dict[str, Any]:
        """Get opportunity statistics."""
        query = """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'approved') as approved,
                COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
                COUNT(*) FILTER (WHERE status = 'responded') as responded,
                AVG(relevance_score) as avg_relevance_score
            FROM opportunities
            WHERE created_at > NOW() - INTERVAL '7 days'
        """
        return self.db.execute_one(query, ())


class ScanLogQueries:
    """Queries for scan logging."""

    def __init__(self, db: Optional[DatabaseConnection] = None):
        self.db = db or get_connection()

    def start_scan(self, subreddit: str) -> int:
        """Start a scan log entry."""
        query = """
            INSERT INTO scan_logs (subreddit, started_at)
            VALUES (%s, NOW())
            RETURNING id
        """
        result = self.db.execute_one(query, (subreddit,))
        return result["id"]

    def complete_scan(
        self,
        scan_id: int,
        posts_scanned: int,
        opportunities_found: int,
        errors: Optional[str] = None
    ) -> None:
        """Complete a scan log entry."""
        query = """
            UPDATE scan_logs
            SET completed_at = NOW(),
                posts_scanned = %s,
                opportunities_found = %s,
                errors = %s,
                duration_seconds = EXTRACT(EPOCH FROM (NOW() - started_at))
            WHERE id = %s
        """
        self.db.execute(query, (posts_scanned, opportunities_found, errors, scan_id))


class SubredditQueries:
    """Queries for subreddit management."""

    def __init__(self, db: Optional[DatabaseConnection] = None):
        self.db = db or get_connection()

    def get_active(self) -> List[Dict]:
        """Get all active subreddits."""
        query = "SELECT * FROM subreddits WHERE is_active = true ORDER BY name"
        return self.db.execute(query, fetch=True) or []

    def update_last_scanned(self, name: str) -> None:
        """Update last scanned timestamp."""
        query = "UPDATE subreddits SET last_scanned_at = NOW() WHERE name = %s"
        self.db.execute(query, (name,))

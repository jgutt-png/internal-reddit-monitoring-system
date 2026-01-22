"""Reddit API client using PRAW."""

import praw
from praw.models import Submission, Comment
from typing import Optional, List, Dict, Any, Generator
from datetime import datetime, timezone
import structlog

from src.config import RedditConfig, load_config

logger = structlog.get_logger(__name__)


class RedditClient:
    """Wrapper around PRAW for Reddit API access."""

    def __init__(self, config: Optional[RedditConfig] = None):
        self.config = config or load_config().reddit
        self._reddit: Optional[praw.Reddit] = None

    @property
    def reddit(self) -> praw.Reddit:
        """Lazy initialization of Reddit instance."""
        if self._reddit is None:
            self._reddit = praw.Reddit(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                user_agent=self.config.user_agent,
                username=self.config.username if self.config.username else None,
                password=self.config.password if self.config.password else None,
            )
            logger.info("reddit_client_initialized", user_agent=self.config.user_agent)
        return self._reddit

    def get_subreddit_posts(
        self,
        subreddit_name: str,
        sort: str = "new",
        limit: int = 25,
        time_filter: str = "day"
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Get posts from a subreddit.

        Args:
            subreddit_name: Name of subreddit (without r/)
            sort: Sort method - 'new', 'hot', 'top', 'rising'
            limit: Maximum number of posts
            time_filter: Time filter for 'top' sort - 'hour', 'day', 'week', 'month', 'year', 'all'

        Yields:
            Dict containing post data
        """
        try:
            subreddit = self.reddit.subreddit(subreddit_name)

            if sort == "new":
                posts = subreddit.new(limit=limit)
            elif sort == "hot":
                posts = subreddit.hot(limit=limit)
            elif sort == "top":
                posts = subreddit.top(time_filter=time_filter, limit=limit)
            elif sort == "rising":
                posts = subreddit.rising(limit=limit)
            else:
                posts = subreddit.new(limit=limit)

            for post in posts:
                yield self._submission_to_dict(post)

        except Exception as e:
            logger.error("subreddit_fetch_error", subreddit=subreddit_name, error=str(e))
            raise

    def _submission_to_dict(self, submission: Submission) -> Dict[str, Any]:
        """Convert a PRAW Submission to a dictionary."""
        created_utc = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - created_utc).total_seconds() / 3600

        return {
            "reddit_id": submission.id,
            "subreddit": submission.subreddit.display_name,
            "post_type": "post",
            "title": submission.title,
            "body": submission.selftext or "",
            "author": str(submission.author) if submission.author else "[deleted]",
            "permalink": f"https://reddit.com{submission.permalink}",
            "url": submission.url if not submission.is_self else None,
            "upvotes": submission.score,
            "comment_count": submission.num_comments,
            "post_age_hours": round(age_hours, 2),
            "created_utc": created_utc.isoformat(),
            "is_self": submission.is_self,
            "flair": submission.link_flair_text,
            "nsfw": submission.over_18,
            "spoiler": submission.spoiler,
            "locked": submission.locked,
            "archived": submission.archived,
        }

    def search_subreddit(
        self,
        subreddit_name: str,
        query: str,
        sort: str = "relevance",
        time_filter: str = "week",
        limit: int = 25
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Search within a subreddit.

        Args:
            subreddit_name: Name of subreddit
            query: Search query
            sort: Sort by 'relevance', 'hot', 'top', 'new', 'comments'
            time_filter: Time filter
            limit: Maximum results

        Yields:
            Dict containing post data
        """
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            results = subreddit.search(query, sort=sort, time_filter=time_filter, limit=limit)

            for post in results:
                yield self._submission_to_dict(post)

        except Exception as e:
            logger.error("subreddit_search_error", subreddit=subreddit_name, query=query, error=str(e))
            raise

    def get_post_comments(
        self,
        post_id: str,
        limit: int = 50,
        sort: str = "best"
    ) -> List[Dict[str, Any]]:
        """
        Get comments from a post.

        Args:
            post_id: Reddit post ID
            limit: Maximum number of top-level comments
            sort: Sort method

        Returns:
            List of comment dictionaries
        """
        try:
            submission = self.reddit.submission(id=post_id)
            submission.comment_sort = sort
            submission.comments.replace_more(limit=0)  # Don't expand "more comments"

            comments = []
            for comment in submission.comments[:limit]:
                if isinstance(comment, Comment):
                    comments.append(self._comment_to_dict(comment))

            return comments

        except Exception as e:
            logger.error("comments_fetch_error", post_id=post_id, error=str(e))
            raise

    def _comment_to_dict(self, comment: Comment) -> Dict[str, Any]:
        """Convert a PRAW Comment to a dictionary."""
        created_utc = datetime.fromtimestamp(comment.created_utc, tz=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - created_utc).total_seconds() / 3600

        return {
            "reddit_id": comment.id,
            "post_type": "comment",
            "body": comment.body,
            "author": str(comment.author) if comment.author else "[deleted]",
            "permalink": f"https://reddit.com{comment.permalink}",
            "upvotes": comment.score,
            "post_age_hours": round(age_hours, 2),
            "created_utc": created_utc.isoformat(),
            "parent_id": comment.parent_id,
            "is_submitter": comment.is_submitter,
        }

    def get_post_by_id(self, post_id: str) -> Dict[str, Any]:
        """Get a single post by ID."""
        submission = self.reddit.submission(id=post_id)
        return self._submission_to_dict(submission)

    def test_connection(self) -> bool:
        """Test the Reddit API connection."""
        try:
            # Try to access read-only endpoint
            self.reddit.subreddit("test").id
            logger.info("reddit_connection_test_passed")
            return True
        except Exception as e:
            logger.error("reddit_connection_test_failed", error=str(e))
            return False

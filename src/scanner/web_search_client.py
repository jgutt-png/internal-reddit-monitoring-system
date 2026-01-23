"""Web search client for finding Reddit posts without API access."""

import re
import time
import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import requests
import structlog

logger = structlog.get_logger(__name__)

# Flag to use stealth browser if JSON API is blocked
USE_STEALTH_BROWSER = True

# User agents to rotate
USER_AGENTS = [
    "Mozilla/5.0 (compatible; RedditMonitor/1.0)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
]


class WebSearchClient:
    """Search for Reddit posts using Reddit's public JSON endpoints."""

    def __init__(self):
        self.session = requests.Session()
        self._last_request_time = 0
        self.min_delay = 2  # Minimum seconds between requests

    def _get_headers(self) -> Dict[str, str]:
        """Get randomized headers."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json",
        }

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.min_delay:
            sleep_time = self.min_delay - elapsed + random.uniform(0.5, 1.5)
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    def search_reddit(
        self,
        keywords: List[str],
        subreddits: List[str] = None,
        time_filter: str = "week",
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for Reddit posts using Reddit's public JSON API.

        Args:
            keywords: List of keywords to search for
            subreddits: Optional list of subreddits to limit search to
            time_filter: Time filter (day, week, month, all)
            max_results: Maximum results to return

        Returns:
            List of post dictionaries
        """
        all_results = []
        seen_ids = set()

        # Search across specified subreddits
        target_subreddits = subreddits if subreddits else ["all"]

        for subreddit in target_subreddits[:10]:  # Limit subreddits
            for keyword in keywords[:5]:  # Limit keywords
                try:
                    results = self._search_subreddit(
                        subreddit=subreddit,
                        query=keyword,
                        time_filter=time_filter,
                        limit=min(25, max_results)
                    )

                    # Deduplicate
                    for result in results:
                        if result["reddit_id"] not in seen_ids:
                            seen_ids.add(result["reddit_id"])
                            all_results.append(result)

                    logger.info(
                        "search_completed",
                        subreddit=subreddit,
                        query=keyword[:30],
                        results=len(results)
                    )

                except Exception as e:
                    logger.warning(
                        "search_failed",
                        subreddit=subreddit,
                        query=keyword[:30],
                        error=str(e)
                    )

                if len(all_results) >= max_results:
                    break

            if len(all_results) >= max_results:
                break

        return all_results[:max_results]

    def _search_subreddit(
        self,
        subreddit: str,
        query: str,
        time_filter: str = "week",
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """
        Search a specific subreddit using Reddit's JSON API.

        Args:
            subreddit: Subreddit name
            query: Search query
            time_filter: Time filter
            limit: Max results

        Returns:
            List of post dictionaries
        """
        self._rate_limit()

        # Build URL for Reddit JSON search
        if subreddit.lower() == "all":
            url = f"https://www.reddit.com/search.json"
            params = {
                "q": query,
                "sort": "relevance",
                "t": time_filter,
                "limit": limit,
            }
        else:
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
            params = {
                "q": query,
                "restrict_sr": "on",
                "sort": "relevance",
                "t": time_filter,
                "limit": limit,
            }

        try:
            response = self.session.get(
                url,
                params=params,
                headers=self._get_headers(),
                timeout=15
            )
            response.raise_for_status()

            data = response.json()
            children = data.get("data", {}).get("children", [])

            results = []
            for child in children:
                post_data = child.get("data", {})
                parsed = self._parse_post(post_data)
                if parsed:
                    results.append(parsed)

            return results

        except Exception as e:
            logger.error("reddit_search_error", error=str(e))
            return []

    def _parse_post(self, post_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse Reddit post data from JSON response."""
        try:
            created_utc = post_data.get("created_utc", 0)
            age_hours = 0
            if created_utc:
                created_time = datetime.fromtimestamp(created_utc, tz=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - created_time).total_seconds() / 3600

            return {
                "reddit_id": post_data.get("id", ""),
                "subreddit": post_data.get("subreddit", ""),
                "post_type": "post",
                "title": post_data.get("title", ""),
                "body": post_data.get("selftext", "")[:2000],  # Truncate long bodies
                "author": post_data.get("author", "[deleted]"),
                "permalink": f"https://www.reddit.com{post_data.get('permalink', '')}",
                "url": post_data.get("url"),
                "upvotes": post_data.get("ups", 0),
                "comment_count": post_data.get("num_comments", 0),
                "post_age_hours": round(age_hours, 2),
                "source": "reddit_json_api",
                "is_self": post_data.get("is_self", True),
                "flair": post_data.get("link_flair_text", ""),
            }

        except Exception as e:
            logger.debug("post_parse_error", error=str(e))
            return None

    def fetch_post_details(self, permalink: str) -> Optional[Dict[str, Any]]:
        """
        Fetch additional details from a Reddit post.

        Note: Using JSON endpoint instead of scraping HTML.
        """
        self._rate_limit()

        try:
            # Convert permalink to JSON URL
            json_url = permalink.rstrip("/") + ".json"

            response = self.session.get(
                json_url,
                headers=self._get_headers(),
                timeout=15
            )
            response.raise_for_status()

            data = response.json()
            if not data or not isinstance(data, list) or len(data) == 0:
                return None

            # First element is the post, second is comments
            post_data = data[0].get("data", {}).get("children", [{}])[0].get("data", {})

            return {
                "title": post_data.get("title"),
                "body": post_data.get("selftext", "")[:2000],
                "upvotes": post_data.get("ups", 0),
                "comment_count": post_data.get("num_comments", 0),
                "author": post_data.get("author", "[deleted]"),
            }

        except Exception as e:
            logger.warning("post_fetch_error", url=permalink[:50], error=str(e))
            return None

    def get_subreddit_new(
        self,
        subreddit: str,
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """
        Get new posts from a subreddit.

        Args:
            subreddit: Subreddit name
            limit: Max posts to fetch

        Returns:
            List of post dictionaries
        """
        self._rate_limit()

        url = f"https://www.reddit.com/r/{subreddit}/new.json"

        try:
            response = self.session.get(
                url,
                params={"limit": limit},
                headers=self._get_headers(),
                timeout=15
            )
            response.raise_for_status()

            data = response.json()
            children = data.get("data", {}).get("children", [])

            results = []
            for child in children:
                post_data = child.get("data", {})
                parsed = self._parse_post(post_data)
                if parsed:
                    results.append(parsed)

            return results

        except Exception as e:
            logger.error("subreddit_fetch_error", subreddit=subreddit, error=str(e))
            return []


def search_reddit_posts(
    keywords: List[str],
    subreddits: List[str] = None,
    max_results: int = 20,
    fetch_details: bool = False,
    use_stealth: bool = None
) -> List[Dict[str, Any]]:
    """
    Convenience function to search Reddit posts.

    Args:
        keywords: Keywords to search for
        subreddits: Optional subreddits to limit search
        max_results: Maximum results
        fetch_details: Whether to fetch full post details (slower)
        use_stealth: Force stealth browser (None = auto-detect)

    Returns:
        List of post dictionaries
    """
    # Try JSON API first
    if use_stealth is not True:
        client = WebSearchClient()
        results = client.search_reddit(keywords, subreddits, max_results=max_results)

        # If we got results, use them
        if results:
            if fetch_details:
                for i, post in enumerate(results):
                    details = client.fetch_post_details(post["permalink"])
                    if details:
                        results[i].update(details)
            return results

    # Fall back to stealth browser if enabled and JSON API returned nothing
    if USE_STEALTH_BROWSER or use_stealth is True:
        try:
            from .stealth_browser import search_reddit_posts as stealth_search
            logger.info("using_stealth_browser", reason="json_api_blocked_or_empty")
            return stealth_search(keywords, subreddits, max_results)
        except ImportError as e:
            logger.warning("stealth_browser_unavailable", error=str(e))
        except Exception as e:
            logger.error("stealth_browser_error", error=str(e))

    return []

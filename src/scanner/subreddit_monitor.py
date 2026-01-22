"""Subreddit monitoring and opportunity detection."""

from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass
import structlog

from src.config import ScannerConfig, load_config
from .reddit_client import RedditClient
from .keyword_matcher import KeywordMatcher, calculate_engagement_score

logger = structlog.get_logger(__name__)


@dataclass
class ScanResult:
    """Result from scanning a subreddit."""
    subreddit: str
    posts_scanned: int
    opportunities_found: int
    opportunities: List[Dict[str, Any]]
    errors: Optional[str] = None


class SubredditMonitor:
    """Monitor subreddits for engagement opportunities."""

    def __init__(
        self,
        reddit_client: Optional[RedditClient] = None,
        keyword_matcher: Optional[KeywordMatcher] = None,
        config: Optional[ScannerConfig] = None
    ):
        self.reddit = reddit_client or RedditClient()
        self.matcher = keyword_matcher or KeywordMatcher()
        self.config = config or load_config().scanner

    def scan_subreddit(
        self,
        subreddit_name: str,
        limit: int = None,
        min_score: float = None
    ) -> ScanResult:
        """
        Scan a subreddit for engagement opportunities.

        Args:
            subreddit_name: Name of subreddit to scan
            limit: Max posts to scan (default from config)
            min_score: Minimum relevance score (default from config)

        Returns:
            ScanResult with found opportunities
        """
        limit = limit or self.config.max_posts_per_subreddit
        min_score = min_score or self.config.min_relevance_score

        opportunities = []
        posts_scanned = 0
        errors = None

        try:
            logger.info("scanning_subreddit", subreddit=subreddit_name, limit=limit)

            for post in self.reddit.get_subreddit_posts(subreddit_name, sort="new", limit=limit):
                posts_scanned += 1

                # Skip old posts
                if post.get("post_age_hours", 0) > self.config.post_max_age_hours:
                    continue

                # Skip locked/archived posts
                if post.get("locked") or post.get("archived"):
                    continue

                # Skip NSFW
                if post.get("nsfw"):
                    continue

                # Check for keyword matches
                match_result = self.matcher.match(post.get("body", ""), post.get("title", ""))

                if not match_result.matched:
                    continue

                # Calculate engagement score
                engagement_score, engagement_level = calculate_engagement_score(
                    post, match_result.score
                )

                # Filter by minimum score
                if engagement_score < min_score:
                    continue

                # Create opportunity record
                opportunity = {
                    **post,
                    "relevance_score": engagement_score,
                    "engagement_potential": engagement_level,
                    "matched_keywords": match_result.keywords,
                    "matched_categories": list(match_result.categories),
                }

                opportunities.append(opportunity)
                logger.debug(
                    "opportunity_found",
                    reddit_id=post["reddit_id"],
                    score=engagement_score,
                    keywords=len(match_result.keywords)
                )

        except Exception as e:
            errors = str(e)
            logger.error("scan_error", subreddit=subreddit_name, error=errors)

        # Sort by relevance score descending
        opportunities.sort(key=lambda x: x["relevance_score"], reverse=True)

        result = ScanResult(
            subreddit=subreddit_name,
            posts_scanned=posts_scanned,
            opportunities_found=len(opportunities),
            opportunities=opportunities,
            errors=errors
        )

        logger.info(
            "scan_complete",
            subreddit=subreddit_name,
            scanned=posts_scanned,
            found=len(opportunities)
        )

        return result

    def scan_all_subreddits(
        self,
        subreddits: List[str] = None,
        limit_per_sub: int = None,
        min_score: float = None
    ) -> Generator[ScanResult, None, None]:
        """
        Scan all configured subreddits.

        Args:
            subreddits: List of subreddits to scan (default from config)
            limit_per_sub: Max posts per subreddit
            min_score: Minimum relevance score

        Yields:
            ScanResult for each subreddit
        """
        subreddits = subreddits or self.config.subreddits

        logger.info("starting_full_scan", subreddit_count=len(subreddits))

        for subreddit in subreddits:
            result = self.scan_subreddit(
                subreddit,
                limit=limit_per_sub,
                min_score=min_score
            )
            yield result

    def search_subreddits(
        self,
        query: str,
        subreddits: List[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search across subreddits for a specific query.

        Args:
            query: Search query
            subreddits: List of subreddits to search
            limit: Max results per subreddit

        Returns:
            List of matching posts with scores
        """
        subreddits = subreddits or self.config.subreddits
        all_results = []

        for subreddit in subreddits:
            try:
                for post in self.reddit.search_subreddit(subreddit, query, limit=limit):
                    match_result = self.matcher.match(post.get("body", ""), post.get("title", ""))
                    engagement_score, engagement_level = calculate_engagement_score(
                        post, match_result.score
                    )

                    if match_result.matched:
                        all_results.append({
                            **post,
                            "relevance_score": engagement_score,
                            "engagement_potential": engagement_level,
                            "matched_keywords": match_result.keywords,
                        })

            except Exception as e:
                logger.warning("search_error", subreddit=subreddit, query=query, error=str(e))

        # Sort by score and return
        all_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return all_results

    def get_hot_opportunities(
        self,
        subreddits: List[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get hot/trending posts that match keywords.

        Args:
            subreddits: Subreddits to check
            limit: Max total results

        Returns:
            List of hot opportunities
        """
        subreddits = subreddits or self.config.subreddits[:5]  # Top 5 subreddits
        all_opportunities = []

        for subreddit in subreddits:
            try:
                for post in self.reddit.get_subreddit_posts(subreddit, sort="hot", limit=15):
                    match_result = self.matcher.match(post.get("body", ""), post.get("title", ""))

                    if match_result.matched and match_result.score >= 0.3:
                        engagement_score, engagement_level = calculate_engagement_score(
                            post, match_result.score
                        )

                        all_opportunities.append({
                            **post,
                            "relevance_score": engagement_score,
                            "engagement_potential": engagement_level,
                            "matched_keywords": match_result.keywords,
                        })

            except Exception as e:
                logger.warning("hot_fetch_error", subreddit=subreddit, error=str(e))

        # Sort by score and limit
        all_opportunities.sort(key=lambda x: x["relevance_score"], reverse=True)
        return all_opportunities[:limit]

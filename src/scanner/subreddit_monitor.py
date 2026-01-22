"""Subreddit monitoring using web search."""

from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass
import structlog

from src.config import ScannerConfig, load_config, KEYWORDS
from .web_search_client import WebSearchClient
from .keyword_matcher import KeywordMatcher, calculate_engagement_score

logger = structlog.get_logger(__name__)


@dataclass
class ScanResult:
    """Result from scanning."""
    subreddit: str
    posts_scanned: int
    opportunities_found: int
    opportunities: List[Dict[str, Any]]
    errors: Optional[str] = None


class SubredditMonitor:
    """Monitor subreddits for engagement opportunities using web search."""

    def __init__(
        self,
        search_client: Optional[WebSearchClient] = None,
        keyword_matcher: Optional[KeywordMatcher] = None,
        config: Optional[ScannerConfig] = None
    ):
        self.search = search_client or WebSearchClient()
        self.matcher = keyword_matcher or KeywordMatcher()
        self.config = config or load_config().scanner

    def scan_all(
        self,
        keywords: List[str] = None,
        subreddits: List[str] = None,
        max_results: int = 50,
        min_score: float = None,
        fetch_details: bool = True
    ) -> ScanResult:
        """
        Scan for Reddit posts matching keywords.

        Args:
            keywords: Keywords to search for (default from config)
            subreddits: Subreddits to focus on (default from config)
            max_results: Maximum posts to return
            min_score: Minimum relevance score
            fetch_details: Whether to fetch full post details

        Returns:
            ScanResult with found opportunities
        """
        keywords = keywords or self._get_default_keywords()
        subreddits = subreddits or self.config.subreddits
        min_score = min_score or self.config.min_relevance_score

        opportunities = []
        posts_scanned = 0
        errors = None

        try:
            logger.info(
                "starting_scan",
                keywords=len(keywords),
                subreddits=len(subreddits),
                max_results=max_results
            )

            # Search for posts
            posts = self.search.search_reddit(
                keywords=keywords,
                subreddits=subreddits,
                max_results=max_results
            )

            posts_scanned = len(posts)

            # Fetch details and score each post
            for post in posts:
                # Optionally fetch full details
                if fetch_details:
                    details = self.search.fetch_post_details(post["permalink"])
                    if details:
                        post.update(details)

                # Check for keyword matches
                match_result = self.matcher.match(
                    post.get("body", ""),
                    post.get("title", "")
                )

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
                    reddit_id=post.get("reddit_id"),
                    score=engagement_score,
                    keywords=len(match_result.keywords)
                )

        except Exception as e:
            errors = str(e)
            logger.error("scan_error", error=errors)

        # Sort by relevance score descending
        opportunities.sort(key=lambda x: x["relevance_score"], reverse=True)

        result = ScanResult(
            subreddit="all",
            posts_scanned=posts_scanned,
            opportunities_found=len(opportunities),
            opportunities=opportunities,
            errors=errors
        )

        logger.info(
            "scan_complete",
            scanned=posts_scanned,
            found=len(opportunities)
        )

        return result

    def scan_subreddit(
        self,
        subreddit_name: str,
        limit: int = 25,
        min_score: float = None
    ) -> ScanResult:
        """
        Scan a specific subreddit.

        Args:
            subreddit_name: Name of subreddit to scan
            limit: Max posts to scan
            min_score: Minimum relevance score

        Returns:
            ScanResult with found opportunities
        """
        keywords = self._get_default_keywords()
        return self.scan_all(
            keywords=keywords,
            subreddits=[subreddit_name],
            max_results=limit,
            min_score=min_score
        )

    def scan_all_subreddits(
        self,
        subreddits: List[str] = None,
        min_score: float = None
    ) -> Generator[ScanResult, None, None]:
        """
        Scan all configured subreddits.

        Note: With web search, we do one combined search rather than
        individual subreddit scans for efficiency.

        Yields:
            Single ScanResult with all opportunities
        """
        result = self.scan_all(
            subreddits=subreddits,
            min_score=min_score
        )
        yield result

    def _get_default_keywords(self) -> List[str]:
        """Get flattened list of keywords from config."""
        all_keywords = []
        for category, keywords in KEYWORDS.items():
            # Prioritize certain categories
            if category in ["florida_off_market", "investor_intent", "deal_types"]:
                all_keywords.extend(keywords[:5])  # Top 5 from priority categories
            else:
                all_keywords.extend(keywords[:3])  # Top 3 from others
        return all_keywords[:15]  # Limit total keywords

    def quick_search(
        self,
        query: str,
        subreddits: List[str] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Quick search with a custom query.

        Args:
            query: Search query
            subreddits: Optional subreddits to focus on
            max_results: Maximum results

        Returns:
            List of matching posts
        """
        return self.search.search_reddit(
            keywords=[query],
            subreddits=subreddits,
            max_results=max_results
        )

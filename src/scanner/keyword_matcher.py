"""Keyword matching for Reddit posts."""

import re
from typing import List, Dict, Any, Set, Tuple
from dataclasses import dataclass
import structlog

from src.config import KEYWORDS

logger = structlog.get_logger(__name__)


@dataclass
class MatchResult:
    """Result of keyword matching."""
    matched: bool
    score: float
    keywords: List[Dict[str, Any]]
    categories: Set[str]


class KeywordMatcher:
    """Match posts against keyword patterns."""

    def __init__(self, keywords: Dict[str, List[str]] = None):
        """
        Initialize with keywords dictionary.

        Args:
            keywords: Dict mapping category -> list of keyword phrases
        """
        self.keywords = keywords or KEYWORDS
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[str, List[Tuple[re.Pattern, str]]]:
        """Compile keyword phrases into regex patterns."""
        compiled = {}
        for category, phrases in self.keywords.items():
            compiled[category] = [
                (re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE), phrase)
                for phrase in phrases
            ]
        return compiled

    def match(self, text: str, title: str = "") -> MatchResult:
        """
        Match text against all keywords.

        Args:
            text: Post body text
            title: Post title (optional, weighted higher)

        Returns:
            MatchResult with match details
        """
        combined_text = f"{title} {text}".lower()
        matched_keywords = []
        matched_categories = set()
        total_score = 0.0

        for category, patterns in self._compiled_patterns.items():
            for pattern, phrase in patterns:
                # Check title (higher weight)
                title_matches = len(pattern.findall(title.lower()))
                # Check body
                body_matches = len(pattern.findall(text.lower()))

                if title_matches > 0 or body_matches > 0:
                    # Title matches worth 1.5x, body matches worth 1x
                    keyword_score = (title_matches * 1.5) + body_matches

                    # Miami-specific keywords get bonus
                    if category == "miami_specific":
                        keyword_score *= 1.3

                    matched_keywords.append({
                        "phrase": phrase,
                        "category": category,
                        "title_matches": title_matches,
                        "body_matches": body_matches,
                        "score": round(keyword_score, 2)
                    })
                    matched_categories.add(category)
                    total_score += keyword_score

        # Normalize score to 0-1 range (cap at 10 matches = 1.0)
        normalized_score = min(total_score / 10.0, 1.0)

        # Bonus for multiple categories (more diverse = more relevant)
        category_bonus = min(len(matched_categories) * 0.1, 0.3)
        final_score = min(normalized_score + category_bonus, 1.0)

        return MatchResult(
            matched=len(matched_keywords) > 0,
            score=round(final_score, 2),
            keywords=matched_keywords,
            categories=matched_categories
        )

    def quick_match(self, text: str, title: str = "") -> bool:
        """
        Quick check if any keywords match (no scoring).

        Args:
            text: Post body text
            title: Post title

        Returns:
            True if any keyword matches
        """
        combined_text = f"{title} {text}".lower()

        for category, patterns in self._compiled_patterns.items():
            for pattern, _ in patterns:
                if pattern.search(combined_text):
                    return True
        return False

    def get_categories_for_text(self, text: str, title: str = "") -> Set[str]:
        """Get all matching categories for text."""
        result = self.match(text, title)
        return result.categories

    def add_custom_keywords(self, category: str, phrases: List[str]) -> None:
        """Add custom keywords at runtime."""
        if category not in self.keywords:
            self.keywords[category] = []

        self.keywords[category].extend(phrases)

        # Recompile patterns
        self._compiled_patterns[category] = [
            (re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE), phrase)
            for phrase in self.keywords[category]
        ]

        logger.info("custom_keywords_added", category=category, count=len(phrases))


def calculate_engagement_score(post: Dict[str, Any], keyword_score: float) -> Tuple[float, str]:
    """
    Calculate overall engagement potential score.

    Args:
        post: Post dictionary with upvotes, comment_count, post_age_hours
        keyword_score: Score from keyword matching (0-1)

    Returns:
        Tuple of (score, engagement_level)
    """
    # Factors to consider
    upvotes = post.get("upvotes", 0)
    comments = post.get("comment_count", 0)
    age_hours = post.get("post_age_hours", 0)

    # Fresh posts get bonus (under 6 hours)
    freshness_bonus = 0.2 if age_hours < 6 else (0.1 if age_hours < 12 else 0)

    # Moderate engagement is good (not too hot, not dead)
    engagement_score = 0
    if 5 <= upvotes <= 100:
        engagement_score += 0.15
    if 3 <= comments <= 50:
        engagement_score += 0.15

    # Calculate final score
    final_score = keyword_score * 0.6 + engagement_score + freshness_bonus
    final_score = min(final_score, 1.0)

    # Determine engagement level
    if final_score >= 0.7:
        level = "high"
    elif final_score >= 0.4:
        level = "medium"
    else:
        level = "low"

    return round(final_score, 2), level

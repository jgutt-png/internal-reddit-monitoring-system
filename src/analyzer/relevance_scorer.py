"""AI-powered relevance scoring using AWS Bedrock."""

import json
from typing import Dict, Any, Optional
import boto3
from botocore.config import Config as BotoConfig
import structlog

from src.config import AWSConfig, load_config

logger = structlog.get_logger(__name__)

ANALYSIS_PROMPT = """You are an expert at identifying Reddit posts in wholesale real estate communities that present opportunities for genuine engagement. You represent AcqAtlas, a Florida off-market real estate deal platform.

CRITICAL DM/COMMENT RULES (from proven outreach data):
- Goal of message 1 is to get message 2, NOT to close
- NO pitching, NO links, NO "I help X do Y"
- Reference something SPECIFIC they said
- Show you understand their problem
- Ask ONE question only
- Sound like a helpful community member, not a salesperson
- Volume is a trap. Relevance is the game.

Analyze this Reddit post:

Subreddit: r/{subreddit}
Title: {title}
Content: {body}
Post Stats: {upvotes} upvotes | {comment_count} comments | Posted {post_age_hours:.1f} hours ago
Matched Keywords: {matched_keywords}

Evaluate:

1. **Relevance Score (0.0-1.0)**: How relevant to Florida wholesale/off-market deals?
   - Is this someone looking for deals, struggling to find inventory, or asking about Florida markets?
   - Are they a wholesaler, investor, or buyer who could benefit from off-market leads?
   - Florida-specific = bonus points

2. **Engagement Potential**:
   - HIGH: Clear pain point about finding deals, need for inventory, Florida market questions
   - MEDIUM: General wholesaling question where Florida expertise adds value
   - LOW: Not a good fit, already solved, or venting

3. **User Intent**: What do they actually need? (deals, advice, validation, venting)

4. **Suggested Angle**: What specific insight can we offer based on Florida market experience?

5. **Red Flags**: Reasons NOT to engage:
   - Complaining about wholesalers/investors
   - Legal issues, scam accusations
   - Already has solution, just sharing
   - Post is old (24h+) or locked

6. **Draft Response**: Write a response that:
   - References something SPECIFIC from their post (quote them)
   - Shows you understand their exact problem
   - Asks ONE clarifying question to continue the conversation
   - NO links, NO company mentions, NO pitch
   - Sounds like an experienced Florida wholesaler helping out
   - 2-4 sentences MAX

GOOD EXAMPLE:
"Saw you're having trouble finding deals in Tampa - are you mainly struggling with finding motivated sellers or is it more about the competition on the deals you do find?"

BAD EXAMPLE:
"Hey! I run a platform that finds off-market deals in Florida. Check out AcqAtlas.com for leads!"

Respond in this exact JSON format:
{{
    "relevance_score": 0.0,
    "engagement_potential": "high|medium|low",
    "user_intent": "string describing what they're looking for",
    "suggested_angle": "specific approach to take",
    "red_flags": ["list of concerns, or empty"],
    "should_engage": true,
    "reasoning": "1-2 sentence explanation",
    "draft_response": "The actual response to post - SHORT, one question, no pitch"
}}

Important: Only respond with valid JSON, no additional text."""


class RelevanceScorer:
    """Score post relevance using AWS Bedrock."""

    def __init__(self, config: Optional[AWSConfig] = None):
        self.config = config or load_config().aws
        self._client = None

    @property
    def client(self):
        """Lazy initialization of Bedrock client."""
        if self._client is None:
            boto_config = BotoConfig(
                region_name=self.config.region,
                retries={"max_attempts": 3, "mode": "adaptive"}
            )
            self._client = boto3.client("bedrock-runtime", config=boto_config)
            logger.info("bedrock_client_initialized", region=self.config.region)
        return self._client

    def analyze_post(self, post: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a post using Claude on Bedrock.

        Args:
            post: Post dictionary with title, body, upvotes, etc.

        Returns:
            Analysis result dictionary
        """
        # Format the prompt
        prompt = ANALYSIS_PROMPT.format(
            subreddit=post.get("subreddit", "unknown"),
            title=post.get("title", ""),
            body=post.get("body", "")[:2000],  # Truncate long posts
            upvotes=post.get("upvotes", 0),
            comment_count=post.get("comment_count", 0),
            post_age_hours=post.get("post_age_hours", 0),
            matched_keywords=", ".join([k.get("phrase", "") for k in post.get("matched_keywords", [])[:5]])
        )

        try:
            # Call Bedrock
            response = self.client.invoke_model(
                modelId=self.config.bedrock_model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1500,
                    "temperature": 0.3,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                })
            )

            # Parse response
            response_body = json.loads(response["body"].read())
            content = response_body.get("content", [{}])[0].get("text", "{}")

            # Parse JSON from response
            analysis = self._parse_json_response(content)

            logger.info(
                "post_analyzed",
                reddit_id=post.get("reddit_id"),
                relevance_score=analysis.get("relevance_score"),
                should_engage=analysis.get("should_engage")
            )

            return analysis

        except Exception as e:
            logger.error("bedrock_analysis_error", error=str(e), reddit_id=post.get("reddit_id"))
            # Return default values on error
            return {
                "relevance_score": post.get("relevance_score", 0.5),
                "engagement_potential": post.get("engagement_potential", "medium"),
                "user_intent": "unknown",
                "suggested_angle": "",
                "red_flags": ["Analysis failed"],
                "should_engage": False,
                "reasoning": f"Analysis error: {str(e)}",
                "draft_response": ""
            }

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from Claude response, handling edge cases."""
        try:
            # Try direct parse
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            else:
                # Last resort: find JSON object in text
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    return json.loads(content[start:end])
                raise

    def batch_analyze(self, posts: list, max_concurrent: int = 5) -> list:
        """
        Analyze multiple posts.

        Args:
            posts: List of post dictionaries
            max_concurrent: Max concurrent requests (not implemented yet)

        Returns:
            List of analysis results
        """
        results = []
        for post in posts:
            analysis = self.analyze_post(post)
            results.append({
                "reddit_id": post.get("reddit_id"),
                "analysis": analysis
            })
        return results

    def should_engage(self, analysis: Dict[str, Any], min_score: float = 0.6) -> bool:
        """
        Determine if we should engage based on analysis.

        Args:
            analysis: Analysis result from analyze_post
            min_score: Minimum relevance score

        Returns:
            True if we should engage
        """
        if not analysis.get("should_engage", False):
            return False

        if analysis.get("relevance_score", 0) < min_score:
            return False

        if analysis.get("red_flags"):
            # Check if red flags are serious
            serious_flags = ["legal", "complaint", "lawsuit", "scam", "spam"]
            for flag in analysis.get("red_flags", []):
                if any(word in flag.lower() for word in serious_flags):
                    return False

        return True

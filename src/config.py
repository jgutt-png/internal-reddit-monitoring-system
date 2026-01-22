"""Configuration management for Reddit automation."""

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class RedditConfig:
    """Reddit API configuration."""
    client_id: str = field(default_factory=lambda: os.getenv("REDDIT_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("REDDIT_CLIENT_SECRET", ""))
    user_agent: str = field(default_factory=lambda: os.getenv("REDDIT_USER_AGENT", "RealEstateBot/1.0"))
    username: str = field(default_factory=lambda: os.getenv("REDDIT_USERNAME", ""))
    password: str = field(default_factory=lambda: os.getenv("REDDIT_PASSWORD", ""))


@dataclass
class DatabaseConfig:
    """PostgreSQL database configuration."""
    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    name: str = field(default_factory=lambda: os.getenv("DB_NAME", "reddit_automation"))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))

    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class SlackConfig:
    """Slack bot configuration."""
    bot_token: str = field(default_factory=lambda: os.getenv("SLACK_BOT_TOKEN", ""))
    channel_id: str = field(default_factory=lambda: os.getenv("SLACK_CHANNEL_ID", ""))
    signing_secret: str = field(default_factory=lambda: os.getenv("SLACK_SIGNING_SECRET", ""))


@dataclass
class AWSConfig:
    """AWS configuration."""
    region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-2"))


@dataclass
class ScannerConfig:
    """Scanner behavior configuration."""
    scan_interval_minutes: int = 30
    max_posts_per_subreddit: int = 25
    min_relevance_score: float = 0.6
    post_max_age_hours: int = 24

    # Target subreddits - Florida Wholesale Real Estate
    subreddits: List[str] = field(default_factory=lambda: [
        # Primary - High intent wholesale/investing
        "WholesaleRealestate",
        "wholesaling",
        "realestateinvesting",
        "flipping",
        # General real estate
        "RealEstate",
        "CommercialRealEstate",
        # Florida specific
        "FloridaRealEstate",
        "florida",
        "Miami",
        "tampa",
        "orlando",
        "jacksonville",
    ])


@dataclass
class Config:
    """Main configuration container."""
    reddit: RedditConfig = field(default_factory=RedditConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    slack: SlackConfig = field(default_factory=SlackConfig)
    aws: AWSConfig = field(default_factory=AWSConfig)
    scanner: ScannerConfig = field(default_factory=ScannerConfig)


# Keywords for matching - Florida Wholesale Focus
KEYWORDS = {
    "florida_off_market": [
        "florida off market", "FL wholesale", "florida wholesale deal",
        "miami off market", "florida wholesale", "off market florida",
        "florida deals", "FL off market", "south florida wholesale",
        "tampa wholesale", "orlando wholesale", "jacksonville wholesale"
    ],
    "deal_types": [
        "motivated seller", "tax lien", "probate", "distressed property",
        "pre-foreclosure", "foreclosure", "bank owned", "REO",
        "short sale", "estate sale", "divorce sale", "vacant property",
        "absentee owner", "code violation", "fire damage", "hoarder house",
        "inherited property", "back taxes", "liens"
    ],
    "investor_intent": [
        "looking for deals", "investor network", "off market leads",
        "cash buyer", "need deals", "looking for wholesale",
        "buyer's list", "deal flow", "acquisitions", "dispositions",
        "assignment fee", "double close", "JV deal", "seeking deals",
        "active investor", "cash ready", "proof of funds"
    ],
    "wholesaling": [
        "wholesale", "wholesaling", "assignment", "assignment contract",
        "EMD", "earnest money", "title company", "closing cost",
        "ARV", "after repair value", "MAO", "maximum allowable offer",
        "70% rule", "repair estimate", "comps", "deal analysis",
        "skip tracing", "driving for dollars", "D4D", "cold calling"
    ],
    "florida_markets": [
        "miami", "south florida", "fort lauderdale", "boca raton",
        "palm beach", "broward", "dade", "tampa", "orlando",
        "jacksonville", "st petersburg", "clearwater", "sarasota",
        "naples", "cape coral", "fort myers", "gainesville", "tallahassee",
        "pensacola", "daytona", "west palm beach", "pompano beach"
    ],
    "help_seeking": [
        "need advice", "any tips", "how do I", "what should I",
        "help me understand", "new to wholesaling", "beginner wholesaler",
        "first deal", "getting started", "how to find", "where to find",
        "struggling to find", "can't find deals", "deal sources"
    ]
}


def load_config() -> Config:
    """Load configuration from environment variables."""
    from dotenv import load_dotenv
    load_dotenv()
    return Config()

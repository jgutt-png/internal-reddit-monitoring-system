# Reddit Monitoring System

A Reddit monitoring bot that scans for posts matching configurable keywords using web search and sends notifications to Slack for team review.

## Features

- **Web Search Scanning**: Searches for Reddit posts using DuckDuckGo with `site:reddit.com` filtering
- **Keyword Matching**: Filters posts based on customizable keyword categories with weighted scoring
- **Slack Notifications**: Sends matching posts to Slack with post details and action buttons
- **PostgreSQL Storage**: Tracks posts, review status, and scan history
- **AWS Lambda Ready**: Designed for serverless deployment with EventBridge scheduling

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  EventBridge    │────▶│  Lambda Scanner  │────▶│   PostgreSQL    │
│  (Scheduled)    │     │  (Web Search)    │     │   (Aurora)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │                         │
                               ▼                         ▼
                       ┌──────────────────┐     ┌─────────────────┐
                       │   Slack Bot      │◀────│   Posts Table   │
                       │  (Notifications) │     │                 │
                       └──────────────────┘     └─────────────────┘
```

## How It Works

1. **Scanner** runs on schedule (configurable, default: every 30 minutes)
2. **Searches** for Reddit posts using web search with configured keywords
3. **Keyword matching** scores posts based on relevance
4. **Slack notification** sent with post details and review buttons
5. **Team reviews** posts directly in Slack

## Project Structure

```
├── src/
│   ├── scanner/          # Web search client and monitoring
│   │   ├── web_search_client.py
│   │   ├── subreddit_monitor.py
│   │   └── keyword_matcher.py
│   ├── database/         # PostgreSQL connection and queries
│   └── config.py         # Configuration management
├── slack/                # Slack bot and message formatting
├── lambda/               # AWS Lambda handlers
├── terraform/            # Infrastructure as Code
└── scripts/              # Utility scripts
```

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL database
- Slack Bot Token

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your credentials
4. Initialize the database:
   ```bash
   python scripts/init_db.py
   ```
5. Test locally:
   ```bash
   python scripts/test_local.py
   ```

### Slack Setup

1. Create a Slack App at https://api.slack.com/apps
2. Add Bot Token Scopes: `chat:write`, `reactions:write`
3. Enable Interactivity for button support
4. Install to your workspace

## Configuration

Edit `src/config.py` to customize:

- **Subreddits**: Which subreddits to focus searches on
- **Keywords**: Keyword categories and phrases to match
- **Scan interval**: How often to scan
- **Minimum score**: Threshold for Slack notifications

## Rate Limits

Web search has implicit rate limits. The scanner includes delays between requests (configurable, default: 2 seconds) to avoid being blocked.

## License

MIT

"""Stealth browser client for Reddit scraping with anti-bot detection."""

import asyncio
import random
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import structlog

logger = structlog.get_logger(__name__)

# Realistic user agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Stealth JavaScript to inject
STEALTH_JS = """
// Remove webdriver property
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// Fake Chrome runtime object
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};

// Fake browser plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
        { name: 'Native Client', filename: 'internal-nacl-plugin' }
    ]
});

// Language spoofing
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en']
});

// Permissions query fix
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// WebGL fingerprint spoofing
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Intel Inc.';
    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter.call(this, parameter);
};
"""

# Configuration
CONFIG = {
    'SEARCH_WAIT': 1.5,
    'PAGE_WAIT': 1.5,
    'TYPE_DELAY': 0.1,
    'MIN_DELAY': 2.0,
    'MAX_DELAY': 4.0,
}


class StealthRedditClient:
    """Stealth browser client for Reddit scraping."""

    def __init__(self):
        self.browser = None
        self.tab = None

    async def _init_browser(self):
        """Initialize stealth browser."""
        from pydoll.browser import Chrome
        from pydoll.browser.options import ChromiumOptions

        options = ChromiumOptions()

        # Core stealth arguments
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process,TranslateUI")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins-discovery")
        options.add_argument("--disable-default-apps")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument(f"--user-agent={USER_AGENT}")

        # Additional stealth options
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-setuid-sandbox")

        # Headless mode
        options.headless = True

        self.browser = Chrome(options=options)
        await self.browser.start()
        self.tab = await self.browser.new_tab()

        # Inject stealth JS
        await self._inject_stealth()

    async def _inject_stealth(self):
        """Inject stealth JavaScript."""
        try:
            await self.tab.execute_script(STEALTH_JS)
        except Exception as e:
            logger.debug("stealth_injection_warning", error=str(e))

    async def _random_delay(self):
        """Add random human-like delay."""
        delay = random.uniform(CONFIG['MIN_DELAY'], CONFIG['MAX_DELAY'])
        await asyncio.sleep(delay)

    async def search_reddit(
        self,
        keywords: List[str],
        subreddits: List[str] = None,
        time_filter: str = "week",
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search Reddit using stealth browser.

        Args:
            keywords: Keywords to search
            subreddits: Subreddits to search in
            time_filter: Time filter (day, week, month)
            max_results: Maximum results

        Returns:
            List of post dictionaries
        """
        if not self.browser:
            await self._init_browser()

        all_results = []
        seen_ids = set()

        target_subreddits = subreddits if subreddits else ["all"]

        try:
            for subreddit in target_subreddits[:5]:
                for keyword in keywords[:3]:
                    try:
                        results = await self._search_subreddit(
                            subreddit=subreddit,
                            query=keyword,
                            time_filter=time_filter,
                            limit=min(10, max_results)
                        )

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

                        await self._random_delay()

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

        finally:
            pass  # Keep browser open for reuse

        return all_results[:max_results]

    async def _search_subreddit(
        self,
        subreddit: str,
        query: str,
        time_filter: str = "week",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search a subreddit using old.reddit.com."""
        # Use old.reddit.com - simpler HTML, easier to parse
        if subreddit.lower() == "all":
            url = f"https://old.reddit.com/search?q={query}&sort=relevance&t={time_filter}"
        else:
            url = f"https://old.reddit.com/r/{subreddit}/search?q={query}&restrict_sr=on&sort=relevance&t={time_filter}"

        await self.tab.go_to(url)
        await asyncio.sleep(CONFIG['PAGE_WAIT'])

        # Re-inject stealth after navigation
        await self._inject_stealth()

        # Get page HTML
        html = await self.tab.page_source

        # Parse results
        return self._parse_search_results(html, limit)

    def _parse_search_results(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse Reddit search results from HTML."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'html.parser')
        results = []

        # Find all search result posts
        posts = soup.select('.search-result, .thing.link')

        for post in posts[:limit]:
            try:
                # Extract post ID
                post_id = post.get('data-fullname', '') or post.get('id', '')
                if post_id.startswith('t3_'):
                    post_id = post_id[3:]
                elif post_id.startswith('thing_t3_'):
                    post_id = post_id[9:]

                if not post_id:
                    continue

                # Extract title
                title_elem = post.select_one('a.search-title, a.title')
                title = title_elem.get_text(strip=True) if title_elem else ""

                # Extract subreddit
                subreddit_elem = post.select_one('a.search-subreddit-link, a.subreddit')
                subreddit = ""
                if subreddit_elem:
                    subreddit = subreddit_elem.get_text(strip=True).replace('r/', '')

                # Extract permalink
                permalink = ""
                if title_elem:
                    href = title_elem.get('href', '')
                    if href.startswith('/r/'):
                        permalink = f"https://www.reddit.com{href}"
                    elif href.startswith('http'):
                        permalink = href

                # Extract body/snippet
                body_elem = post.select_one('.search-result-body, .md')
                body = body_elem.get_text(strip=True)[:500] if body_elem else ""

                # Extract author
                author_elem = post.select_one('a.author')
                author = author_elem.get_text(strip=True) if author_elem else "[unknown]"

                # Extract score
                score_elem = post.select_one('.search-score, .score.unvoted')
                upvotes = 0
                if score_elem:
                    score_text = score_elem.get_text(strip=True)
                    match = re.search(r'(\d+)', score_text.replace(',', ''))
                    if match:
                        upvotes = int(match.group(1))

                # Extract comment count
                comments_elem = post.select_one('a.search-comments, a.comments')
                comment_count = 0
                if comments_elem:
                    comments_text = comments_elem.get_text(strip=True)
                    match = re.search(r'(\d+)', comments_text)
                    if match:
                        comment_count = int(match.group(1))

                # Extract time
                time_elem = post.select_one('time, .search-time')
                post_age_hours = 0
                if time_elem:
                    datetime_str = time_elem.get('datetime', '')
                    if datetime_str:
                        try:
                            posted_time = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                            post_age_hours = (datetime.now(timezone.utc) - posted_time).total_seconds() / 3600
                        except:
                            pass

                results.append({
                    "reddit_id": post_id,
                    "subreddit": subreddit,
                    "post_type": "post",
                    "title": title,
                    "body": body,
                    "author": author,
                    "permalink": permalink,
                    "url": None,
                    "upvotes": upvotes,
                    "comment_count": comment_count,
                    "post_age_hours": round(post_age_hours, 2),
                    "source": "stealth_browser",
                })

            except Exception as e:
                logger.debug("post_parse_error", error=str(e))
                continue

        return results

    async def close(self):
        """Close the browser."""
        if self.browser:
            try:
                await self.browser.stop()
            except:
                pass
            self.browser = None
            self.tab = None


async def search_reddit_stealth(
    keywords: List[str],
    subreddits: List[str] = None,
    max_results: int = 20
) -> List[Dict[str, Any]]:
    """
    Convenience function for stealth Reddit search.

    Args:
        keywords: Keywords to search
        subreddits: Subreddits to limit search
        max_results: Maximum results

    Returns:
        List of post dictionaries
    """
    client = StealthRedditClient()
    try:
        results = await client.search_reddit(keywords, subreddits, max_results=max_results)
        return results
    finally:
        await client.close()


# Sync wrapper for non-async code
def search_reddit_posts(
    keywords: List[str],
    subreddits: List[str] = None,
    max_results: int = 20,
    fetch_details: bool = False
) -> List[Dict[str, Any]]:
    """Synchronous wrapper for stealth Reddit search."""
    return asyncio.run(search_reddit_stealth(keywords, subreddits, max_results))

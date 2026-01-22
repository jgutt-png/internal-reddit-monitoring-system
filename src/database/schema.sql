-- Reddit Automation Database Schema
-- PostgreSQL 14+

-- Target subreddits to monitor
CREATE TABLE IF NOT EXISTS subreddits (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT true,
    scan_frequency_minutes INT DEFAULT 30,
    last_scanned_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Keywords/phrases to match
CREATE TABLE IF NOT EXISTS keywords (
    id SERIAL PRIMARY KEY,
    phrase VARCHAR(255) NOT NULL,
    category VARCHAR(50),  -- 'buying', 'selling', 'investing', 'renting', etc.
    weight DECIMAL(3,2) DEFAULT 1.0,  -- Importance multiplier
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Found opportunities
CREATE TABLE IF NOT EXISTS opportunities (
    id SERIAL PRIMARY KEY,
    reddit_id VARCHAR(20) NOT NULL UNIQUE,  -- Reddit's post/comment ID
    subreddit VARCHAR(50) NOT NULL,
    post_type VARCHAR(10) NOT NULL,  -- 'post' or 'comment'
    title TEXT,
    body TEXT NOT NULL,
    author VARCHAR(50),
    permalink VARCHAR(500) NOT NULL,
    url TEXT,  -- Original URL if link post
    upvotes INT DEFAULT 0,
    comment_count INT DEFAULT 0,
    post_age_hours DECIMAL(10,2),

    -- Scoring
    relevance_score DECIMAL(3,2),  -- 0.0 to 1.0
    engagement_potential VARCHAR(20),  -- 'high', 'medium', 'low'
    matched_keywords JSONB DEFAULT '[]'::jsonb,
    ai_analysis JSONB,  -- Full AI analysis response

    -- Response
    suggested_response TEXT,

    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'approved', 'rejected', 'responded', 'expired'
    reviewed_at TIMESTAMP,
    reviewed_by VARCHAR(100),
    responded_at TIMESTAMP,

    -- Slack tracking
    slack_message_ts VARCHAR(50),  -- Slack message timestamp for updates

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Track responses posted
CREATE TABLE IF NOT EXISTS responses (
    id SERIAL PRIMARY KEY,
    opportunity_id INT REFERENCES opportunities(id) ON DELETE CASCADE,
    response_text TEXT NOT NULL,
    reddit_comment_id VARCHAR(20),
    posted_at TIMESTAMP DEFAULT NOW(),
    posted_by VARCHAR(100),
    upvotes_received INT DEFAULT 0,
    replies_received INT DEFAULT 0,
    last_checked TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Scan history for monitoring
CREATE TABLE IF NOT EXISTS scan_logs (
    id SERIAL PRIMARY KEY,
    subreddit VARCHAR(50) NOT NULL,
    posts_scanned INT DEFAULT 0,
    opportunities_found INT DEFAULT 0,
    errors TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    duration_seconds DECIMAL(10,2)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_opportunities_status ON opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opportunities_subreddit ON opportunities(subreddit);
CREATE INDEX IF NOT EXISTS idx_opportunities_score ON opportunities(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_opportunities_created ON opportunities(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_opportunities_reddit_id ON opportunities(reddit_id);
CREATE INDEX IF NOT EXISTS idx_scan_logs_subreddit ON scan_logs(subreddit);
CREATE INDEX IF NOT EXISTS idx_scan_logs_started ON scan_logs(started_at DESC);

-- Insert default subreddits - Florida Wholesale Focus
INSERT INTO subreddits (name, is_active) VALUES
    -- Primary - High intent wholesale/investing
    ('WholesaleRealestate', true),
    ('wholesaling', true),
    ('realestateinvesting', true),
    ('flipping', true),
    -- General real estate
    ('RealEstate', true),
    ('CommercialRealEstate', true),
    -- Florida specific
    ('FloridaRealEstate', true),
    ('florida', true),
    ('Miami', true),
    ('tampa', true),
    ('orlando', true),
    ('jacksonville', true)
ON CONFLICT (name) DO NOTHING;

-- Insert default keywords - Florida Wholesale Focus
INSERT INTO keywords (phrase, category, weight) VALUES
    -- Florida off-market (highest priority)
    ('florida off market', 'florida_off_market', 1.5),
    ('FL wholesale', 'florida_off_market', 1.5),
    ('florida wholesale deal', 'florida_off_market', 1.5),
    ('miami off market', 'florida_off_market', 1.5),
    ('tampa wholesale', 'florida_off_market', 1.4),
    ('orlando wholesale', 'florida_off_market', 1.4),
    -- Deal types
    ('motivated seller', 'deal_types', 1.3),
    ('tax lien', 'deal_types', 1.3),
    ('probate', 'deal_types', 1.4),
    ('distressed property', 'deal_types', 1.3),
    ('pre-foreclosure', 'deal_types', 1.4),
    ('foreclosure', 'deal_types', 1.2),
    ('inherited property', 'deal_types', 1.3),
    ('absentee owner', 'deal_types', 1.2),
    -- Investor intent (high value)
    ('looking for deals', 'investor_intent', 1.4),
    ('investor network', 'investor_intent', 1.3),
    ('off market leads', 'investor_intent', 1.5),
    ('cash buyer', 'investor_intent', 1.3),
    ('need deals', 'investor_intent', 1.4),
    ('deal flow', 'investor_intent', 1.3),
    ('buyers list', 'investor_intent', 1.2),
    -- Wholesaling terms
    ('wholesale', 'wholesaling', 1.2),
    ('assignment', 'wholesaling', 1.2),
    ('ARV', 'wholesaling', 1.1),
    ('MAO', 'wholesaling', 1.1),
    ('driving for dollars', 'wholesaling', 1.2),
    ('skip tracing', 'wholesaling', 1.2),
    -- Florida markets
    ('miami', 'florida_markets', 1.1),
    ('tampa', 'florida_markets', 1.1),
    ('orlando', 'florida_markets', 1.1),
    ('jacksonville', 'florida_markets', 1.1),
    ('south florida', 'florida_markets', 1.2),
    ('fort lauderdale', 'florida_markets', 1.1)
ON CONFLICT DO NOTHING;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for opportunities
DROP TRIGGER IF EXISTS update_opportunities_updated_at ON opportunities;
CREATE TRIGGER update_opportunities_updated_at
    BEFORE UPDATE ON opportunities
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

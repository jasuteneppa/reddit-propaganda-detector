import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    subreddit TEXT,
    author TEXT,
    title TEXT,
    url TEXT,
    domain TEXT,
    permalink TEXT,
    is_video INTEGER,
    over_18 INTEGER,
    crosspost_parent TEXT,
    created_utc REAL,
    first_seen REAL,
    first_seen_source TEXT,
    last_comment_snap REAL
);

-- One row per post per observation: rank in a listing, or rank NULL when
-- the snapshot came from fetching the post's comment page.
CREATE TABLE IF NOT EXISTS post_snapshots (
    post_id TEXT,
    ts REAL,
    source TEXT,
    rank INTEGER,
    score INTEGER,
    upvote_ratio REAL,
    num_comments INTEGER
);
CREATE INDEX IF NOT EXISTS idx_post_snap ON post_snapshots(post_id, ts);

CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    post_id TEXT,
    parent_id TEXT,
    author TEXT,
    body TEXT,
    created_utc REAL,
    first_seen REAL
);
CREATE INDEX IF NOT EXISTS idx_comments_post ON comments(post_id);

-- top_rank is the position among top-level comments in "best" sort
-- (what readers see by default); NULL for replies.
CREATE TABLE IF NOT EXISTS comment_snapshots (
    comment_id TEXT,
    post_id TEXT,
    ts REAL,
    top_rank INTEGER,
    depth INTEGER,
    score INTEGER
);
CREATE INDEX IF NOT EXISTS idx_comment_snap ON comment_snapshots(post_id, ts);

-- Filled lazily: a name is inserted when first seen, details fetched later.
CREATE TABLE IF NOT EXISTS authors (
    name TEXT PRIMARY KEY,
    status TEXT,              -- ok | suspended | not_found
    created_utc REAL,
    link_karma INTEGER,
    comment_karma INTEGER,
    default_avatar INTEGER,
    verified_email INTEGER,
    fetched_at REAL
);
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn

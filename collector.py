"""Snapshot r/popular, target subreddits, comment trees and author metadata.

Run continuously:   python collector.py
Single pass (test): python collector.py --once
"""
import argparse
import logging
import time
import tomllib

import praw
import prawcore

import db

log = logging.getLogger("collector")


def load_config(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def make_reddit(cfg):
    r = cfg["reddit"]
    # No username/password: application-only, read-only access.
    return praw.Reddit(
        client_id=r["client_id"],
        client_secret=r["client_secret"],
        user_agent=r["user_agent"],
    )


def author_name(thing):
    return thing.author.name if thing.author else None


def queue_author(conn, name):
    if name:
        conn.execute("INSERT OR IGNORE INTO authors(name) VALUES (?)", (name,))


def upsert_post(conn, s, now, source):
    conn.execute(
        """INSERT OR IGNORE INTO posts
           (id, subreddit, author, title, url, domain, permalink, is_video, over_18,
            crosspost_parent, created_utc, first_seen, first_seen_source)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            s.id, s.subreddit.display_name, author_name(s), s.title, s.url, s.domain,
            s.permalink, int(s.is_video), int(s.over_18),
            getattr(s, "crosspost_parent", None), s.created_utc, now, source,
        ),
    )
    queue_author(conn, author_name(s))


def snapshot_listing(reddit, conn, name, limit, params=None):
    now = time.time()
    n = 0
    for rank, s in enumerate(reddit.subreddit(name).hot(limit=limit, params=params or {}), 1):
        upsert_post(conn, s, now, name)
        conn.execute(
            "INSERT INTO post_snapshots VALUES (?,?,?,?,?,?,?)",
            (s.id, now, name, rank, s.score, s.upvote_ratio, s.num_comments),
        )
        n += 1
    return n


def snapshot_comments(reddit, conn, post_id, limit):
    s = reddit.submission(id=post_id)
    s.comment_sort = "confidence"  # "best": the default order readers see
    s.comment_limit = limit
    s.comments.replace_more(limit=0)
    now = time.time()

    conn.execute(
        "INSERT INTO post_snapshots VALUES (?,?,?,?,?,?,?)",
        (s.id, now, "comments", None, s.score, s.upvote_ratio, s.num_comments),
    )
    top_rank = 0
    n = 0
    for c in s.comments.list():  # breadth-first, so top-level comments come first in order
        rank = None
        if c.is_root:
            top_rank += 1
            rank = top_rank
        name = author_name(c)
        conn.execute(
            "INSERT OR IGNORE INTO comments VALUES (?,?,?,?,?,?,?)",
            (c.id, post_id, c.parent_id, name, c.body, c.created_utc, now),
        )
        conn.execute(
            "INSERT INTO comment_snapshots VALUES (?,?,?,?,?,?)",
            (c.id, post_id, now, rank, getattr(c, "depth", None), c.score),
        )
        queue_author(conn, name)
        n += 1
    conn.execute("UPDATE posts SET last_comment_snap = ? WHERE id = ?", (now, post_id))
    return n


def due_posts(conn, schedule, now):
    """Posts whose comment tree is due for a snapshot, most overdue first."""
    max_age = schedule[-1][0] * 3600
    rows = conn.execute(
        "SELECT id, created_utc, last_comment_snap FROM posts WHERE created_utc > ?",
        (now - max_age,),
    ).fetchall()
    due = []
    for pid, created, last in rows:
        age_h = (now - created) / 3600
        interval = next(mins for hours, mins in schedule if age_h < hours) * 60
        overdue = now - (last or 0) - interval
        if overdue >= 0:
            due.append((overdue, pid))
    due.sort(reverse=True)
    return [pid for _, pid in due]


def fetch_authors(reddit, conn, max_n):
    rows = conn.execute(
        "SELECT name FROM authors WHERE fetched_at IS NULL LIMIT ?", (max_n,)
    ).fetchall()
    for (name,) in rows:
        now = time.time()
        try:
            u = reddit.redditor(name)
            if getattr(u, "is_suspended", False):
                conn.execute(
                    "UPDATE authors SET status='suspended', fetched_at=? WHERE name=?", (now, name)
                )
                continue
            icon = getattr(u, "icon_img", "") or ""
            default_avatar = "avatar_default" in icon and not getattr(u, "snoovatar_img", "")
            conn.execute(
                """UPDATE authors SET status='ok', created_utc=?, link_karma=?, comment_karma=?,
                   default_avatar=?, verified_email=?, fetched_at=? WHERE name=?""",
                (
                    u.created_utc, u.link_karma, u.comment_karma, int(default_avatar),
                    int(bool(getattr(u, "has_verified_email", False))), now, name,
                ),
            )
        except (prawcore.NotFound, prawcore.Forbidden):
            conn.execute(
                "UPDATE authors SET status='not_found', fetched_at=? WHERE name=?", (now, name)
            )
    return len(rows)


def run_cycle(reddit, conn, cfg):
    c = cfg["collector"]
    start = time.time()

    posts_seen = 0
    sources = [("popular", c["popular_limit"], {"g": c.get("popular_geo", "GLOBAL")})]
    sources += [(name, c["subreddit_limit"], None) for name in c["subreddits"]]
    for name, limit, params in sources:
        try:
            posts_seen += snapshot_listing(reddit, conn, name, limit, params)
        except prawcore.PrawcoreException as e:
            log.warning("listing r/%s failed: %s", name, e)
        conn.commit()

    due = due_posts(conn, c["comment_schedule"], time.time())
    trees = comments_seen = 0
    for pid in due[: c["max_comment_snapshots"]]:
        try:
            comments_seen += snapshot_comments(reddit, conn, pid, c["comment_limit"])
            trees += 1
        except prawcore.PrawcoreException as e:
            log.warning("comments %s failed: %s", pid, e)
        conn.commit()

    authors = fetch_authors(reddit, conn, c["max_author_fetches"])
    conn.commit()

    log.info(
        "cycle done in %.0fs: %d listing rows, %d/%d due trees (%d comments), %d authors",
        time.time() - start, posts_seen, trees, len(due), comments_seen, authors,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("--once", action="store_true", help="run a single cycle and exit")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(args.config)
    reddit = make_reddit(cfg)
    conn = db.connect(cfg["collector"]["db_path"])

    while True:
        start = time.time()
        try:
            run_cycle(reddit, conn, cfg)
        except prawcore.PrawcoreException as e:
            log.error("cycle aborted: %s", e)
        if args.once:
            break
        time.sleep(max(0, cfg["collector"]["cycle_seconds"] - (time.time() - start)))


if __name__ == "__main__":
    main()

"""Quick look at what the collector has gathered: python stats.py [db_path]"""
import sqlite3
import sys
import time

path = sys.argv[1] if len(sys.argv) > 1 else "watch.db"
conn = sqlite3.connect(path)
q = lambda sql: conn.execute(sql).fetchone()[0]

print(f"posts tracked:      {q('SELECT COUNT(*) FROM posts')}")
print(f"post snapshots:     {q('SELECT COUNT(*) FROM post_snapshots')}")
print(f"comments:           {q('SELECT COUNT(*) FROM comments')}")
print(f"comment snapshots:  {q('SELECT COUNT(*) FROM comment_snapshots')}")
print(f"authors known:      {q('SELECT COUNT(*) FROM authors')}"
      f" ({q('SELECT COUNT(*) FROM authors WHERE fetched_at IS NOT NULL')} fetched)")

first = q("SELECT MIN(ts) FROM post_snapshots")
if first:
    print(f"collecting for:     {(time.time() - first) / 3600:.1f} hours")

print("\ncurrent top 10 of r/popular:")
for rank, score, ncom, sub, title in conn.execute(
    """SELECT s.rank, s.score, s.num_comments, p.subreddit, p.title
       FROM post_snapshots s JOIN posts p ON p.id = s.post_id
       WHERE s.source = 'popular' AND s.ts = (SELECT MAX(ts) FROM post_snapshots WHERE source = 'popular')
       ORDER BY s.rank LIMIT 10"""
):
    print(f"  {rank:>3}. {score:>6} pts {ncom:>5} cmts  r/{sub}: {title[:70]}")

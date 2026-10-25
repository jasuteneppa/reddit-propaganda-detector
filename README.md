# Reddit Coordination Watch

**Open-source tool for detecting coordinated inauthentic behavior, bot activity and propaganda campaigns on Reddit.**

Some posts reach r/popular because people care about them. Others get there because someone pushed them: bot-filled comment sections, comments that rocket to the top within minutes, old videos reposted with new captions whenever the news makes them useful. Reddit Coordination Watch collects the data needed to tell those apart, by looking at *how* content spreads rather than *what* it says.

> **Status:** early. The data collector works; the analysis and detection layer is being built. Contributions welcome.

## Why behavior, not content

Judging posts by their opinions would flag real people who sincerely hold those views and would make the tool easy to dismiss as partisan. Coordination leaves traces regardless of politics:

| Signal | What it looks like |
| --- | --- |
| Comment velocity | A thread fills with comments far faster than comparable posts in the same subreddit |
| Comment rank jumps | Late comments suddenly leap past established top comments |
| Account patterns | Unusually many new, default-named, default-avatar or recently reactivated accounts |
| Repost networks | The same image or video posted repeatedly across generic "viral" subreddits |
| Origin tracing | Content crossposted from violence- or outrage-focused subreddits and reframed |
| Periodic resurfacing | Old footage that reappears every few months with a new story attached |

The detector is designed to be politically neutral: it measures coordination wherever it happens.

## What the collector does

Every 5 minutes, `collector.py`:

- snapshots the rank, score, upvote ratio and comment count of r/popular and a configurable list of subreddits
- re-snapshots the comment trees of recent posts in "best" order (every 5 min for posts under 2 h old, then every 15 min, then hourly up to 24 h), so comment-rank jumps and fill speed can be measured
- looks up basic public metadata for commenters (account age, karma, default avatar, suspended status)
- records crosspost parents for tracing where content came from

Everything goes into a single SQLite file.

## Requirements

- Python 3.11+
- **Reddit API credentials.** Since November 2025, Reddit requires approval for new API access under its [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy). Academic researchers can apply through the [Reddit for Researchers program](https://support.reddithelp.com/hc/en-us/articles/49381918834964-Reddit-for-Researchers-Program). If you already have a script app, it works as-is.

## Setup

```
pip install -r requirements.txt
cp config.example.toml config.toml   # then fill in the [reddit] section
python collector.py --once           # one test pass
python stats.py                      # see what was collected
python collector.py                  # run continuously
```

The collector uses read-only, application-only access and stays well within Reddit's rate limits.

## Responsible use

- Publish findings about **posts and patterns**, not individual users. Many real people have default usernames; no single signal proves anything.
- Respect Reddit's API terms: don't resell or redistribute raw data, and don't use it to train AI models.
- Purge content that its authors delete, and don't keep raw data longer than you need it.
- When sharing a suspicious thread, use archive links or screenshots so you don't send a brigade into it.

## Roadmap

- [ ] Data retention limits and purging of deleted content
- [ ] Comment rank-jump detection
- [ ] Comment-velocity baselines per subreddit
- [ ] Perceptual hashing of images and video frames for repost and resurfacing tracking
- [ ] Per-thread coordination report

## Contributing

Issues and pull requests are welcome, especially from researchers who study disinformation or platform manipulation. If you have Reddit API access and want to help collect or analyze data, open an issue.

## License

MIT

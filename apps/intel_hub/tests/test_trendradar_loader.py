import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


class TrendRadarLoaderTests(unittest.TestCase):
    def test_loader_reads_json_input(self) -> None:
        from apps.intel_hub.ingest.trendradar_loader import load_latest_raw_signals

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output" / "news"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "2026-04-01.json").write_text(
                json.dumps(
                    {
                        "items": [
                            {
                                "title": "JSON signal",
                                "summary": "from json",
                                "source_url": "https://example.com/json",
                                "source_name": "Json Source",
                                "published_at": "2026-04-01T10:00:00+08:00",
                                "content": "json content",
                                "platform": "news",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            records = load_latest_raw_signals(output_dir.parent, include_rss=False)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["title"], "JSON signal")
            self.assertEqual(records[0]["raw_source_type"], "json")

    def test_loader_reads_jsonl_input(self) -> None:
        from apps.intel_hub.ingest.trendradar_loader import load_latest_raw_signals

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output" / "news"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "2026-04-02.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "headline": "JSONL signal",
                                "description": "from jsonl",
                                "url": "https://example.com/jsonl",
                                "media": "Jsonl Source",
                                "created_at": "2026-04-02T09:00:00+08:00",
                                "text": "jsonl body",
                            },
                            ensure_ascii=False,
                        )
                    ]
                ),
                encoding="utf-8",
            )

            records = load_latest_raw_signals(output_dir.parent, include_rss=False)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["title"], "JSONL signal")
            self.assertEqual(records[0]["raw_source_type"], "jsonl")

    def test_loader_reads_specialized_news_sqlite_schema(self) -> None:
        from apps.intel_hub.ingest.trendradar_loader import load_latest_raw_signals

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output" / "news"
            output_dir.mkdir(parents=True, exist_ok=True)
            db_path = output_dir / "2026-04-03.db"
            self._create_news_db_fixture(db_path)

            records = load_latest_raw_signals(output_dir.parent, include_rss=False)

            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record["title"], "Alpha AI launches new capability")
            self.assertEqual(record["platform"], "xhs")
            self.assertEqual(record["source_name"], "XiaoHongShu")
            self.assertEqual(record["author"], "Alice")
            self.assertEqual(record["account"], "AlphaOfficial")
            self.assertEqual(record["captured_at"], "2026-04-03T10:10:00+08:00")
            self.assertEqual(record["rank"], 3)
            self.assertEqual(record["watchlist_hits"], ["competitor_alpha"])
            self.assertEqual(record["raw_source_type"], "db_news_items")

    def test_loader_reads_specialized_rss_sqlite_schema(self) -> None:
        from apps.intel_hub.ingest.trendradar_loader import load_latest_raw_signals

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output" / "rss"
            output_dir.mkdir(parents=True, exist_ok=True)
            db_path = output_dir / "2026-04-03.db"
            self._create_rss_db_fixture(db_path)

            records = load_latest_raw_signals(output_dir.parent, include_rss=True)

            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(record["title"], "RSS item title")
            self.assertEqual(record["source_name"], "Feed Source")
            self.assertEqual(record["platform"], "rss")
            self.assertEqual(record["source_url"], "https://feed.example.com/post")
            self.assertEqual(record["raw_source_type"], "db_rss_items")

    def test_loader_tolerates_missing_fields(self) -> None:
        from apps.intel_hub.ingest.trendradar_loader import load_latest_raw_signals

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output" / "news"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "2026-04-01.json").write_text(
                json.dumps(
                    [
                        {
                            "content": "content only still becomes a signal",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            records = load_latest_raw_signals(output_dir.parent, include_rss=False)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["title"], "content only still becomes a signal")

    def test_loader_prefers_latest_batch_when_multiple_files_exist(self) -> None:
        from apps.intel_hub.ingest.trendradar_loader import load_latest_raw_signals

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output" / "news"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "2026-04-01.json").write_text(
                json.dumps([{"title": "older", "content": "older"}], ensure_ascii=False),
                encoding="utf-8",
            )
            (output_dir / "2026-04-09.json").write_text(
                json.dumps([{"title": "latest", "content": "latest"}], ensure_ascii=False),
                encoding="utf-8",
            )

            records = load_latest_raw_signals(output_dir.parent, include_rss=False)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["title"], "latest")

    def _create_news_db_fixture(self, db_path: Path) -> None:
        with sqlite3.connect(db_path) as connection:
            connection.executescript(
                """
                CREATE TABLE platforms (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    display_name TEXT,
                    source_type TEXT
                );
                CREATE TABLE news_items (
                    id INTEGER PRIMARY KEY,
                    platform_id INTEGER,
                    title TEXT,
                    summary TEXT,
                    content TEXT,
                    url TEXT,
                    author TEXT,
                    account TEXT,
                    published_at TEXT,
                    captured_at TEXT,
                    keyword TEXT,
                    watchlist_hits TEXT,
                    hot_score REAL
                );
                CREATE TABLE rank_history (
                    id INTEGER PRIMARY KEY,
                    news_item_id INTEGER,
                    rank INTEGER,
                    score REAL,
                    captured_at TEXT
                );
                """
            )
            connection.execute(
                "INSERT INTO platforms (id, name, display_name, source_type) VALUES (1, 'xhs', 'XiaoHongShu', 'social')"
            )
            connection.execute(
                """
                INSERT INTO news_items (
                    id, platform_id, title, summary, content, url, author, account,
                    published_at, captured_at, keyword, watchlist_hits, hot_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    10,
                    1,
                    "Alpha AI launches new capability",
                    "Alpha summary",
                    "Alpha long content",
                    "https://example.com/alpha",
                    "Alice",
                    "AlphaOfficial",
                    "2026-04-03T09:00:00+08:00",
                    "2026-04-03T10:10:00+08:00",
                    "competitor alpha",
                    "competitor_alpha",
                    88.5,
                ),
            )
            connection.execute(
                "INSERT INTO rank_history (news_item_id, rank, score, captured_at) VALUES (?, ?, ?, ?)",
                (10, 6, 70.0, "2026-04-03T09:30:00+08:00"),
            )
            connection.execute(
                "INSERT INTO rank_history (news_item_id, rank, score, captured_at) VALUES (?, ?, ?, ?)",
                (10, 3, 89.0, "2026-04-03T10:20:00+08:00"),
            )

    def _create_rss_db_fixture(self, db_path: Path) -> None:
        with sqlite3.connect(db_path) as connection:
            connection.executescript(
                """
                CREATE TABLE rss_feeds (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    site_url TEXT,
                    feed_url TEXT
                );
                CREATE TABLE rss_items (
                    id INTEGER PRIMARY KEY,
                    feed_id INTEGER,
                    title TEXT,
                    summary TEXT,
                    content TEXT,
                    url TEXT,
                    author TEXT,
                    published_at TEXT,
                    captured_at TEXT,
                    keyword TEXT,
                    watchlist_hits TEXT
                );
                """
            )
            connection.execute(
                "INSERT INTO rss_feeds (id, title, site_url, feed_url) VALUES (1, 'Feed Source', 'https://feed.example.com', 'https://feed.example.com/rss')"
            )
            connection.execute(
                """
                INSERT INTO rss_items (
                    id, feed_id, title, summary, content, url, author, published_at,
                    captured_at, keyword, watchlist_hits
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    20,
                    1,
                    "RSS item title",
                    "rss summary",
                    "rss content",
                    "https://feed.example.com/post",
                    "Reporter",
                    "2026-04-03T11:00:00+08:00",
                    "2026-04-03T11:10:00+08:00",
                    "ai-native intelligence hub",
                    "ai_native_intel_hub",
                ),
            )


if __name__ == "__main__":
    unittest.main()

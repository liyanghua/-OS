import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "data" / "fixtures" / "mediacrawler_output" / "xhs" / "jsonl"


class MediaCrawlerLoaderJSONLTests(unittest.TestCase):
    def test_load_jsonl_fixture(self) -> None:
        from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

        records = load_mediacrawler_records(FIXTURE_DIR)
        self.assertGreaterEqual(len(records), 5)

    def test_fields_mapped_correctly(self) -> None:
        from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

        records = load_mediacrawler_records(FIXTURE_DIR)
        first = records[0]
        self.assertEqual(first["platform"], "xiaohongshu")
        self.assertEqual(first["source_name"], "小红书")
        self.assertIn("note_tc_", first["source_url"])
        self.assertIn("liked_count", first["metrics"])
        self.assertIn("engagement", first["metrics"])
        self.assertTrue(first["title"])
        self.assertTrue(first["raw_text"])
        self.assertTrue(first["author"])

    def test_keyword_preserved(self) -> None:
        from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

        records = load_mediacrawler_records(FIXTURE_DIR)
        keywords = [r["keyword"] for r in records if r.get("keyword")]
        self.assertTrue(any("桌布" in k or "桌垫" in k for k in keywords))

    def test_metrics_engagement_sum(self) -> None:
        from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

        records = load_mediacrawler_records(FIXTURE_DIR)
        for r in records:
            m = r["metrics"]
            expected = m["liked_count"] + m["collected_count"] + m["comment_count"] + m["share_count"]
            self.assertEqual(m["engagement"], expected)

    def test_published_at_is_iso(self) -> None:
        from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

        records = load_mediacrawler_records(FIXTURE_DIR)
        for r in records:
            self.assertIsNotNone(r["published_at"])
            self.assertIn("T", r["published_at"])

    def test_tags_parsed(self) -> None:
        from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

        records = load_mediacrawler_records(FIXTURE_DIR)
        for r in records:
            self.assertIsInstance(r["tags"], list)
        first_tags = records[0]["tags"]
        self.assertIn("桌布", first_tags)


class MediaCrawlerLoaderJSONTests(unittest.TestCase):
    def test_load_json_array(self) -> None:
        from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "search_contents_2026-04-02.json"
            items = [
                {
                    "note_id": "json_note_1",
                    "title": "JSON测试桌布",
                    "desc": "这是一个JSON格式的桌布笔记",
                    "note_url": "https://www.xiaohongshu.com/explore/json_note_1",
                    "time": 1743580800,
                    "last_modify_ts": 1743580900000,
                    "liked_count": "100",
                    "collected_count": "50",
                    "comment_count": "20",
                    "share_count": "10",
                    "nickname": "测试用户",
                    "user_id": "u_json",
                    "source_keyword": "桌布",
                    "tag_list": "桌布,测试",
                },
            ]
            json_path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
            records = load_mediacrawler_records(tmpdir)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["platform"], "xiaohongshu")
            self.assertEqual(records[0]["raw_source_type"], "mediacrawler_json")


class MediaCrawlerLoaderSQLiteTests(unittest.TestCase):
    def test_load_sqlite(self) -> None:
        from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "sqlite_tables.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE xhs_note (
                    id INTEGER PRIMARY KEY,
                    note_id TEXT,
                    type TEXT,
                    title TEXT,
                    desc TEXT,
                    note_url TEXT,
                    time INTEGER,
                    last_modify_ts INTEGER,
                    liked_count TEXT,
                    collected_count TEXT,
                    comment_count TEXT,
                    share_count TEXT,
                    nickname TEXT,
                    user_id TEXT,
                    source_keyword TEXT,
                    tag_list TEXT,
                    ip_location TEXT
                )
            """)
            conn.execute("""
                INSERT INTO xhs_note (note_id, type, title, desc, note_url, time, last_modify_ts,
                    liked_count, collected_count, comment_count, share_count,
                    nickname, user_id, source_keyword, tag_list, ip_location)
                VALUES ('sqlite_note_1', 'normal', 'SQLite桌布测试', '防水桌布推荐',
                    'https://www.xiaohongshu.com/explore/sqlite_note_1',
                    1743580800, 1743580900000,
                    '200', '80', '30', '15', '数据库测试', 'u_sqlite', '桌布', '桌布,防水', '深圳')
            """)
            conn.commit()
            conn.close()

            records = load_mediacrawler_records(tmpdir)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["raw_source_type"], "mediacrawler_sqlite")
            self.assertEqual(records[0]["keyword"], "桌布")


class MediaCrawlerLoaderEdgeCaseTests(unittest.TestCase):
    def test_nonexistent_path_returns_empty(self) -> None:
        from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

        records = load_mediacrawler_records("/nonexistent/path")
        self.assertEqual(records, [])

    def test_empty_dir_returns_empty(self) -> None:
        from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

        with tempfile.TemporaryDirectory() as tmpdir:
            records = load_mediacrawler_records(tmpdir)
            self.assertEqual(records, [])

    def test_comments_only_jsonl_filtered_out(self) -> None:
        from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

        with tempfile.TemporaryDirectory() as tmpdir:
            comments_path = Path(tmpdir) / "search_comments_2026-04-02.jsonl"
            comment = {
                "comment_id": "c001",
                "note_id": "",
                "content": "好看",
                "nickname": "user",
            }
            comments_path.write_text(json.dumps(comment, ensure_ascii=False), encoding="utf-8")
            records = load_mediacrawler_records(tmpdir)
            self.assertEqual(records, [])

    def test_missing_title_uses_desc(self) -> None:
        from apps.intel_hub.ingest.mediacrawler_loader import load_mediacrawler_records

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "notes.jsonl"
            item = {
                "note_id": "no_title",
                "title": "",
                "desc": "这是描述用作标题" * 5,
                "note_url": "https://www.xiaohongshu.com/explore/no_title",
                "time": 1743580800,
                "last_modify_ts": 1743580900000,
                "liked_count": "10",
                "collected_count": "5",
                "comment_count": "2",
                "share_count": "1",
                "nickname": "用户",
                "user_id": "u",
                "source_keyword": "桌布",
                "tag_list": "",
            }
            path.write_text(json.dumps(item, ensure_ascii=False), encoding="utf-8")
            records = load_mediacrawler_records(tmpdir)
            self.assertEqual(len(records), 1)
            self.assertTrue(records[0]["title"])


if __name__ == "__main__":
    unittest.main()

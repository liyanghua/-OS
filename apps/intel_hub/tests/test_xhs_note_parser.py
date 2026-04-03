"""XHS 笔记解析器测试 — 验证 raw dict -> XHSNoteRaw -> XHSParsedNote。"""

from __future__ import annotations

import pytest

from apps.intel_hub.parsing.xhs_note_parser import parse_note, parse_raw_note


FIXTURE_NOTE_CREAMY = {
    "note_id": "test_creamy_001",
    "type": "normal",
    "title": "出租屋改造｜奶油风桌布让小窝瞬间高级✨",
    "desc": "租房党的福音！这款奶油风桌布真的太出片了 铺上去瞬间提升高级感 #出租屋改造[话题]# #奶油风[话题]# #桌布[话题]#",
    "user_id": "uid_001",
    "nickname": "小花花",
    "liked_count": "2300",
    "collected_count": "1800",
    "comment_count": "150",
    "share_count": "80",
    "image_list": "http://sns-webpic-qc.xhscdn.com/202604030738/abc123/img-001!nd_dft_wlteh_jpg_3,http://sns-webpic-qc.xhscdn.com/202604030738/def456/img-002!nd_dft_wlteh_jpg_3",
    "tag_list": "出租屋改造,奶油风,桌布",
    "time": 1743600000000,
    "last_modify_ts": 1743700000000,
    "note_url": "",
    "source_keyword": "桌布",
    "ip_location": "",
}

FIXTURE_NOTE_WATERPROOF = {
    "note_id": "test_waterproof_002",
    "type": "normal",
    "title": "终于找到了防水防油又好看的餐桌布！",
    "desc": "我家是黑胡桃餐桌，实木不防水耐脏 最近入了这款PVC桌布，防水防油好打理，一擦就干净！尺寸可选，平价又好看",
    "user_id": "uid_002",
    "nickname": "居家小达人",
    "liked_count": "5600",
    "collected_count": "4200",
    "comment_count": "320",
    "share_count": "150",
    "image_list": "http://sns-webpic-qc.xhscdn.com/202604030738/ghi789/cover!nd_dft_wlteh_jpg_3",
    "tag_list": "餐桌布,防水,好打理",
    "time": 1743500000000,
    "last_modify_ts": 1743600000000,
    "note_url": "",
    "source_keyword": "餐桌布",
    "ip_location": "",
}

FIXTURE_NOTE_RISK = {
    "note_id": "test_risk_003",
    "type": "normal",
    "title": "桌布踩雷合集！千万别买这几款",
    "desc": "买了五六款桌布踩了无数坑：卷边严重、廉价感十足、尺寸不合。分享给大家避坑！",
    "user_id": "uid_003",
    "nickname": "真实测评家",
    "liked_count": "1200",
    "collected_count": "900",
    "comment_count": "280",
    "share_count": "60",
    "image_list": "",
    "tag_list": "踩坑,避坑,桌布",
    "time": 1743400000000,
    "last_modify_ts": 1743500000000,
    "note_url": "https://www.xiaohongshu.com/explore/test_risk_003",
    "source_keyword": "桌布",
    "ip_location": "上海",
}

FIXTURE_COMMENTS_RISK = [
    {"comment_id": "c001", "note_id": "test_risk_003", "content": "真的吗？我刚下单了一款", "nickname": "用户A", "like_count": "5", "sub_comment_count": "0", "parent_comment_id": 0},
    {"comment_id": "c002", "note_id": "test_risk_003", "content": "卷边太严重了 廉价感 退货了", "nickname": "用户B", "like_count": "12", "sub_comment_count": "2", "parent_comment_id": 0},
    {"comment_id": "c003", "note_id": "test_risk_003", "content": "求链接 想看看到底多差", "nickname": "用户C", "like_count": "3", "sub_comment_count": "0", "parent_comment_id": 0},
]


class TestParseRawNote:
    def test_basic_fields(self):
        raw = parse_raw_note(FIXTURE_NOTE_CREAMY)
        assert raw.note_id == "test_creamy_001"
        assert raw.title_text == "出租屋改造｜奶油风桌布让小窝瞬间高级✨"
        assert raw.like_count == 2300
        assert raw.collect_count == 1800
        assert raw.author_name == "小花花"

    def test_image_persistent_url(self):
        raw = parse_raw_note(FIXTURE_NOTE_CREAMY)
        assert len(raw.image_list) == 2
        assert "sns-img-bd.xhscdn.com" in raw.image_list[0].url
        assert raw.image_list[0].is_cover is True
        assert raw.image_list[1].is_cover is False

    def test_tags_include_inline_topics(self):
        raw = parse_raw_note(FIXTURE_NOTE_CREAMY)
        tag_lower = [t.lower() for t in raw.tag_list]
        assert "出租屋改造" in tag_lower
        assert "奶油风" in tag_lower

    def test_note_url_fallback(self):
        raw = parse_raw_note(FIXTURE_NOTE_CREAMY)
        assert "xiaohongshu.com" in raw.note_url

    def test_empty_image_list(self):
        raw = parse_raw_note(FIXTURE_NOTE_RISK)
        assert raw.image_count == 0

    def test_comments_association(self):
        raw = parse_raw_note(FIXTURE_NOTE_RISK, comments=FIXTURE_COMMENTS_RISK)
        assert len(raw.comments) == 3
        assert raw.comments[0].content == "真的吗？我刚下单了一款"
        assert raw.top_comments[0].like_count >= raw.top_comments[-1].like_count


class TestParseNote:
    def test_normalized_fields(self):
        raw = parse_raw_note(FIXTURE_NOTE_CREAMY)
        parsed = parse_note(raw)
        assert "奶油风" in parsed.normalized_body or "出片" in parsed.normalized_body
        assert parsed.note_id == "test_creamy_001"

    def test_engagement_summary(self):
        raw = parse_raw_note(FIXTURE_NOTE_WATERPROOF)
        parsed = parse_note(raw)
        assert parsed.engagement_summary["total_engagement"] == 5600 + 4200 + 320 + 150
        assert parsed.engagement_summary["like_ratio"] > 0

    def test_normalized_tags(self):
        raw = parse_raw_note(FIXTURE_NOTE_WATERPROOF)
        parsed = parse_note(raw)
        assert "防水" in parsed.normalized_tags

from __future__ import annotations

from typing import Any

from apps.intel_hub.schemas import Signal, Watchlist


def tag_topics(signal: Signal, matched_watchlists: list[Watchlist], ontology_mapping: dict[str, Any]) -> list[str]:
    haystack = " ".join(
        [
            signal.title,
            signal.summary,
            signal.raw_text,
            signal.keyword or "",
            " ".join(signal.topic_tags),
        ]
    ).lower()

    tags = set(signal.topic_tags)
    for watchlist in matched_watchlists:
        tags.add(str(watchlist.watchlist_type))
        tags.update(watchlist.topic_tags)

    for topic_name, topic_config in ontology_mapping.get("topics", {}).items():
        keywords = topic_config.get("keywords", []) if isinstance(topic_config, dict) else []
        if any(str(keyword).lower() in haystack for keyword in keywords):
            tags.add(topic_name)

    tablecloth_rules = {
        "风格偏好": ("ins风", "奶油风", "北欧", "复古", "法式"),
        "材质偏好": ("pvc", "棉麻", "硅胶", "皮革"),
        "清洁痛点": ("防水", "防油", "免洗", "好打理"),
        "场景改造": ("改造", "茶几", "餐桌", "书桌"),
        "内容钩子": ("推荐", "测评", "踩坑", "平替", "开箱", "对比", "好物"),
        "拍照出片": ("出片", "拍照", "氛围感", "高级感", "上镜"),
        "价格敏感": ("便宜", "平价", "性价比", "多少钱", "贵"),
        "尺寸适配": ("尺寸", "大小", "定制", "圆桌", "长桌", "方桌"),
    }
    matched_watchlist_ids = {watchlist.id for watchlist in matched_watchlists}
    if (
        "category_tablecloth" in signal.entity_refs
        or "category_tablecloth" in signal.canonical_entity_refs
        or "category_tablecloth" in matched_watchlist_ids
    ):
        for tag_name, keywords in tablecloth_rules.items():
            if any(keyword.lower() in haystack for keyword in keywords):
                tags.add(tag_name)

    xhs_review_rules = {
        "用户真实体验": ("真实", "亲测", "用了", "买了", "到手", "实测", "体验"),
        "购买意向": ("想买", "求链接", "哪里买", "多少钱", "有链接吗", "怎么买", "求购"),
        "负面反馈": ("退货", "差评", "踩坑", "不好", "质量差", "色差", "不推荐", "翻车"),
        "推荐种草": ("推荐", "好用", "必买", "回购", "安利", "种草", "真香", "绝绝子"),
    }
    xhs_platforms = {"xhs", "xiaohongshu"}
    is_xhs = bool(xhs_platforms & set(signal.platform_refs or [])) or "小红书" in haystack or "xiaohongshu" in haystack
    if is_xhs:
        for tag_name, kws in xhs_review_rules.items():
            if any(kw.lower() in haystack for kw in kws):
                tags.add(tag_name)

    return sorted(tags)

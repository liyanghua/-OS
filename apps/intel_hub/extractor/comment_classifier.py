"""评论级信号分类器。

将单条评论文本分类为经营信号类型。
"""

from __future__ import annotations

import re

from apps.intel_hub.schemas.content_frame import CommentFrame
from apps.intel_hub.schemas.enums import CommentSignalType

PURCHASE_INTENT_RE = re.compile(
    r"(求链接|想买|哪里买|多少钱|有链接|怎么买|求购|已下单|已入|同款|被种草|链接)",
    re.IGNORECASE,
)
POSITIVE_RE = re.compile(
    r"(好看|好用|推荐|真香|绝绝子|爱了|强推|回购|好打理|出片|高级感)",
    re.IGNORECASE,
)
NEGATIVE_RE = re.compile(
    r"(卷边|翘边|廉价|塑料感|色差|翻车|退货|差评|不好|质量差|不推荐|难清洁|难打理|不值)",
    re.IGNORECASE,
)
QUESTION_RE = re.compile(
    r"(吗[?？]|怎么选|怎么样|好不好|值不值|会不会|能不能|可以.+吗|有.+吗)",
    re.IGNORECASE,
)
COMPARISON_RE = re.compile(
    r"(和.+比|跟.+比|比.+好|不如|哪个好|哪个更|选哪个|还是.+好)",
    re.IGNORECASE,
)
UNMET_NEED_RE = re.compile(
    r"(想要|有没有|出.+色|什么时候出|求.+版|希望有|能不能出|想出)",
    re.IGNORECASE,
)
TRUST_GAP_RE = re.compile(
    r"(实物一样|会不会翻车|真的吗|靠谱吗|真实吗|是不是托|到底怎么样)",
    re.IGNORECASE,
)


def classify_comment(comment: CommentFrame) -> list[CommentSignalType]:
    """对单条评论做信号类型分类，可返回多个类型。"""
    text = comment.comment_text
    if not text:
        return []

    types: list[CommentSignalType] = []

    if PURCHASE_INTENT_RE.search(text):
        types.append(CommentSignalType.PURCHASE_INTENT)
    if POSITIVE_RE.search(text):
        types.append(CommentSignalType.POSITIVE_FEEDBACK)
    if NEGATIVE_RE.search(text):
        types.append(CommentSignalType.NEGATIVE_FEEDBACK)
    if QUESTION_RE.search(text):
        types.append(CommentSignalType.QUESTION)
    if COMPARISON_RE.search(text):
        types.append(CommentSignalType.COMPARISON)
    if UNMET_NEED_RE.search(text):
        types.append(CommentSignalType.UNMET_NEED)
    if TRUST_GAP_RE.search(text):
        types.append(CommentSignalType.TRUST_GAP)

    return types


def classify_comments_batch(comments: list[CommentFrame]) -> dict[str, list[CommentSignalType]]:
    """批量分类，返回 {comment_id: [signal_types]}。"""
    return {
        c.comment_id or str(i): classify_comment(c)
        for i, c in enumerate(comments)
    }

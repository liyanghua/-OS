"""XHS 选择器版本化抽取模块。

每个页面类型（搜索结果、笔记详情、评论）独立版本管理，
支持 validate -> extract -> fallback 链。
"""

from .registry import ExtractorRegistry, get_extractor, get_registry
from .search_v1 import SearchExtractorV1
from .note_detail_v1 import NoteDetailExtractorV1
from .comment_v1 import CommentExtractorV1

_reg = get_registry()
_reg.register(SearchExtractorV1(), priority=10)
_reg.register(NoteDetailExtractorV1(), priority=10)
_reg.register(CommentExtractorV1(), priority=10)

__all__ = ["ExtractorRegistry", "get_extractor", "get_registry"]

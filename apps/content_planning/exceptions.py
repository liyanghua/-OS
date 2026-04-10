"""内容策划编排层异常（供 API 映射为不同 HTTP 状态码）。"""


class OpportunityNotPromotedError(Exception):
    """机会卡存在但未处于已升级（promoted）状态，不允许走内容策划编译链。"""

    def __init__(self, opportunity_id: str, current_status: str) -> None:
        self.opportunity_id = opportunity_id
        self.current_status = current_status
        super().__init__(
            f"机会卡 {opportunity_id} 当前状态为「{current_status}」，仅「promoted / 已升级」机会卡可生成 Brief 与策划方案"
        )


class StageApplyConflictError(Exception):
    """对象阶段 apply 发生版本冲突或被上游 stale 阻断。"""

    def __init__(self, message: str, *, stage: str, stale_flags: dict[str, bool] | None = None) -> None:
        self.message = message
        self.stage = stage
        self.stale_flags = stale_flags or {}
        super().__init__(message)

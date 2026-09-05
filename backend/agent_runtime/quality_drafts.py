"""Terminal quality failures for drafts that must not become reports."""

from __future__ import annotations


class AgentQualityDraftError(Exception):
    """A failed quality rewrite retained a draft, not publishable output."""

    def __init__(self, agent_num: int, detail: str):
        self.agent_num = agent_num
        self.detail = detail
        super().__init__(f"Agent {agent_num} 品質重寫失敗，原稿保留為未通過草稿，不產生正式報告。")

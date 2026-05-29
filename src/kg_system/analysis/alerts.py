"""告警管理（骨架占位）。"""
from __future__ import annotations

from kg_system.core.exceptions import NotImplementedInSkeleton
from kg_system.core.models import Alert


class AlertManager:
    """根据 ALERT_RULES 评估指标并触发告警。"""

    ALERT_RULES: dict[str, dict] = {
        "error_rate_high": {
            "condition": "error_rate > 0.05",
            "severity": "warning",
            "channels": ["log", "webhook"],
        },
        "response_time_slow": {
            "condition": "p99_duration > 10000",
            "severity": "warning",
            "channels": ["log", "webhook"],
        },
        "cost_over_budget": {
            "condition": "daily_cost > budget_limit",
            "severity": "critical",
            "channels": ["log", "webhook", "email"],
        },
        "service_down": {
            "condition": "success_rate < 0.5",
            "severity": "critical",
            "channels": ["log", "webhook", "email", "sms"],
        },
    }

    async def evaluate(self, metrics: dict) -> list[Alert]:
        raise NotImplementedInSkeleton("alerts.evaluate")

    async def notify(self, alert: Alert) -> None:
        raise NotImplementedInSkeleton("alerts.notify")

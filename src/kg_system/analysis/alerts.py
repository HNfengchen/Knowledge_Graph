"""告警管理：评估指标规则、多渠道通知、后台调度器。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger
from kg_system.core.models import Alert

log = get_logger(__name__)


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

    def __init__(self) -> None:
        self._settings = get_settings()

    async def evaluate(self, metrics: dict[str, Any]) -> list[Alert]:
        alerts: list[Alert] = []
        s = self._settings

        for rule_name, rule in self.ALERT_RULES.items():
            condition = rule["condition"]
            triggered = False
            error_rate = metrics.get("error_rate", 0.0)
            p99_duration = metrics.get("p99_duration", 0)
            daily_cost = metrics.get("daily_cost", 0.0)
            success_rate = metrics.get("success_rate", 1.0)
            budget_limit = s.DAILY_BUDGET_USD * s.BUDGET_ALERT_THRESHOLD

            try:
                triggered = eval(
                    condition,
                    {
                        "error_rate": error_rate,
                        "p99_duration": p99_duration,
                        "daily_cost": daily_cost,
                        "success_rate": success_rate,
                        "budget_limit": budget_limit,
                    },
                )
            except Exception as e:
                log.warning("alert_eval_failed", rule=rule_name, error=str(e))
                continue

            if triggered:
                alerts.append(
                    Alert(
                        rule=rule_name,
                        severity=rule["severity"],
                        message=f"Rule '{rule_name}' triggered: {condition}",
                        metrics=metrics,
                    )
                )

        return alerts

    async def notify(self, alert: Alert) -> None:
        s = self._settings
        rule = self.ALERT_RULES.get(alert.rule, {})

        for channel in rule.get("channels", ["log"]):
            try:
                if channel == "log":
                    log.warning("alert_triggered", rule=alert.rule, severity=alert.severity, msg=alert.message)
                elif channel == "webhook":
                    if s.ALERT_WEBHOOK_URL:
                        async with httpx.AsyncClient(timeout=s.ALERT_WEBHOOK_TIMEOUT) as client:
                            await client.post(s.ALERT_WEBHOOK_URL, json=alert.model_dump())
                elif channel in ("email", "sms"):
                    log.info("alert_channel_stub", channel=channel, rule=alert.rule)
            except Exception as e:
                log.error("alert_notify_failed", channel=channel, error=str(e))


class AlertScheduler:
    """后台周期调度器：每 ALERT_EVAL_INTERVAL 秒评估一次告警。"""

    def __init__(self, alert_manager: AlertManager, metrics_aggregator) -> None:
        self._manager = alert_manager
        self._metrics = metrics_aggregator
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="alert-scheduler")
        log.info("alert_scheduler_started")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        log.info("alert_scheduler_stopped")

    async def _run(self) -> None:
        s = get_settings()
        while not self._stop.is_set():
            try:
                qps = await self._metrics.get_qps(60)
                latencies = await self._metrics.get_latency_percentiles(300)
                error_rate = await self._metrics.get_error_rate(60)
                daily_cost = await self._metrics.get_daily_cost_usd()

                metrics = {
                    "qps": qps,
                    "p99_duration": latencies.get("p99", 0),
                    "error_rate": error_rate,
                    "success_rate": 1.0 - error_rate,
                    "daily_cost": daily_cost,
                }
                alerts = await self._manager.evaluate(metrics)
                for alert in alerts:
                    await self._manager.notify(alert)
            except Exception as e:
                log.warning("alert_cycle_failed", error=str(e))

            await asyncio.wait_for(
                asyncio.get_event_loop().create_future() if False else asyncio.sleep(s.ALERT_CHECK_INTERVAL),
                timeout=s.ALERT_CHECK_INTERVAL,
            )

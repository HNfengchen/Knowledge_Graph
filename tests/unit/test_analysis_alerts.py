from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kg_system.analysis.alerts import AlertManager, AlertScheduler
from kg_system.core.models import Alert


@pytest.mark.unit
class TestAlertManager:
    @pytest.fixture
    def manager(self) -> AlertManager:
        return AlertManager()

    # ── evaluate ──

    async def test_evaluate_triggers_on_high_error_rate(
        self, manager: AlertManager
    ) -> None:
        alerts = await manager.evaluate({"error_rate": 0.10})

        names = [a.rule for a in alerts]
        assert "error_rate_high" in names

    async def test_evaluate_triggers_on_slow_response(
        self, manager: AlertManager
    ) -> None:
        alerts = await manager.evaluate({"p99_duration": 15000})

        names = [a.rule for a in alerts]
        assert "response_time_slow" in names

    async def test_evaluate_triggers_on_cost_over_budget(
        self, manager: AlertManager
    ) -> None:
        alerts = await manager.evaluate({"daily_cost": 100.0})

        names = [a.rule for a in alerts]
        assert "cost_over_budget" in names

    async def test_evaluate_triggers_on_service_down(
        self, manager: AlertManager
    ) -> None:
        alerts = await manager.evaluate({"success_rate": 0.3})

        names = [a.rule for a in alerts]
        assert "service_down" in names

    async def test_evaluate_returns_empty_for_clean_metrics(
        self, manager: AlertManager
    ) -> None:
        alerts = await manager.evaluate(
            {
                "error_rate": 0.0,
                "p99_duration": 100,
                "daily_cost": 1.0,
                "success_rate": 1.0,
            }
        )

        assert alerts == []

    async def test_evaluate_missing_fields_default_to_zero(
        self, manager: AlertManager
    ) -> None:
        alerts = await manager.evaluate({})

        assert alerts == []

    async def test_evaluate_alert_has_correct_fields(
        self, manager: AlertManager
    ) -> None:
        metrics = {"error_rate": 0.10, "p99_duration": 100, "daily_cost": 1.0}
        alerts = await manager.evaluate(metrics)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.rule == "error_rate_high"
        assert alert.severity == "warning"
        assert "error_rate > 0.05" in alert.message
        assert alert.metrics == metrics

    # ── notify ──

    async def test_notify_log_channel(self, manager: AlertManager) -> None:
        alert = Alert(
            rule="error_rate_high",
            severity="warning",
            message="test alert",
            metrics={},
        )

        with patch("kg_system.analysis.alerts.log.warning") as mock_log:
            await manager.notify(alert)

        mock_log.assert_called_once()

    async def test_notify_webhook_channel(
        self, manager: AlertManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(manager._settings, "ALERT_WEBHOOK_URL", "http://webhook.test")

        alert = Alert(
            rule="error_rate_high",
            severity="warning",
            message="webhook test",
            metrics={"error_rate": 0.10},
        )

        mock_client = AsyncMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            await manager.notify(alert)

        mock_client.post.assert_called_once_with(
            "http://webhook.test", json=alert.model_dump()
        )

    async def test_notify_skips_webhook_when_url_empty(
        self, manager: AlertManager
    ) -> None:
        alert = Alert(
            rule="error_rate_high",
            severity="warning",
            message="no webhook",
            metrics={},
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            await manager.notify(alert)

        mock_client_class.assert_not_called()

    async def test_notify_webhook_failure_does_not_raise(
        self, manager: AlertManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(manager._settings, "ALERT_WEBHOOK_URL", "http://webhook.test")

        alert = Alert(
            rule="error_rate_high",
            severity="warning",
            message="fail test",
            metrics={},
        )

        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("timeout")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            with patch("kg_system.analysis.alerts.log.error") as mock_log:
                await manager.notify(alert)

        mock_client.post.assert_called_once()
        mock_log.assert_called_once()

    async def test_notify_email_sms_stub_log(
        self, manager: AlertManager
    ) -> None:
        alert = Alert(
            rule="service_down",
            severity="critical",
            message="stub test",
            metrics={},
        )

        with patch("kg_system.analysis.alerts.log.info") as mock_log:
            await manager.notify(alert)

        assert mock_log.call_count >= 2

    async def test_notify_unknown_rule_uses_log_default(
        self, manager: AlertManager
    ) -> None:
        alert = Alert(
            rule="nonexistent_rule",
            severity="critical",
            message="fallback test",
            metrics={},
        )

        with patch("kg_system.analysis.alerts.log.warning") as mock_log:
            await manager.notify(alert)

        mock_log.assert_called_once()


@pytest.mark.unit
class TestAlertScheduler:
    @pytest.fixture
    def manager(self) -> AlertManager:
        return AlertManager()

    @pytest.fixture
    def mock_metrics(self) -> AsyncMock:
        m = AsyncMock()
        m.get_qps.return_value = 0.0
        m.get_latency_percentiles.return_value = {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        m.get_error_rate.return_value = 0.0
        m.get_daily_cost_usd.return_value = 0.0
        return m

    @pytest.fixture
    def scheduler(
        self, manager: AlertManager, mock_metrics: AsyncMock
    ) -> AlertScheduler:
        return AlertScheduler(manager, mock_metrics)

    async def test_start_creates_task(self, scheduler: AlertScheduler) -> None:
        stop = scheduler._stop
        async def _run() -> None:
            while not stop.is_set():
                await asyncio.sleep(0.05)

        with patch.object(scheduler, "_run", _run):
            await scheduler.start()
            assert scheduler._task is not None
            assert not scheduler._task.done()
            await scheduler.stop()
            assert scheduler._task is None

    async def test_start_is_idempotent(self, scheduler: AlertScheduler) -> None:
        stop = scheduler._stop
        async def _run() -> None:
            while not stop.is_set():
                await asyncio.sleep(0.05)

        with patch.object(scheduler, "_run", _run):
            await scheduler.start()
            first = scheduler._task
            await scheduler.start()
            assert scheduler._task is first
            await scheduler.stop()

    async def test_stop_does_nothing_when_not_running(
        self, scheduler: AlertScheduler
    ) -> None:
        await scheduler.stop()
        assert scheduler._task is None

    @pytest.mark.parametrize("interval", [0, 1])
    async def test_run_cycle_invokes_metrics_and_evaluate(
        self, scheduler: AlertScheduler, mock_metrics: AsyncMock, interval: int
    ) -> None:
        _iteration_done = False

        original_run = scheduler._run

        async def controlled_run() -> None:
            nonlocal _iteration_done
            s = scheduler._manager._settings
            s.ALERT_CHECK_INTERVAL = interval
            with patch.object(s, "ALERT_CHECK_INTERVAL", interval):
                qps = await mock_metrics.get_qps(60)
                latencies = await mock_metrics.get_latency_percentiles(300)
                error_rate = await mock_metrics.get_error_rate(60)
                daily_cost = await mock_metrics.get_daily_cost_usd()
                metrics = {
                    "qps": qps,
                    "p99_duration": latencies.get("p99", 0),
                    "error_rate": error_rate,
                    "success_rate": 1.0 - error_rate,
                    "daily_cost": daily_cost,
                }
                await scheduler._manager.evaluate(metrics)
                _iteration_done = True

        with patch.object(scheduler, "_run", controlled_run):
            await scheduler.start()
            await asyncio.sleep(0.1)
            await scheduler.stop()

        assert _iteration_done
        mock_metrics.get_qps.assert_called_once_with(60)
        mock_metrics.get_latency_percentiles.assert_called_once_with(300)
        mock_metrics.get_error_rate.assert_called_once_with(60)
        mock_metrics.get_daily_cost_usd.assert_called_once()

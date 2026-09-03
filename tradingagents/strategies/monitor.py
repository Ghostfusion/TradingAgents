"""Monitoring / alert notification path (W4-7, advisory).

Production nightlies should PUSH on breaker trips, stale-data thresholds,
and invalidation breaches — not just append to a JSONL that has to be read.
This is a small, default-off notifier: a webhook POST (Slack/Teams/Discord
generic), a console line, or nothing. Deterministic and safe: a failed
notify never raises (advisory).

Wire points (existing code) can call ``notify(event, detail, config)`` at
their logged events; unconfigured -> no-op.
"""

from __future__ import annotations

import json
import logging
import urllib.request

logger = logging.getLogger(__name__)


def notify(event: str, detail: str = "", config: dict | None = None) -> None:
    """Emit one alert event. No-op unless a notifier is configured.

    ``config`` may carry ``monitor_webhook`` (a URL) and ``monitor_channel``
    (default ``other``). When only ``monitor_notify=True`` with no webhook,
    the event goes to the log (visible in the nightly log, still a push-like
    record). Never raises.
    """
    cfg = config or {}
    webhook = cfg.get("monitor_webhook")
    enabled = bool(cfg.get("monitor_notify", False)) or bool(webhook)
    if not enabled:
        return
    payload = {"event": event, "detail": detail,
               "channel": cfg.get("monitor_channel", "other")}
    if webhook:
        try:
            req = urllib.request.Request(
                webhook,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5).read()  # noqa: S310 advisory
        except Exception as exc:  # noqa: BLE001 - never block the caller
            logger.warning("monitor notify failed for %s: %s", event, exc)
    else:
        logger.warning("MONITOR %s: %s", event, detail)


__all__ = ["notify"]

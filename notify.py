"""Outbound notifications: a JSON webhook (works with Home Assistant, ntfy,
Discord/Slack via relays, n8n, etc.)."""
import logging
import threading

import requests

log = logging.getLogger("spynet.notify")


def send_webhook(url, payload):
    if not url:
        return

    def _post():
        try:
            resp = requests.post(url, json=payload, timeout=8)
            if resp.status_code >= 400:
                log.warning("webhook %s returned %s", url, resp.status_code)
        except requests.RequestException as exc:
            log.warning("webhook failed: %s", exc)

    threading.Thread(target=_post, daemon=True, name="webhook").start()

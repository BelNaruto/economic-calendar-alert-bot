"""Delivery channels: Telegram Bot API, Discord webhooks, or stdout (dry run)."""
from __future__ import annotations

import html
import json
import re

import requests


class Notifier:
    def send(self, telegram_html: str, discord_payload: dict) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class TelegramNotifier(Notifier):
    def __init__(self, bot_token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id

    def send(self, telegram_html: str, discord_payload: dict) -> None:
        r = requests.post(self.url, json={"chat_id": self.chat_id, "text": telegram_html, "parse_mode": "HTML",
                                          "disable_web_page_preview": True}, timeout=20)
        r.raise_for_status()


class DiscordNotifier(Notifier):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send(self, telegram_html: str, discord_payload: dict) -> None:
        r = requests.post(self.webhook_url, json=discord_payload, timeout=20)
        r.raise_for_status()


class ConsoleNotifier(Notifier):
    def __init__(self, json_mode: bool = False):
        self.json_mode = json_mode
        self.sent: list[tuple[str, dict]] = []

    def send(self, telegram_html: str, discord_payload: dict) -> None:
        self.sent.append((telegram_html, discord_payload))
        if self.json_mode:
            print(json.dumps(discord_payload, ensure_ascii=False))
        else:
            print(html.unescape(re.sub(r"<[^>]+>", "", telegram_html)))
            print("-" * 60)


class MultiNotifier(Notifier):
    def __init__(self, notifiers: list[Notifier]):
        self.notifiers = notifiers

    def send(self, telegram_html: str, discord_payload: dict) -> None:
        errors = []
        for n in self.notifiers:
            try:
                n.send(telegram_html, discord_payload)
            except Exception as exc:  # keep other channels working
                errors.append(f"{type(n).__name__}: {exc}")
        if errors and len(errors) == len(self.notifiers):
            raise RuntimeError("; ".join(errors))

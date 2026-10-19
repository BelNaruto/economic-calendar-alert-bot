"""Message formatting for Telegram (HTML) and Discord (embeds)."""
from __future__ import annotations

import html as _html
from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from .client import ACTOR_URL, Event, flag


def _esc(text: str) -> str:
    return _html.escape(text, quote=False)

SURPRISE_EMOJI = {"beat": "🟢 Beat", "miss": "🔴 Miss", "inline": "⚪ In line"}
IMPACT_EMOJI = {"high": "🔴", "medium": "🟠", "low": "🟡", None: "🏖"}
IMPACT_COLOR = {"high": 0xE53935, "medium": 0xFB8C00, "low": 0xFDD835, None: 0x43A047}


def local_time(e: Event, tz: ZoneInfo) -> str:
    return e.when.astimezone(tz).strftime("%H:%M") if e.when else "All day"


def agenda_telegram(events: list[Event], day: date, tz: ZoneInfo, title: str = "Economic calendar") -> str:
    lines = [f"📅 <b>{_esc(title)} — {day.strftime('%A %d %b %Y')}</b>", f"<i>Times in {tz.key}</i>", ""]
    if not events:
        lines.append("No events matching your filters today. 😴")
    by_time: dict[str, list[Event]] = defaultdict(list)
    for e in events:
        by_time[local_time(e, tz)].append(e)
    for t, evs in by_time.items():
        for e in evs:
            detail = []
            if e.forecast:
                detail.append(f"f {_esc(e.forecast)}")
            if e.previous:
                detail.append(f"p {_esc(e.previous)}")
            if e.actual:
                detail.insert(0, f"<b>A {_esc(e.actual)}</b>")
            suffix = f"  <code>{' · '.join(detail)}</code>" if detail else ""
            lines.append(f"{IMPACT_EMOJI.get(e.importance, '•')} <b>{t}</b> {flag(e.country)} {_esc(e.title)}{suffix}")
    lines += ["", f'<a href="{ACTOR_URL}">Data: Investing.com via Apify</a>']
    return "\n".join(lines)


def reminder_telegram(e: Event, minutes: int, tz: ZoneInfo) -> str:
    return (
        f"⏰ <b>In {minutes} min</b> — {flag(e.country)} <b>{_esc(e.title)}</b>\n"
        f"🕒 {local_time(e, tz)} ({tz.key}) · {IMPACT_EMOJI.get(e.importance, '')} {(e.importance or '').upper()}\n"
        f"Forecast: <code>{_esc(e.forecast or '-')}</code> · Previous: <code>{_esc(e.previous or '-')}</code>"
    )


def result_telegram(e: Event, tz: ZoneInfo) -> str:
    s = e.surprise()
    verdict = SURPRISE_EMOJI.get(s, "")
    return (
        f"📊 <b>{flag(e.country)} {_esc(e.title)}</b> {verdict}\n"
        f"Actual: <b>{_esc(e.actual or '-')}</b> · Forecast: {_esc(e.forecast or '-')} · "
        f"Previous: {_esc(e.previous or '-')}\n"
        f"🕒 {local_time(e, tz)} {tz.key} · {e.currency or ''}"
    )


def _embed_event_line(e: Event, tz: ZoneInfo) -> str:
    vals = " · ".join(x for x in [f"**A {e.actual}**" if e.actual else "", f"f {e.forecast}" if e.forecast else "",
                                    f"p {e.previous}" if e.previous else ""] if x)
    return f"{IMPACT_EMOJI.get(e.importance, '•')} `{local_time(e, tz)}` {flag(e.country)} {e.title}" + (f" — {vals}" if vals else "")


def agenda_discord(events: list[Event], day: date, tz: ZoneInfo, title: str = "Economic calendar") -> dict:
    body = "\n".join(_embed_event_line(e, tz) for e in events) or "No events matching your filters today."
    return {"embeds": [{
        "title": f"📅 {title} — {day.strftime('%A %d %b %Y')}",
        "description": body[:4000],
        "color": 0x4F8CFF,
        "footer": {"text": f"Times in {tz.key} · Data: Investing.com via Apify"},
        "url": ACTOR_URL,
    }]}


def reminder_discord(e: Event, minutes: int, tz: ZoneInfo) -> dict:
    return {"embeds": [{
        "title": f"⏰ In {minutes} min — {flag(e.country)} {e.title}",
        "color": IMPACT_COLOR.get(e.importance, 0x999999),
        "fields": [
            {"name": "Time", "value": f"{local_time(e, tz)} {tz.key}", "inline": True},
            {"name": "Forecast", "value": e.forecast or "-", "inline": True},
            {"name": "Previous", "value": e.previous or "-", "inline": True},
        ],
    }]}


def result_discord(e: Event, tz: ZoneInfo) -> dict:
    return {"embeds": [{
        "title": f"📊 {flag(e.country)} {e.title} {SURPRISE_EMOJI.get(e.surprise(), '')}",
        "color": {"beat": 0x43A047, "miss": 0xE53935}.get(e.surprise() or "", 0x9E9E9E),
        "fields": [
            {"name": "Actual", "value": e.actual or "-", "inline": True},
            {"name": "Forecast", "value": e.forecast or "-", "inline": True},
            {"name": "Previous", "value": e.previous or "-", "inline": True},
        ],
        "footer": {"text": f"{local_time(e, tz)} {tz.key} · {e.currency or ''}"},
    }]}

"""Alert logic, independent from I/O so it is easy to test."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import messages as m
from .client import Event
from .notify import Notifier


def event_key(e: Event) -> str:
    return f"{e.id}|{e.day.isoformat()}|{e.title}"


@dataclass
class State:
    path: Path | None = None
    reminded: set[str] = field(default_factory=set)
    results: set[str] = field(default_factory=set)
    agendas: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: str | Path | None) -> "State":
        if not path or not Path(path).exists():
            return cls(Path(path) if path else None)
        data = json.loads(Path(path).read_text())
        return cls(Path(path), set(data.get("reminded", [])), set(data.get("results", [])), set(data.get("agendas", [])))

    def save(self) -> None:
        if self.path:
            # keep the file small: only the most recent keys
            data = {k: sorted(getattr(self, k))[-2000:] for k in ("reminded", "results", "agendas")}
            self.path.write_text(json.dumps(data, indent=1))


class AlertEngine:
    def __init__(self, notifier: Notifier, tz: ZoneInfo, remind_minutes: int = 15, state: State | None = None,
                 result_window: timedelta = timedelta(hours=3)):
        self.notifier = notifier
        self.tz = tz
        self.remind = timedelta(minutes=remind_minutes)
        self.remind_minutes = remind_minutes
        self.state = state or State()
        self.result_window = result_window

    def process(self, events: list[Event], now: datetime) -> dict:
        sent = {"reminders": 0, "results": 0}
        for e in events:
            if not e.when:
                continue
            k = event_key(e)
            until = e.when - now
            if timedelta(0) < until <= self.remind and k not in self.state.reminded:
                mins = max(1, round(until.total_seconds() / 60))
                self.notifier.send(m.reminder_telegram(e, mins, self.tz), m.reminder_discord(e, mins, self.tz))
                self.state.reminded.add(k)
                sent["reminders"] += 1
            if e.actual and timedelta(0) <= now - e.when <= self.result_window and k not in self.state.results:
                self.notifier.send(m.result_telegram(e, self.tz), m.result_discord(e, self.tz))
                self.state.results.add(k)
                sent["results"] += 1
        self.state.save()
        return sent

    def agenda(self, events: list[Event], now: datetime, title: str, force: bool = False) -> bool:
        day = now.astimezone(self.tz).date()
        key = day.isoformat()
        if key in self.state.agendas and not force:
            return False
        todays = [e for e in events if (e.when.astimezone(self.tz).date() if e.when else e.day) == day]
        self.notifier.send(m.agenda_telegram(todays, day, self.tz, title), m.agenda_discord(todays, day, self.tz, title))
        self.state.agendas.add(key)
        self.state.save()
        return True

    def needs_fast_refresh(self, events: list[Event], now: datetime) -> bool:
        """True while an event was released in the last 30 min without an 'actual' value yet."""
        return any(e.when and timedelta(0) <= now - e.when <= timedelta(minutes=30) and not e.actual for e in events)

"""Economic calendar alert bot for Telegram & Discord.

Commands
  agenda   post today's agenda once and exit (great for a daily cron / GitHub Actions)
  run      long-running bot: daily agenda + reminders before each release + actual vs forecast results
  preview  print the messages for a given moment using sample data (no tokens needed)

Configuration (environment variables or .env-style exports):
  APIFY_TOKEN            Apify API token (https://console.apify.com/settings/integrations)
  TELEGRAM_BOT_TOKEN     token from @BotFather            (optional)
  TELEGRAM_CHAT_ID       channel/group/user id, e.g. -1001234567890 or @mychannel
  DISCORD_WEBHOOK_URL    Discord channel webhook URL       (optional)
  COUNTRIES              comma list, default "united states,euro zone,united kingdom,japan"
  IMPORTANCE             high | medium | low | all   (default high)
  REMIND_MINUTES         minutes before a release to alert (default 15)
  DISPLAY_TZ             IANA time zone for messages (default UTC), e.g. Europe/Lisbon, America/New_York
  AGENDA_TIME            local time to post the daily agenda in `run` mode (default 07:00)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .client import ActorError, load_events
from .engine import AlertEngine, State
from .notify import ConsoleNotifier, DiscordNotifier, MultiNotifier, TelegramNotifier

DEFAULT_COUNTRIES = "united states,euro zone,united kingdom,japan"


def build_notifier(dry_run: bool):
    if dry_run:
        return ConsoleNotifier()
    chans = []
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        chans.append(TelegramNotifier(os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]))
    if os.getenv("DISCORD_WEBHOOK_URL"):
        chans.append(DiscordNotifier(os.environ["DISCORD_WEBHOOK_URL"]))
    if not chans:
        print("No TELEGRAM_* or DISCORD_WEBHOOK_URL configured -> printing messages instead (dry run).", file=sys.stderr)
        return ConsoleNotifier()
    return MultiNotifier(chans)


def fetch(args, now: datetime):
    imp = (args.importance or "high").lower()
    filters = {"countries": [c.strip() for c in args.countries.split(",") if c.strip()] or None}
    if imp != "all":
        filters["importance"] = imp
    return load_events(sample_file=args.sample, from_date=(now - timedelta(days=1)).date(),
                       to_date=(now + timedelta(days=1)).date(), **filters)


def parse_now(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="alertbot", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["agenda", "run", "preview"])
    p.add_argument("--countries", default=os.getenv("COUNTRIES", DEFAULT_COUNTRIES))
    p.add_argument("--importance", default=os.getenv("IMPORTANCE", "high"))
    p.add_argument("--remind", type=int, default=int(os.getenv("REMIND_MINUTES", "15")))
    p.add_argument("--tz", default=os.getenv("DISPLAY_TZ", "UTC"))
    p.add_argument("--agenda-time", default=os.getenv("AGENDA_TIME", "07:00"))
    p.add_argument("--title", default=os.getenv("AGENDA_TITLE", "Economic calendar"))
    p.add_argument("--state", default=os.getenv("STATE_FILE", "alertbot-state.json"))
    p.add_argument("--sample", help="JSON export to use instead of the live Actor (demo / tests)")
    p.add_argument("--now", help="pretend current time (ISO, UTC), for preview/testing")
    p.add_argument("--dry-run", action="store_true", help="print messages instead of sending them")
    args = p.parse_args(argv)

    tz = ZoneInfo(args.tz)
    if args.command == "preview":
        args.dry_run = True
        args.state = None
    notifier = build_notifier(args.dry_run)
    engine = AlertEngine(notifier, tz, args.remind, State.load(args.state))

    if args.command in ("agenda", "preview"):
        now = parse_now(args.now)
        events = fetch(args, now)
        engine.agenda(events, now, args.title, force=True)
        if args.command == "preview":
            engine.process(events, now)
        return 0

    # long-running mode
    events, last_fetch = [], datetime.min.replace(tzinfo=timezone.utc)
    print(f"alertbot running · countries={args.countries} · importance={args.importance} · tz={tz.key}")
    while True:
        now = datetime.now(timezone.utc)
        fast = engine.needs_fast_refresh(events, now)
        if now - last_fetch >= (timedelta(minutes=2) if fast else timedelta(minutes=60)):
            try:
                events = fetch(args, now)
                last_fetch = now
            except (ActorError, OSError) as exc:
                print(f"[warn] fetch failed: {exc}", file=sys.stderr)
        local = now.astimezone(tz)
        if local.strftime("%H:%M") >= args.agenda_time:
            engine.agenda(events, now, args.title)
        engine.process(events, now)
        time.sleep(30)


if __name__ == "__main__":
    raise SystemExit(main())

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from alertbot.__main__ import main
from alertbot.client import load_events
from alertbot.engine import AlertEngine, State
from alertbot.notify import ConsoleNotifier

SAMPLE = Path(__file__).with_name("sample-events.json")
UTC = timezone.utc


def _engine(tmp_path=None):
    n = ConsoleNotifier()
    return n, AlertEngine(n, ZoneInfo("UTC"), 15, State.load(tmp_path / "s.json" if tmp_path else None))


def test_reminder_sent_once(tmp_path):
    events = load_events(sample_file=SAMPLE, countries=["united states"], importance="high")
    n, eng = _engine(tmp_path)
    now = datetime(2026, 10, 14, 12, 20, tzinfo=UTC)
    r1 = eng.process(events, now)
    r2 = eng.process(events, now)
    assert r1["reminders"] == 3  # Core CPI MoM, CPI MoM, CPI YoY at 12:30
    assert r2["reminders"] == 0
    assert any("CPI (YoY) (Sep)" in t for t, _ in n.sent)


def test_result_posted_after_release(tmp_path):
    events = load_events(sample_file=SAMPLE, countries=["united states"], importance="high")
    n, eng = _engine(tmp_path)
    eng.process(events, datetime(2026, 10, 14, 12, 35, tzinfo=UTC))
    results = [t for t, _ in n.sent if t.startswith("📊")]
    assert any("CPI (YoY) (Sep)" in t and "Beat" in t for t in results)


def test_state_persists(tmp_path):
    events = load_events(sample_file=SAMPLE, countries=["united states"], importance="high")
    _, eng = _engine(tmp_path)
    eng.process(events, datetime(2026, 10, 14, 12, 20, tzinfo=UTC))
    _, eng2 = _engine(tmp_path)
    assert eng2.process(events, datetime(2026, 10, 14, 12, 21, tzinfo=UTC))["reminders"] == 0


def test_cli_preview(capsys):
    assert main(["preview", "--sample", str(SAMPLE), "--now", "2026-10-28T17:50:00Z",
                 "--countries", "united states"]) == 0
    out = capsys.readouterr().out
    assert "Fed Interest Rate Decision" in out

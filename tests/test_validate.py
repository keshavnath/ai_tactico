"""Tests for StatsBomb data validation."""
import json
from pathlib import Path
from collections import defaultdict
import pytest


def validate_data(json_path: str):
    """Analyze StatsBomb JSON structure and return stats."""
    with open(json_path) as f:
        events = json.load(f)

    # Event types
    event_types = defaultdict(int)
    teams = set()
    players = set()
    possessions = set()
    periods = set()

    for event in events:
        event_types[event["type"]["name"]] += 1
        if "team" in event:
            teams.add(event["team"]["name"])
        if "player" in event:
            players.add(event["player"]["name"])
        possessions.add(event["possession"])
        periods.add(event["period"])

    return {
        "total_events": len(events),
        "event_types": dict(event_types),
        "teams": sorted(teams),
        "player_count": len(players),
        "possession_count": len(possessions),
        "periods": sorted(periods),
    }


def test_data_structure():
    """Test that data file exists and has expected structure."""
    data_file = Path("data/18245.json")
    assert data_file.exists(), "Data file not found"

    stats = validate_data(str(data_file))

    # Basic assertions about data
    assert stats["total_events"] > 0, "No events found"
    assert len(stats["teams"]) == 2, "Expected 2 teams"
    assert stats["player_count"] > 0, "No players found"
    assert stats["possession_count"] > 0, "No possessions found"
    assert len(stats["periods"]) > 0, "No periods found"


def test_event_types_present():
    """Test that expected event types are in the data."""
    data_file = Path("data/18245.json")
    stats = validate_data(str(data_file))

    expected_types = {"Pass", "Ball Receipt*", "Carry", "Shot"}
    actual_types = set(stats["event_types"].keys())

    for expected in expected_types:
        assert expected in actual_types or any(
            expected.lower() in t.lower() for t in actual_types
        ), f"Expected event type '{expected}' not found"


def test_print_validation_report(capsys):
    """Test data validation report generation."""
    data_file = Path("data/18245.json")
    
    if not data_file.exists():
        pytest.skip("Data file not found")
    
    stats = validate_data(str(data_file))

    # Print report (can be captured in tests)
    print("\nData Validation Report")
    print(f"{'='*50}")
    print(f"Total events: {stats['total_events']}")
    print(f"\nTeams ({len(stats['teams'])}):")
    for team in stats["teams"]:
        print(f"  {team}")
    print(f"\nPlayers: {stats['player_count']}")
    print(f"Possessions: {stats['possession_count']}")
    print(f"Periods: {stats['periods']}")
    print(f"\nEvent Types (top 10):")
    for event_type, count in sorted(
        stats["event_types"].items(), key=lambda x: x[1], reverse=True
    )[:10]:
        print(f"  {event_type:30s} {count:5d}")

    captured = capsys.readouterr()
    assert "Data Validation Report" in captured.out
    assert "Events loaded" in captured.out or "Total events" in captured.out

"""Tests for StatsBomb data ingestion."""
import json
from pathlib import Path
import pytest
from src.db import StatsBombIngestion


@pytest.fixture
def sample_event_data():
    """Create minimal sample StatsBomb events for testing."""
    return [
        {
            "id": "d39f8e36-1acf-4c45-a97f-c79c618e6e93",
            "index": 1,
            "period": 1,
            "timestamp": "00:00:00.000",
            "minute": 0,
            "second": 0,
            "type": {"id": 35, "name": "Starting XI"},
            "possession": 1,
            "possession_team": {"id": 1, "name": "Team A"},
            "team": {"id": 1, "name": "Team A"},
            "player": None,
            "tactics": {
                "formation": 442,
                "lineup": [
                    {
                        "player": {"id": 101, "name": "Player 1"},
                        "position": {"id": 1, "name": "Goalkeeper"},
                        "jersey_number": 1,
                    },
                    {
                        "player": {"id": 102, "name": "Player 2"},
                        "position": {"id": 2, "name": "Defender"},
                        "jersey_number": 2,
                    },
                ],
            },
        },
        {
            "id": "starting-xi-team-b",
            "index": 2,
            "period": 1,
            "timestamp": "00:00:00.000",
            "minute": 0,
            "second": 0,
            "type": {"id": 35, "name": "Starting XI"},
            "possession": 1,
            "possession_team": {"id": 2, "name": "Team B"},
            "team": {"id": 2, "name": "Team B"},
            "tactics": {
                "formation": 433,
                "lineup": [
                    {
                        "player": {"id": 201, "name": "Player B1"},
                        "position": {"id": 1, "name": "Goalkeeper"},
                        "jersey_number": 1,
                    },
                    {
                        "player": {"id": 202, "name": "Player B2"},
                        "position": {"id": 2, "name": "Defender"},
                        "jersey_number": 2,
                    },
                ],
            },
        },
        {
            "id": "pass-event-1",
            "index": 3,
            "period": 1,
            "timestamp": "00:00:05.123",
            "minute": 0,
            "second": 5,
            "type": {"id": 16, "name": "Pass"},
            "possession": 2,
            "possession_team": {"id": 1, "name": "Team A"},
            "team": {"id": 1, "name": "Team A"},
            "player": {"id": 101, "name": "Player 1"},
            "pass": {
                "recipient": {"id": 102, "name": "Player 2"},
                "length": 15.5,
                "angle": 0.45,
            },
        },
        {
            "id": "pass-event-2",
            "index": 4,
            "period": 1,
            "timestamp": "00:00:10.456",
            "minute": 0,
            "second": 10,
            "type": {"id": 16, "name": "Pass"},
            "possession": 2,
            "possession_team": {"id": 1, "name": "Team A"},
            "team": {"id": 1, "name": "Team A"},
            "player": {"id": 102, "name": "Player 2"},
            "pass": {
                "recipient": {"id": 101, "name": "Player 1"},
                "length": 12.0,
                "angle": -0.5,
            },
        },
    ]


def test_ingestion_creates_match_node(schema_client, sample_event_data):
    """Test that ingestion creates a Match node."""
    match_id = schema_client._test_match_id
    ingestion = StatsBombIngestion(schema_client)
    
    # Manually call the load functions (normally called by ingest())
    match_info = ingestion._extract_match_info(sample_event_data)
    schema_client.execute(
        "CREATE (m:Match {id: $id, loaded_at: datetime()})",
        {"id": match_id}
    )
    
    result = schema_client.query(f"MATCH (m:Match {{id: '{match_id}'}}) RETURN m")
    assert len(result) == 1


def test_ingestion_extracts_teams(schema_client, sample_event_data):
    """Test that ingestion extracts team information."""
    ingestion = StatsBombIngestion(schema_client)
    teams = ingestion._extract_teams(sample_event_data)
    
    assert len(teams) == 2
    assert 1 in teams
    assert 2 in teams
    assert teams[1]["name"] == "Team A"
    assert teams[2]["name"] == "Team B"
    assert teams[1]["formation"] == 442
    assert teams[2]["formation"] == 433


def test_ingestion_extracts_players(schema_client, sample_event_data):
    """Test that ingestion extracts player information."""
    ingestion = StatsBombIngestion(schema_client)
    players = ingestion._extract_players(sample_event_data)
    
    assert 101 in players
    assert 102 in players
    assert players[101]["name"] == "Player 1"
    assert players[102]["name"] == "Player 2"


def test_ingestion_extracts_possessions(schema_client, sample_event_data):
    """Test that ingestion groups events by possession."""
    ingestion = StatsBombIngestion(schema_client)
    possessions = ingestion._extract_possessions(sample_event_data)
    
    assert 1 in possessions  # First two events (Starting XI)
    assert 2 in possessions  # Pass events
    assert len(possessions[1]) == 2  # Two Starting XI events
    assert len(possessions[2]) == 2  # Two pass events

"""Tests for database query functions."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_performance_diagnostics.diagnostics import (
    _query_state_changes,
    async_get_db_health,
    async_get_state_change_analysis,
)


@pytest.fixture
def mock_db():
    """Create a temporary SQLite database with test data."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)

    # Create states_meta table (new schema)
    conn.execute(
        """
        CREATE TABLE states_meta (
            metadata_id INTEGER PRIMARY KEY,
            entity_id TEXT NOT NULL
        )
        """
    )

    # Create states table
    conn.execute(
        """
        CREATE TABLE states (
            state_id INTEGER PRIMARY KEY,
            metadata_id INTEGER,
            last_updated_ts REAL,
            FOREIGN KEY (metadata_id) REFERENCES states_meta(metadata_id)
        )
        """
    )

    # Insert entity metadata
    entities = [
        (1, "sensor.outdoor_temp"),
        (2, "binary_sensor.motion"),
        (3, "sensor.power_meter"),
        (4, "sensor.rarely_changes"),
    ]
    conn.executemany(
        "INSERT INTO states_meta (metadata_id, entity_id) VALUES (?, ?)",
        entities,
    )

    # Insert state changes in the last hour
    now = time.time()
    state_id = 1
    changes = [
        (1, 142),  # sensor.outdoor_temp: 142 changes
        (2, 98),  # binary_sensor.motion: 98 changes
        (3, 76),  # sensor.power_meter: 76 changes
        (4, 2),  # sensor.rarely_changes: 2 changes
    ]
    for metadata_id, count in changes:
        for i in range(count):
            ts = now - (3600 * i / count)  # Spread across last hour
            conn.execute(
                "INSERT INTO states (state_id, metadata_id, last_updated_ts) VALUES (?, ?, ?)",
                (state_id, metadata_id, ts),
            )
            state_id += 1

    conn.commit()
    conn.close()

    yield db_path

    os.unlink(db_path)


@pytest.fixture
def empty_db():
    """Create an empty temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE states_meta (
            metadata_id INTEGER PRIMARY KEY,
            entity_id TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE states (
            state_id INTEGER PRIMARY KEY,
            metadata_id INTEGER,
            last_updated_ts REAL
        )
        """
    )
    conn.commit()
    conn.close()

    yield db_path

    os.unlink(db_path)


class TestQueryStateChanges:
    """Test the _query_state_changes function."""

    def test_returns_correct_ranking(self, mock_db):
        """Top entities are correctly ranked by change count."""
        entities, total = _query_state_changes(mock_db)
        assert len(entities) >= 3
        assert entities[0]["entity_id"] == "sensor.outdoor_temp"
        assert entities[1]["entity_id"] == "binary_sensor.motion"
        assert entities[2]["entity_id"] == "sensor.power_meter"

    def test_change_counts(self, mock_db):
        """Change counts match inserted data."""
        entities, total = _query_state_changes(mock_db)
        assert entities[0]["changes_per_hour"] == 142
        assert entities[1]["changes_per_hour"] == 98
        assert entities[2]["changes_per_hour"] == 76

    def test_total_changes(self, mock_db):
        """Total changes is sum across all entities."""
        entities, total = _query_state_changes(mock_db)
        assert total == 142 + 98 + 76 + 2

    def test_empty_database(self, empty_db):
        """Empty database returns empty list."""
        entities, total = _query_state_changes(empty_db)
        assert entities == []
        assert total == 0

    def test_nonexistent_db(self):
        """Non-existent database returns empty results."""
        entities, total = _query_state_changes("/nonexistent/path.db")
        assert entities == []
        assert total == 0


class TestAsyncGetDbHealth:
    """Test the async_get_db_health function."""

    @pytest.mark.asyncio
    async def test_db_not_found(self):
        """Returns None for missing database."""
        hass = MagicMock()
        hass.config.path.return_value = "/nonexistent/path.db"
        hass.async_add_executor_job = AsyncMock(return_value=None)

        result = await async_get_db_health(hass)
        assert result["db_size_mb"] is None

    @pytest.mark.asyncio
    async def test_db_found(self, mock_db):
        """Returns size for existing database."""
        hass = MagicMock()
        hass.config.path.return_value = mock_db

        async def run_executor(fn, *args):
            return fn(*args)

        hass.async_add_executor_job = run_executor

        with patch("homeassistant.components.recorder.get_instance") as mock_recorder:
            mock_recorder.return_value = MagicMock(backlog=5)
            result = await async_get_db_health(hass)

        assert result["db_size_mb"] is not None
        assert result["db_size_mb"] > 0
        assert result["integrity_ok"] is True
        assert result["recorder_queue_size"] == 5


class TestAsyncGetStateChangeAnalysis:
    """Test the async_get_state_change_analysis function."""

    @pytest.mark.asyncio
    async def test_returns_top_entities(self, mock_db):
        """Returns enriched top entities."""
        hass = MagicMock()
        hass.config.path.return_value = mock_db
        hass.states.get.return_value = MagicMock(attributes={"friendly_name": "Test Entity"})
        hass.states.async_all.return_value = [MagicMock()] * 50

        async def run_executor(fn, *args):
            return fn(*args)

        hass.async_add_executor_job = run_executor

        with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_async_get:
            mock_registry = MagicMock()
            mock_registry.async_get.return_value = MagicMock(platform="test_platform")
            mock_er_async_get.return_value = mock_registry

            result = await async_get_state_change_analysis(hass, threshold=60)

        assert len(result["top_entities"]) == 3
        assert result["top_entities"][0]["entity_id"] == "sensor.outdoor_temp"
        assert result["top_entities"][0]["changes_per_hour"] == 142
        assert result["total_changes"] > 0
        assert result["data_window_minutes"] == 60

    @pytest.mark.asyncio
    async def test_threshold_marking(self, mock_db):
        """Entities exceeding threshold are marked."""
        hass = MagicMock()
        hass.config.path.return_value = mock_db
        hass.states.get.return_value = None
        hass.states.async_all.return_value = []

        async def run_executor(fn, *args):
            return fn(*args)

        hass.async_add_executor_job = run_executor

        with patch("homeassistant.helpers.entity_registry.async_get") as mock_er_async_get:
            mock_er_async_get.return_value = MagicMock(async_get=MagicMock(return_value=None))

            result = await async_get_state_change_analysis(hass, threshold=100)

        # outdoor_temp has 142 changes, exceeds 100 threshold
        assert result["top_entities"][0]["exceeds_threshold"] is True
        # motion has 98, below 100 threshold
        assert result["top_entities"][1]["exceeds_threshold"] is False

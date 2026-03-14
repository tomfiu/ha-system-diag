"""Tests for the health score calculation."""

from __future__ import annotations

import copy

import pytest

from custom_components.ha_performance_diagnostics.const import (
    CONF_DB_SIZE_WARN_MB,
    CONF_STATE_CHANGE_THRESHOLD,
    DATA_ANTIPATTERNS,
    DATA_DB,
    DATA_INTEGRATIONS,
    DATA_STATE_CHANGES,
    DATA_SYSTEM,
    DEFAULT_DB_SIZE_WARN_MB,
    DEFAULT_STATE_CHANGE_THRESHOLD,
)
from custom_components.ha_performance_diagnostics.diagnostics import (
    calculate_health_score,
)


class TestHealthScore:
    """Test the health score formula."""

    def test_perfect_score(self, sample_coordinator_data):
        """All metrics nominal returns 100."""
        score = calculate_health_score(sample_coordinator_data)
        assert score == 100

    def test_cpu_medium_deduction(self, sample_coordinator_data):
        """CPU between 30-50% deducts 10."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_SYSTEM]["cpu_percent"] = 35.0
        score = calculate_health_score(data)
        assert score == 90

    def test_cpu_high_deduction(self, sample_coordinator_data):
        """CPU above 50% deducts 20 (not 30)."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_SYSTEM]["cpu_percent"] = 55.0
        score = calculate_health_score(data)
        assert score == 80

    def test_cpu_exactly_30_no_deduction(self, sample_coordinator_data):
        """CPU at exactly 30% should not deduct."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_SYSTEM]["cpu_percent"] = 30.0
        score = calculate_health_score(data)
        assert score == 100

    def test_cpu_exactly_50_deducts_10(self, sample_coordinator_data):
        """CPU at exactly 50% should deduct 10 (medium tier)."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_SYSTEM]["cpu_percent"] = 50.0
        score = calculate_health_score(data)
        assert score == 90

    def test_db_medium_deduction(self, sample_coordinator_data):
        """DB size at 80% of warn threshold deducts 10."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_DB]["db_size_mb"] = 800.0  # 80% of 1000
        score = calculate_health_score(data)
        assert score == 90

    def test_db_high_deduction(self, sample_coordinator_data):
        """DB size over warn threshold deducts 20."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_DB]["db_size_mb"] = 1200.0
        score = calculate_health_score(data)
        assert score == 80

    def test_db_below_75_percent_no_deduction(self, sample_coordinator_data):
        """DB size below 75% of warn threshold should not deduct."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_DB]["db_size_mb"] = 700.0  # 70% of 1000
        score = calculate_health_score(data)
        assert score == 100

    def test_db_size_none_no_deduction(self, sample_coordinator_data):
        """DB size None should not deduct."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_DB]["db_size_mb"] = None
        score = calculate_health_score(data)
        assert score == 100

    def test_noisy_entity_deduction(self, sample_coordinator_data):
        """Entity exceeding threshold deducts 15."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_STATE_CHANGES]["top_entities"][0]["changes_per_hour"] = 100
        score = calculate_health_score(data)
        assert score == 85

    def test_recorder_queue_deduction(self, sample_coordinator_data):
        """Recorder queue > 500 deducts 10."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_DB]["recorder_queue_size"] = 600
        score = calculate_health_score(data)
        assert score == 90

    def test_recorder_queue_at_500_no_deduction(self, sample_coordinator_data):
        """Recorder queue at exactly 500 should not deduct."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_DB]["recorder_queue_size"] = 500
        score = calculate_health_score(data)
        assert score == 100

    def test_slow_integration_deduction(self, sample_coordinator_data):
        """Integration > 1000ms deducts 10."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_INTEGRATIONS]["slowest"][0]["avg_update_ms"] = 1500.0
        score = calculate_health_score(data)
        assert score == 90

    def test_antipattern_deductions(self, sample_coordinator_data):
        """Each antipattern deducts 5."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_ANTIPATTERNS] = [
            {"pattern": "test1"},
            {"pattern": "test2"},
            {"pattern": "test3"},
        ]
        score = calculate_health_score(data)
        assert score == 85

    def test_all_deductions_combined(self, sample_coordinator_data):
        """All deductions combined, score floors at 0."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_SYSTEM]["cpu_percent"] = 55.0  # -20
        data[DATA_DB]["db_size_mb"] = 1200.0  # -20
        data[DATA_DB]["recorder_queue_size"] = 600  # -10
        data[DATA_STATE_CHANGES]["top_entities"][0]["changes_per_hour"] = 100  # -15
        data[DATA_INTEGRATIONS]["slowest"][0]["avg_update_ms"] = 1500.0  # -10
        data[DATA_ANTIPATTERNS] = [
            {"pattern": f"test{i}"} for i in range(10)
        ]  # -50
        # Total: 100 - 20 - 20 - 10 - 15 - 10 - 50 = -25 -> 0
        score = calculate_health_score(data)
        assert score == 0

    def test_empty_data(self):
        """Empty data dict returns 100."""
        score = calculate_health_score({})
        assert score == 100

    def test_missing_keys(self):
        """Missing top-level keys don't crash."""
        data = {DATA_SYSTEM: {}, DATA_DB: {}}
        score = calculate_health_score(data)
        assert score == 100

    def test_custom_config_thresholds(self, sample_coordinator_data):
        """Custom config changes thresholds."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_DB]["db_size_mb"] = 600.0  # Over 500 but under 1000
        config = {CONF_DB_SIZE_WARN_MB: 500}
        score = calculate_health_score(data, config)
        assert score == 80  # -20 for exceeding warn

    def test_custom_state_change_threshold(self, sample_coordinator_data):
        """Custom state change threshold."""
        data = copy.deepcopy(sample_coordinator_data)
        data[DATA_STATE_CHANGES]["top_entities"][0]["changes_per_hour"] = 25
        config = {CONF_STATE_CHANGE_THRESHOLD: 20}
        score = calculate_health_score(data, config)
        assert score == 85  # -15 for noisy entity

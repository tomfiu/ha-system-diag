"""Tests for the top CPU processes feature."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.ha_performance_diagnostics.diagnostics import (
    _get_top_processes_sync,
    async_get_top_cpu_processes,
)


class TestGetTopProcessesSync:
    """Test the synchronous top-process collection logic."""

    def test_returns_empty_list_without_psutil(self):
        """When psutil is not available, return an empty list."""
        with patch(
            "custom_components.ha_performance_diagnostics.diagnostics.HAS_PSUTIL",
            False,
        ):
            result = _get_top_processes_sync()
        assert result == []

    def test_returns_top_5_processes(self):
        """Returns at most 5 processes sorted by CPU descending."""
        fake_procs = [
            _make_proc(pid=i, name=f"proc{i}", cpu=float(i * 5), mem=1.0) for i in range(10)
        ]
        with (
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.HAS_PSUTIL",
                True,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.psutil.process_iter",
                return_value=fake_procs,
            ),
        ):
            result = _get_top_processes_sync()

        assert len(result) == 5
        # Highest CPU first
        assert result[0]["cpu_percent"] >= result[1]["cpu_percent"]

    def test_process_dict_shape(self):
        """Each process dict has the expected keys."""
        fake_procs = [_make_proc(pid=42, name="homeassistant", cpu=12.5, mem=3.2)]
        with (
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.HAS_PSUTIL",
                True,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.psutil.process_iter",
                return_value=fake_procs,
            ),
        ):
            result = _get_top_processes_sync()

        assert len(result) == 1
        proc = result[0]
        assert proc["pid"] == 42
        assert proc["name"] == "homeassistant"
        assert proc["cpu_percent"] == 12.5
        assert proc["memory_percent"] == 3.2
        assert "cmdline" in proc

    def test_cmdline_enriches_module_flag(self):
        """python3 -m <module> anywhere in args is used as the display name."""
        fake_procs = [
            _make_proc(
                pid=10,
                name="python3",
                cpu=20.0,
                mem=5.0,
                cmdline=["python3", "-u", "-m", "homeassistant"],
            )
        ]
        with (
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.HAS_PSUTIL",
                True,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.psutil.process_iter",
                return_value=fake_procs,
            ),
        ):
            result = _get_top_processes_sync()

        assert result[0]["name"] == "python3 -m homeassistant"

    def test_cmdline_enriches_script_path(self):
        """python3 /path/to/script.py uses the basename as the display name."""
        fake_procs = [
            _make_proc(
                pid=11,
                name="python3",
                cpu=15.0,
                mem=3.0,
                cmdline=["python3", "/usr/src/homeassistant/__main__.py"],
            )
        ]
        with (
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.HAS_PSUTIL",
                True,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.psutil.process_iter",
                return_value=fake_procs,
            ),
        ):
            result = _get_top_processes_sync()

        assert result[0]["name"] == "python3 __main__.py"

    def test_cmdline_not_enriched_for_known_process(self):
        """Non-interpreter names are left unchanged even if cmdline is present."""
        fake_procs = [
            _make_proc(
                pid=12,
                name="nginx",
                cpu=5.0,
                mem=1.0,
                cmdline=["nginx", "-g", "daemon off;"],
            )
        ]
        with (
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.HAS_PSUTIL",
                True,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.psutil.process_iter",
                return_value=fake_procs,
            ),
        ):
            result = _get_top_processes_sync()

        assert result[0]["name"] == "nginx"

    def test_skips_inaccessible_processes(self):
        """Processes raising NoSuchProcess or AccessDenied are skipped."""
        import psutil as real_psutil

        good_proc = _make_proc(pid=1, name="good", cpu=5.0, mem=1.0)
        bad_proc = MagicMock()
        bad_proc.info = property(lambda self: (_ for _ in ()).throw(real_psutil.NoSuchProcess(2)))

        # Simulate access error by raising during iteration via a custom iterable
        def _proc_iter(_attrs):
            yield good_proc
            raise real_psutil.AccessDenied(3)

        with (
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.HAS_PSUTIL",
                True,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.psutil.process_iter",
                side_effect=_proc_iter,
            ),
        ):
            result = _get_top_processes_sync()

        assert len(result) == 1
        assert result[0]["pid"] == 1

    def test_handles_none_cpu_and_memory(self):
        """None values for cpu_percent / memory_percent are replaced with 0.0."""
        fake_procs = [_make_proc(pid=99, name="proc99", cpu=None, mem=None)]
        with (
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.HAS_PSUTIL",
                True,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.psutil.process_iter",
                return_value=fake_procs,
            ),
        ):
            result = _get_top_processes_sync()

        assert result[0]["cpu_percent"] == 0.0
        assert result[0]["memory_percent"] == 0.0

    def test_handles_none_process_name(self):
        """None process name is replaced with 'unknown'."""
        fake_procs = [_make_proc(pid=7, name=None, cpu=1.0, mem=0.5)]
        with (
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.HAS_PSUTIL",
                True,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.psutil.process_iter",
                return_value=fake_procs,
            ),
        ):
            result = _get_top_processes_sync()

        assert result[0]["name"] == "unknown"


class TestAsyncGetTopCpuProcesses:
    """Test the async wrapper."""

    @pytest.mark.asyncio
    async def test_returns_processes_key(self):
        """Result dict has a 'processes' key."""
        hass = MagicMock()
        hass.async_add_executor_job = _async_executor_shim

        with (
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.HAS_PSUTIL",
                True,
            ),
            patch(
                "custom_components.ha_performance_diagnostics.diagnostics.psutil.process_iter",
                return_value=[_make_proc(1, "ha", 10.0, 2.0)],
            ),
        ):
            result = await async_get_top_cpu_processes(hass)

        assert "processes" in result
        assert isinstance(result["processes"], list)

    @pytest.mark.asyncio
    async def test_returns_empty_on_executor_error(self):
        """On executor error, returns empty processes list."""
        hass = MagicMock()

        async def _raise(*_args, **_kwargs):
            raise RuntimeError("executor failed")

        hass.async_add_executor_job = _raise

        result = await async_get_top_cpu_processes(hass)
        assert result == {"processes": []}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_proc(
    pid: int,
    name: str | None,
    cpu: float | None,
    mem: float | None,
    cmdline: list[str] | None = None,
):
    """Create a fake psutil Process mock with .info dict."""
    proc = MagicMock()
    proc.info = {
        "pid": pid,
        "name": name,
        "cpu_percent": cpu,
        "memory_percent": mem,
        "cmdline": cmdline or [],
    }
    return proc


async def _async_executor_shim(func, *args):
    """Run a sync function as if it were in an executor (for tests)."""
    return func(*args)

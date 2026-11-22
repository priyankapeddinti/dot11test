"""pytest plugin: report device capabilities the DUT lacks as skips, not failures.

Drivers raise NotImplementedError for operations a platform/config can't do
(e.g. iOS WiFi control with no helper configured). Converting those to skips
keeps device test reports honest. Tests marked `unit` are exempt so a stray
NotImplementedError in framework code still fails loudly.
"""
from __future__ import annotations

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if (
        report.failed
        and call.excinfo is not None
        and call.excinfo.errisinstance(NotImplementedError)
        and item.get_closest_marker("unit") is None
    ):
        report.outcome = "skipped"
        path, lineno, _ = item.location
        report.longrepr = (path, (lineno or 0) + 1, f"Skipped: {call.excinfo.value}")

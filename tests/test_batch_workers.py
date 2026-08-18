"""Batch worker cap: parallel workers stay under moomoo connection limits."""

import os
from unittest import mock

import batch


def test_workers_capped_below_limit():
    assert batch.effective_workers(8) == 4
    assert batch.effective_workers(3) == 3
    assert batch.effective_workers(-5) == 1


def test_env_override():
    with mock.patch.dict(os.environ, {"TRADINGAGENTS_MAX_WORKERS": "6"}):
        assert batch.effective_workers(50) == 6
    with mock.patch.dict(os.environ, {"TRADINGAGENTS_MAX_WORKERS": "junk"}):
        assert batch.effective_workers(9) == 4

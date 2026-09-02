"""Tests for news relevance + coalescing + degrade triple (DSA phase C; §6-5).

- planted articles scored + admission (official-pass, spam-drop)
- coalescing dedups concurrent identical searches (threaded)
- degrade triple distinguishes failed vs empty
"""

import threading
import time

import pytest

from tradingagents.dataflows.news_cache import CoalescingCache
from tradingagents.strategies import news_relevance as nr

pytestmark = pytest.mark.timeout(30)


class TestRelevance:
    def test_code_in_title_scores_high(self):
        r = nr.score_news_article("AAPL beats Apple earnings", "http://x.com/a", "", "AAPL", "Apple")
        assert r["score"] >= 55 + 45  # code + company-name in title

    def test_official_boost(self):
        r = nr.score_news_article("Apple 10-Q", "https://www.sec.gov/Archives/edgar/data/1/0001.html",
                                  "", "AAPL", "Apple")
        assert "official-source" in r["reasons"] and r["score"] >= 8

    def test_macro_penalty(self):
        r = nr.score_news_article("Fed rate hike hits markets", "http://x.com/fed", "", "AAPL", "")
        assert "macro-term" in r["reasons"]
        assert r["score"] < 55  # no code hit; macro penalty

    def test_reasons_capped_five(self):
        r = nr.score_news_article("AAPL Apple surges", "https://www.nasdaq.com/AAPL",
                                  "AAPL apple news", "AAPL", "Apple")
        assert len(r["reasons"]) <= 5 and r["score"] <= 100.0

    def test_ambiguous_company(self):
        r = nr.score_news_article("apple releases new chip", "http://x.com", "", "", "Apple",
                                  ambiguous_names=("apple",))
        assert "company-name-title-ambiguous" in r["reasons"]


class TestAdmission:
    def test_official_passes_spam_signals(self):
        assert nr.admit_article("install our app", "https://www.sec.gov/x", "app download") is True

    def test_spam_dropped(self):
        assert nr.admit_article("Click here free vip", "http://spam.com") is False
        assert nr.admit_article("download the app and earn", "http://x.com") is False

    def test_normal_passes(self):
        assert nr.admit_article("AAPL beats", "http://x.com") is True


class TestDegradeTriple:
    def test_distinct_states(self):
        assert nr.degrade_triple(True, False) == "all_failed"
        assert nr.degrade_triple(False, True) == "empty"
        assert nr.degrade_triple(False, False) == "unavailable"
        assert nr.degrade_triple(False, True, feature_off=True) == "unavailable"


class TestCoalescing:
    def test_single_fetch_for_concurrent_callers(self):
        cache = CoalescingCache(ttl_s=60, wait_max_s=5)
        calls = []

        def work():
            calls.append(1)
            time.sleep(0.1)
            return "R"

        results = []
        t0 = time.time()
        threads = [threading.Thread(target=lambda i=i: results.append(cache.fetch("k", work)))
                   for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - t0
        assert calls == [1]  # exactly ONE work call, coalesced
        assert all(r == ("R", True) for r in results)
        assert elapsed < 1.5  # waiters reused the owner result, not re-fetched

    def test_owner_failure_waiter_competes(self):
        cache = CoalescingCache(ttl_s=60, wait_max_s=3)
        outcomes = []

        def work():
            # first owner fails; the re-competing caller succeeds
            if len(outcomes) == 0:
                outcomes.append("fail")
                raise RuntimeError("boom")
            outcomes.append("ok")
            return "VAL"

        r1 = cache.fetch("k", work)
        r2 = cache.fetch("k", work)
        assert r1 == (None, False)   # owner produced nothing
        assert r2 == ("VAL", True)   # waiter re-competed and succeeded
        assert outcomes == ["fail", "ok"]

    def test_ttl_expiry(self):
        cache = CoalescingCache(ttl_s=0.1, wait_max_s=1)
        assert cache.fetch("k", lambda: "v") == ("v", True)
        time.sleep(0.2)
        assert cache.get("k") is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

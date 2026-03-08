"""Unit tests for SyncResult — the uniform return type for all pipeline services."""

from app.services.sync_result import SyncResult


class TestSyncResultDefaults:
    def test_initial_counters_are_zero(self):
        r = SyncResult()
        assert r.n_written == 0
        assert r.n_updated == 0
        assert r.n_skipped == 0
        assert r.n_failed == 0

    def test_initial_events_empty(self):
        assert SyncResult().events == []

    def test_total_is_zero_on_init(self):
        assert SyncResult().total == 0


class TestSyncResultTotal:
    def test_total_sums_all_counters(self):
        r = SyncResult(n_written=1, n_updated=2, n_skipped=3, n_failed=4)
        assert r.total == 10

    def test_total_reflects_mutations(self):
        r = SyncResult()
        r.n_written += 5
        r.n_failed += 2
        assert r.total == 7


class TestSyncResultAddEvent:
    def test_add_event_appends(self):
        r = SyncResult()
        r.add_event("something failed")
        assert "something failed" in r.events

    def test_add_event_multiple(self):
        r = SyncResult()
        r.add_event("first")
        r.add_event("second")
        assert r.events == ["first", "second"]


class TestSyncResultMerge:
    def test_merge_adds_counters(self):
        a = SyncResult(n_written=2, n_updated=1, n_skipped=0, n_failed=0)
        b = SyncResult(n_written=1, n_updated=0, n_skipped=3, n_failed=1)
        a.merge(b)
        assert a.n_written == 3
        assert a.n_updated == 1
        assert a.n_skipped == 3
        assert a.n_failed == 1

    def test_merge_extends_events(self):
        a = SyncResult(events=["event_a"])
        b = SyncResult(events=["event_b", "event_c"])
        a.merge(b)
        assert a.events == ["event_a", "event_b", "event_c"]

    def test_merge_does_not_mutate_other(self):
        a = SyncResult(n_written=1)
        b = SyncResult(n_written=2)
        a.merge(b)
        assert b.n_written == 2  # unchanged

    def test_merge_with_empty(self):
        a = SyncResult(n_written=5, events=["keep"])
        a.merge(SyncResult())
        assert a.n_written == 5
        assert a.events == ["keep"]

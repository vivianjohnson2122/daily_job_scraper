"""Tests for the SeenStore deduplication logic."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.scrapers.base import Job
from src.seen_store import SeenStore, TTL_DAYS


def _make_job(job_id: str, company: str = "Apple") -> Job:
    return Job(
        company=company,
        job_id=job_id,
        title=f"Data Scientist {job_id}",
        location="Cupertino, CA",
        url=f"https://jobs.apple.com/en-us/details/{job_id}/data-scientist",
    )


def test_filter_new_returns_all_on_empty_store(tmp_path: Path) -> None:
    store = SeenStore(path=tmp_path / "seen.json")
    jobs = [_make_job("AAA"), _make_job("BBB")]
    new = store.filter_new(jobs)
    assert new == jobs


def test_filter_new_deduplicates_on_second_call(tmp_path: Path) -> None:
    store = SeenStore(path=tmp_path / "seen.json")
    jobs = [_make_job("AAA"), _make_job("BBB")]
    store.filter_new(jobs)
    # Second call with the same jobs — all should be filtered out.
    new = store.filter_new(jobs)
    assert new == []


def test_filter_new_allows_different_companies(tmp_path: Path) -> None:
    store = SeenStore(path=tmp_path / "seen.json")
    apple_job = _make_job("123", company="Apple")
    google_job = _make_job("123", company="Google")
    new = store.filter_new([apple_job, google_job])
    assert len(new) == 2, "Same job_id from different companies must be distinct."


def test_save_and_reload_persists_state(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    store = SeenStore(path=path)
    store.filter_new([_make_job("AAA")])
    store.save()

    store2 = SeenStore(path=path)
    new = store2.filter_new([_make_job("AAA")])
    assert new == [], "Job seen before save should still be deduped after reload."


def test_expired_entries_are_pruned(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    old_ts = (datetime.now(timezone.utc) - timedelta(days=TTL_DAYS + 1)).isoformat()
    path.write_text(json.dumps({"Apple::OLD": old_ts}))

    store = SeenStore(path=path)
    new = store.filter_new([_make_job("OLD")])
    assert len(new) == 1, "Entries older than TTL should be treated as new."


def test_save_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "dir" / "seen.json"
    store = SeenStore(path=path)
    store.filter_new([_make_job("X")])
    store.save()
    assert path.exists()


def test_corrupt_state_file_starts_fresh(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    path.write_text("not valid json {{{")
    store = SeenStore(path=path)
    jobs = [_make_job("AAA")]
    new = store.filter_new(jobs)
    assert new == jobs, "Corrupt state file should be ignored and all jobs treated as new."

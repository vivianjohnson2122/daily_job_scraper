"""Tests for the email digest builder (no real SMTP calls)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.emailer import send_job_digest, _plain_body, _html_body, _group_by_company
from src.scrapers.base import Job


def _job(company: str, title: str, location: str = "", url: str = "https://example.com") -> Job:
    return Job(company=company, job_id="1", title=title, location=location, url=url)


CFG = Config(gmail_user="test@gmail.com", gmail_app_password="secret")


# ---------------------------------------------------------------------------
# _group_by_company
# ---------------------------------------------------------------------------

def test_group_by_company_groups_correctly() -> None:
    jobs = [_job("Apple", "DS Role"), _job("Google", "ML Role"), _job("Apple", "AI Role")]
    grouped = _group_by_company(jobs)
    assert len(grouped["Apple"]) == 2
    assert len(grouped["Google"]) == 1


# ---------------------------------------------------------------------------
# _plain_body
# ---------------------------------------------------------------------------

def test_plain_body_contains_company_name() -> None:
    jobs = [_job("Apple", "Data Scientist", location="Cupertino, CA")]
    body = _plain_body(jobs)
    assert "Apple" in body
    assert "Data Scientist" in body
    assert "Cupertino, CA" in body


def test_plain_body_contains_url() -> None:
    jobs = [_job("Google", "ML Engineer", url="https://careers.google.com/123")]
    body = _plain_body(jobs)
    assert "https://careers.google.com/123" in body


def test_plain_body_no_location_omits_dash() -> None:
    jobs = [_job("Apple", "Scientist", location="")]
    body = _plain_body(jobs)
    assert " — " not in body


# ---------------------------------------------------------------------------
# _html_body
# ---------------------------------------------------------------------------

def test_html_body_is_valid_html_structure() -> None:
    jobs = [_job("Apple", "Data Scientist")]
    html = _html_body(jobs, "2026-04-20")
    assert "<html>" in html
    assert "</html>" in html
    assert "<ul>" in html
    assert "<li>" in html


def test_html_body_escapes_special_chars() -> None:
    jobs = [_job("Apple", "<script>alert(1)</script>", url="https://safe.com")]
    html = _html_body(jobs, "2026-04-20")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_html_body_contains_link() -> None:
    jobs = [_job("Apple", "DS", url="https://jobs.apple.com/details/123")]
    html = _html_body(jobs, "2026-04-20")
    assert 'href="https://jobs.apple.com/details/123"' in html


# ---------------------------------------------------------------------------
# send_job_digest
# ---------------------------------------------------------------------------

def test_send_job_digest_skips_on_empty_list() -> None:
    with patch("src.emailer.smtplib.SMTP") as mock_smtp:
        send_job_digest([], CFG)
        mock_smtp.assert_not_called()


def test_send_job_digest_calls_smtp_with_jobs() -> None:
    jobs = [_job("Apple", "Data Scientist")]
    with patch("src.emailer.smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        send_job_digest(jobs, CFG)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with(CFG.gmail_user, CFG.gmail_app_password)
        mock_server.send_message.assert_called_once()

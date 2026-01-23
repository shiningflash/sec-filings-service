"""Tests for filings module - parsing submissions JSON and selecting latest 10-K."""

import pytest

from src.services.filings import No10KFoundError, _parse_latest_10k

# Sample submissions JSON structure (minimal fixture)
SAMPLE_SUBMISSIONS = {
    "cik": "320193",
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "form": ["10-Q", "8-K", "10-K", "10-K", "8-K"],
            "accessionNumber": [
                "0000320193-24-000001",
                "0000320193-23-000099",
                "0000320193-23-000106",  # Latest 10-K (2023-11-03)
                "0000320193-22-000108",  # Older 10-K (2022-10-28)
                "0000320193-22-000050",
            ],
            "primaryDocument": [
                "aapl-20240101.htm",
                "aapl-8k.htm",
                "aapl-20230930.htm",
                "aapl-20220924.htm",
                "aapl-8k-old.htm",
            ],
            "filingDate": [
                "2024-01-15",
                "2023-12-01",
                "2023-11-03",  # Latest 10-K date
                "2022-10-28",
                "2022-06-15",
            ],
            "reportDate": [
                "2024-01-01",
                "2023-11-30",
                "2023-09-30",
                "2022-09-24",
                "2022-06-01",
            ],
        }
    },
}


class TestParseLatest10K:
    """Tests for _parse_latest_10k function."""

    def test_selects_latest_10k_by_filing_date(self):
        """Should select the 10-K with the most recent filing date."""
        result = _parse_latest_10k(SAMPLE_SUBMISSIONS, "AAPL")

        assert result.accession_number == "0000320193-23-000106"
        assert result.filing_date == "2023-11-03"
        assert result.primary_document == "aapl-20230930.htm"
        assert result.form_type == "10-K"

    def test_returns_correct_report_date(self):
        """Should include report date when available."""
        result = _parse_latest_10k(SAMPLE_SUBMISSIONS, "AAPL")

        assert result.report_date == "2023-09-30"

    def test_raises_when_no_10k_found(self):
        """Should raise No10KFoundError when no 10-K exists."""
        submissions_no_10k = {
            "filings": {
                "recent": {
                    "form": ["10-Q", "8-K", "8-K"],
                    "accessionNumber": ["a", "b", "c"],
                    "primaryDocument": ["x.htm", "y.htm", "z.htm"],
                    "filingDate": ["2023-01-01", "2023-02-01", "2023-03-01"],
                    "reportDate": ["", "", ""],
                }
            }
        }

        with pytest.raises(No10KFoundError, match="No 10-K filing found"):
            _parse_latest_10k(submissions_no_10k, "TEST")

    def test_raises_when_no_filings(self):
        """Should raise when filings array is empty."""
        empty_submissions = {"filings": {"recent": {"form": []}}}

        with pytest.raises(No10KFoundError, match="No filings found"):
            _parse_latest_10k(empty_submissions, "TEST")

    def test_handles_single_10k(self):
        """Should work with only one 10-K filing."""
        single_10k = {
            "filings": {
                "recent": {
                    "form": ["10-K"],
                    "accessionNumber": ["0001-23-000001"],
                    "primaryDocument": ["doc.htm"],
                    "filingDate": ["2023-05-01"],
                    "reportDate": ["2023-04-30"],
                }
            }
        }

        result = _parse_latest_10k(single_10k, "TEST")

        assert result.accession_number == "0001-23-000001"
        assert result.filing_date == "2023-05-01"

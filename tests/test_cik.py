"""Tests for ticker to CIK resolution."""

import pytest

from src.services.cik import (
    get_default_companies,
    get_ticker_for_company,
    resolve_ticker_to_cik,
)


class TestResolveTickerToCik:
    """Tests for resolve_ticker_to_cik function."""

    @pytest.fixture
    def sample_ticker_map(self) -> dict[str, int]:
        """Sample ticker map for testing."""
        return {
            "AAPL": 320193,
            "META": 1326801,
            "GOOGL": 1652044,
            "AMZN": 1018724,
            "NFLX": 1065280,
            "GS": 886982,
        }

    def test_resolves_valid_ticker(self, sample_ticker_map: dict[str, int]) -> None:
        """Should return CIK for known ticker."""
        cik_int, cik10 = resolve_ticker_to_cik("AAPL", sample_ticker_map)
        assert cik_int == 320193
        assert cik10 == "0000320193"

    def test_case_insensitive(self, sample_ticker_map: dict[str, int]) -> None:
        """Ticker lookup should be case-insensitive."""
        cik_int, _ = resolve_ticker_to_cik("aapl", sample_ticker_map)
        assert cik_int == 320193

    def test_raises_for_unknown_ticker(self, sample_ticker_map: dict[str, int]) -> None:
        """Should raise ValueError for unknown ticker."""
        with pytest.raises(ValueError, match="not found"):
            resolve_ticker_to_cik("UNKNOWN", sample_ticker_map)

    def test_returns_padded_cik10(self, sample_ticker_map: dict[str, int]) -> None:
        """CIK10 should be 10 digits with leading zeros."""
        _, cik10 = resolve_ticker_to_cik("GS", sample_ticker_map)
        assert len(cik10) == 10
        assert cik10 == "0000886982"


class TestGetTickerForCompany:
    """Tests for get_ticker_for_company function."""

    def test_maps_known_company(self) -> None:
        """Should return ticker for known company name."""
        assert get_ticker_for_company("Apple") == "AAPL"
        assert get_ticker_for_company("Goldman Sachs") == "GS"

    def test_case_insensitive_company_name(self) -> None:
        """Company name lookup should be case-insensitive."""
        assert get_ticker_for_company("apple") == "AAPL"
        assert get_ticker_for_company("APPLE") == "AAPL"

    def test_returns_ticker_as_is_if_unknown(self) -> None:
        """Should return input as-is if not a known company name (assumes it's a ticker)."""
        assert get_ticker_for_company("TSLA") == "TSLA"


class TestGetDefaultCompanies:
    """Tests for get_default_companies function."""

    def test_returns_six_companies(self) -> None:
        """Should return list of 6 default companies."""
        companies = get_default_companies()
        assert len(companies) == 6

    def test_contains_expected_companies(self) -> None:
        """Should include all required companies."""
        companies = get_default_companies()
        expected = {"Apple", "Meta", "Alphabet", "Amazon", "Netflix", "Goldman Sachs"}
        assert set(companies) == expected

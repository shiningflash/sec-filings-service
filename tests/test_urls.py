"""Tests for URL construction and accession number formatting."""

from src.core.settings import SEC_ARCHIVES_URL
from src.core.utils import accession_no_dashes, format_cik, safe_filename


class TestAccessionNoDashes:
    """Tests for accession_no_dashes function."""

    def test_removes_dashes(self):
        """Should remove all dashes from accession number."""
        assert accession_no_dashes("0000320193-23-000106") == "000032019323000106"

    def test_handles_no_dashes(self):
        """Should return unchanged if no dashes present."""
        assert accession_no_dashes("000032019323000106") == "000032019323000106"

    def test_handles_empty_string(self):
        """Should handle empty string."""
        assert accession_no_dashes("") == ""


class TestFormatCik:
    """Tests for format_cik function."""

    def test_pads_to_10_digits(self):
        """Should zero-pad CIK to 10 digits."""
        cik_int, cik10 = format_cik(320193)

        assert cik_int == 320193
        assert cik10 == "0000320193"
        assert len(cik10) == 10

    def test_handles_string_input(self):
        """Should handle string CIK input."""
        cik_int, cik10 = format_cik("320193")

        assert cik_int == 320193
        assert cik10 == "0000320193"

    def test_handles_padded_string_input(self):
        """Should handle already-padded string input."""
        cik_int, cik10 = format_cik("0000320193")

        assert cik_int == 320193
        assert cik10 == "0000320193"

    def test_large_cik(self):
        """Should handle large CIK numbers."""
        cik_int, cik10 = format_cik(1326801)  # Meta's CIK

        assert cik_int == 1326801
        assert cik10 == "0001326801"


class TestArchivesUrl:
    """Tests for SEC Archives URL construction."""

    def test_constructs_valid_url(self):
        """Should construct valid Archives URL."""
        url = SEC_ARCHIVES_URL.format(
            cik_int=320193,
            accession_no_dashes="000032019323000106",
            document="aapl-20230930.htm",
        )

        assert url == (
            "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm"
        )


class TestSafeFilename:
    """Tests for safe_filename function."""

    def test_joins_parts_with_separator(self):
        """Should join parts with underscore."""
        result = safe_filename("AAPL", "2023-11-03", "10-K", extension=".pdf")

        assert result == "AAPL_2023-11-03_10-K.pdf"

    def test_removes_spaces(self):
        """Should replace spaces with underscores."""
        result = safe_filename("Goldman Sachs", "2023-01-01")

        assert " " not in result
        assert "Goldman_Sachs" in result

    def test_removes_slashes(self):
        """Should remove slashes from filename."""
        result = safe_filename("test/file", "data")

        assert "/" not in result
        assert "\\" not in result

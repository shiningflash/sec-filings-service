"""Tests for fallback index page parsing."""

from src.services.download import _parse_index_for_10k_document

# Minimal index page HTML fixture
SAMPLE_INDEX_HTML = """
<!DOCTYPE html>
<html>
<head><title>Filing Index</title></head>
<body>
<table>
    <tr>
        <td><a href="aapl-20230930.htm">aapl-20230930.htm</a></td>
        <td>10-K</td>
        <td>Annual Report</td>
    </tr>
    <tr>
        <td><a href="aapl-20230930_g1.jpg">aapl-20230930_g1.jpg</a></td>
        <td>GRAPHIC</td>
        <td>Image file</td>
    </tr>
    <tr>
        <td><a href="Financial_Report.xlsx">Financial_Report.xlsx</a></td>
        <td>EX-101</td>
        <td>XBRL data</td>
    </tr>
</table>
</body>
</html>
"""

SAMPLE_INDEX_WITH_10K_DESCRIPTION = """
<html>
<body>
<table>
    <tr><td><a href="cover.htm">Cover Page</a></td></tr>
    <tr><td><a href="form10k.htm">Complete 10-K Filing</a></td></tr>
    <tr><td><a href="exhibit.htm">Exhibit</a></td></tr>
</table>
</body>
</html>
"""

SAMPLE_INDEX_NO_HTML = """
<html>
<body>
<table>
    <tr><td><a href="data.xml">XML Data</a></td></tr>
    <tr><td><a href="image.png">Image</a></td></tr>
</table>
</body>
</html>
"""


class TestParseIndexFor10KDocument:
    """Tests for _parse_index_for_10k_document function."""

    def test_finds_htm_document(self):
        """Should find .htm document from index."""
        result = _parse_index_for_10k_document(SAMPLE_INDEX_HTML, "AAPL")

        assert result == "aapl-20230930.htm"

    def test_finds_10k_by_description(self):
        """Should prefer document with 10-K in description."""
        result = _parse_index_for_10k_document(SAMPLE_INDEX_WITH_10K_DESCRIPTION, "TEST")

        assert result == "form10k.htm"

    def test_returns_none_when_no_html(self):
        """Should return None when no HTML documents found."""
        result = _parse_index_for_10k_document(SAMPLE_INDEX_NO_HTML, "TEST")

        assert result is None

    def test_ignores_index_html(self):
        """Should ignore *-index.html files."""
        html_with_index = """
        <html><body>
        <a href="0001-23-000001-index.html">Index</a>
        <a href="main10k.htm">Main Filing</a>
        </body></html>
        """

        result = _parse_index_for_10k_document(html_with_index, "TEST")

        assert result == "main10k.htm"

    def test_handles_empty_html(self):
        """Should handle empty/minimal HTML gracefully."""
        result = _parse_index_for_10k_document("<html></html>", "TEST")

        assert result is None

    def test_prefers_10k_pattern_in_filename(self):
        """Should prefer filenames containing '10k' pattern."""
        html = """
        <html><body>
        <a href="cover.htm">Cover</a>
        <a href="company-10k-2023.htm">Annual Report</a>
        </body></html>
        """

        result = _parse_index_for_10k_document(html, "TEST")

        assert result == "company-10k-2023.htm"

"""Tests for URL rewriting in download module."""

from src.services.download import _rewrite_relative_urls


class TestRewriteRelativeUrls:
    """Tests for _rewrite_relative_urls function."""

    def test_rewrites_relative_src(self) -> None:
        """Should rewrite relative src attributes to absolute URLs."""
        html = '<img src="image.jpg">'
        base_url = "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/"
        result = _rewrite_relative_urls(html, base_url)
        assert (
            result
            == '<img src="https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/image.jpg">'
        )

    def test_rewrites_relative_href(self) -> None:
        """Should rewrite relative href attributes to absolute URLs."""
        html = '<a href="document.htm">Link</a>'
        base_url = "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/"
        result = _rewrite_relative_urls(html, base_url)
        assert (
            result
            == '<a href="https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/document.htm">Link</a>'
        )

    def test_preserves_absolute_urls(self) -> None:
        """Should not modify already-absolute URLs."""
        html = '<img src="https://example.com/image.jpg">'
        result = _rewrite_relative_urls(html, "https://www.sec.gov/base/")
        assert result == '<img src="https://example.com/image.jpg">'

    def test_preserves_data_urls(self) -> None:
        """Should not modify data: URLs."""
        html = '<img src="data:image/png;base64,ABC123">'
        result = _rewrite_relative_urls(html, "https://www.sec.gov/base/")
        assert result == '<img src="data:image/png;base64,ABC123">'

    def test_preserves_anchors(self) -> None:
        """Should not modify anchor references."""
        html = '<a href="#section1">Jump</a>'
        result = _rewrite_relative_urls(html, "https://www.sec.gov/base/")
        assert result == '<a href="#section1">Jump</a>'

    def test_preserves_javascript_urls(self) -> None:
        """Should not modify javascript: URLs."""
        html = '<a href="javascript:void(0)">Click</a>'
        result = _rewrite_relative_urls(html, "https://www.sec.gov/base/")
        assert result == '<a href="javascript:void(0)">Click</a>'

    def test_handles_single_quotes(self) -> None:
        """Should work with single-quoted attributes."""
        html = "<img src='image.jpg'>"
        base_url = "https://www.sec.gov/base/"
        result = _rewrite_relative_urls(html, base_url)
        assert result == "<img src='https://www.sec.gov/base/image.jpg'>"

    def test_adds_trailing_slash_to_base_url(self) -> None:
        """Should add trailing slash to base_url if missing."""
        html = '<img src="image.jpg">'
        base_url = "https://www.sec.gov/base"  # No trailing slash
        result = _rewrite_relative_urls(html, base_url)
        assert result == '<img src="https://www.sec.gov/base/image.jpg">'

    def test_rewrites_multiple_urls(self) -> None:
        """Should rewrite all relative URLs in document."""
        html = """
        <img src="logo.jpg">
        <img src="chart.png">
        <a href="exhibit.htm">Exhibit</a>
        """
        base_url = "https://www.sec.gov/base/"
        result = _rewrite_relative_urls(html, base_url)
        assert 'src="https://www.sec.gov/base/logo.jpg"' in result
        assert 'src="https://www.sec.gov/base/chart.png"' in result
        assert 'href="https://www.sec.gov/base/exhibit.htm"' in result

    def test_handles_sec_filing_image_pattern(self) -> None:
        """Should correctly rewrite SEC filing image filenames."""
        html = '<img src="aapl-20230930_g1.jpg">'
        base_url = "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/"
        result = _rewrite_relative_urls(html, base_url)
        expected = '<img src="https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930_g1.jpg">'
        assert result == expected

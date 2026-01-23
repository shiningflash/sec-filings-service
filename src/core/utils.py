"""Small pure helper functions for file handling, rate limiting, and string processing."""

import os
import re
import tempfile
import time
from pathlib import Path
from typing import Callable


def ensure_output_dirs(out_dir: str) -> dict[str, Path]:
    """Create output directory structure if it doesn't exist.

    Creates the following subdirectories:
    - html/: Downloaded primary filing documents
    - pdf/: Converted PDF files
    - json/: Saved submissions JSON for debugging

    Args:
        out_dir: Base output directory path.

    Returns:
        Dictionary mapping directory names to their Path objects:
        {"html": Path, "pdf": Path, "json": Path, "base": Path}
    """
    base = Path(out_dir)
    dirs = {
        "base": base,
        "html": base / "html",
        "pdf": base / "pdf",
        "json": base / "json",
    }

    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    return dirs


def atomic_write_bytes(path: str | Path, data: bytes) -> None:
    """Write bytes to a file atomically.

    Writes to a temporary file first, then renames to the target path.
    This prevents partial/corrupt files if the process is interrupted.

    Args:
        path: Destination file path.
        data: Bytes to write.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in the same directory (for same-filesystem rename)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        # Atomic rename (on POSIX systems)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def atomic_write_text(path: str | Path, text: str, encoding: str = "utf-8") -> None:
    """Write text to a file atomically.

    Writes to a temporary file first, then renames to the target path.
    This prevents partial/corrupt files if the process is interrupted.

    Args:
        path: Destination file path.
        text: Text content to write.
        encoding: Text encoding (default: utf-8).
    """
    atomic_write_bytes(path, text.encode(encoding))


def simple_rate_limiter(max_per_second: float) -> Callable[[], None]:
    """Create a simple rate limiter that sleeps to maintain the desired rate.

    Returns a callable that should be invoked before each request.
    It will sleep if necessary to ensure requests don't exceed the rate limit.

    Args:
        max_per_second: Maximum number of requests per second.

    Returns:
        A callable that sleeps as needed to maintain the rate limit.

    Example:
        limiter = simple_rate_limiter(2)  # Max 2 requests/second
        for url in urls:
            limiter()  # Will sleep ~0.5s between calls
            response = requests.get(url)
    """
    min_interval = 1.0 / max_per_second
    last_call_time: list[float] = [0.0]  # Use list to allow mutation in closure

    def wait() -> None:
        """Wait if necessary to maintain rate limit."""
        now = time.monotonic()
        elapsed = now - last_call_time[0]
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        last_call_time[0] = time.monotonic()

    return wait


def accession_no_dashes(accession: str) -> str:
    """Remove dashes from an SEC accession number.

    The Archives URL path requires accession numbers without dashes.
    Example: "0000320193-23-000106" -> "000032019323000106"

    Args:
        accession: SEC accession number with dashes.

    Returns:
        Accession number with dashes removed.
    """
    return accession.replace("-", "")


def safe_filename(*parts: str, separator: str = "_", extension: str = "") -> str:
    """Create a safe filename from parts by sanitizing each component.

    Removes or replaces characters that are problematic in filenames:
    - Spaces -> underscores
    - Slashes, backslashes -> removed
    - Other special characters -> removed

    Args:
        *parts: String parts to join into a filename.
        separator: Character to join parts with (default: "_").
        extension: File extension to append (e.g., ".pdf"). Include the dot.

    Returns:
        Sanitized filename string.

    Example:
        safe_filename("AAPL", "2023-11-03", "10-K", extension=".pdf")
        -> "AAPL_2023-11-03_10-K.pdf"
    """
    sanitized_parts = []
    for part in parts:
        # Replace spaces with underscores
        part = part.replace(" ", "_")
        # Remove slashes and backslashes
        part = part.replace("/", "").replace("\\", "")
        # Remove other problematic characters (keep alphanumeric, dash, underscore, dot)
        part = re.sub(r"[^\w\-.]", "", part)
        if part:
            sanitized_parts.append(part)

    filename = separator.join(sanitized_parts)

    if extension:
        # Ensure extension starts with a dot
        if not extension.startswith("."):
            extension = "." + extension
        filename += extension

    return filename


def format_cik(cik: int | str) -> tuple[int, str]:
    """Format a CIK into both integer and 10-digit padded string forms.

    Args:
        cik: CIK as integer or string (may have leading zeros).

    Returns:
        Tuple of (cik_int, cik10):
        - cik_int: Integer form (no leading zeros) for Archives path.
        - cik10: 10-digit zero-padded string for submissions endpoint.

    Example:
        format_cik(320193) -> (320193, "0000320193")
        format_cik("0000320193") -> (320193, "0000320193")
    """
    cik_int = int(str(cik).lstrip("0") or "0")
    cik10 = str(cik_int).zfill(10)
    return cik_int, cik10

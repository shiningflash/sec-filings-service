"""Main entrypoint for SEC EDGAR 10-K fetcher."""

import logging
import sys

from src.cli import parse_args
from src.clients.sec_http import SecHttpClient
from src.core.logging import setup_logging
from src.core.models import Status
from src.core.settings import USER_AGENT
from src.services.pipeline import print_summary, run_pipeline


def main() -> int:
    """Main entry point.

    Returns:
        Exit code: 0 if at least one PDF succeeded, 1 if all failed.
    """
    # Parse CLI arguments
    config = parse_args()

    # Setup logging
    log_level = logging.DEBUG if config.debug else logging.INFO
    setup_logging(level=log_level)

    print("SEC EDGAR 10-K Fetcher")
    print(f"Output directory: {config.output_dir}")
    print(f"Companies: {', '.join(config.companies)}")

    # Create HTTP client
    with SecHttpClient(
        user_agent=USER_AGENT,
        max_per_second=config.max_per_second,
        retries=config.retries,
    ) as client:
        # Run pipeline
        results = run_pipeline(
            companies=config.companies,
            client=client,
            output_dir=config.output_dir,
        )

    # Print summary
    print_summary(results)

    # Exit code: 0 if at least 1 success, 1 if all failed
    success_count = sum(1 for r in results if r.status == Status.OK)
    if success_count > 0:
        print(f"\n✓ Successfully generated {success_count} PDF(s)")
        return 0
    else:
        print("\n✗ All companies failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

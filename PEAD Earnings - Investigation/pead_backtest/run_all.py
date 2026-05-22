"""
Run the full PEAD backtest pipeline end-to-end.

Executes scripts 01–06 in order. Each script is idempotent — already-cached
data is skipped automatically, so re-running this is safe.

Usage:
    python run_all.py

To re-run a single step from scratch, delete the relevant cache file in data/
then run this again. See the spec (PEAD_BACKTEST_SPEC.md) for which file each
script writes.
"""

import subprocess
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"

STEPS = [
    ("01_fetch_constituents.py", "Fetch S&P 500 constituent change history"),
    ("02_fetch_earnings.py",     "Fetch per-ticker earnings history (678+ tickers — slow)"),
    ("03_build_universe.py",     "Build point-in-time tradeable universe"),
    ("04_fetch_prices.py",       "Fetch per-ticker price history via yfinance (slow)"),
    ("05_run_backtest.py",       "Run PEAD backtest"),
    ("06_plot_results.py",       "Plot results and print summary stats"),
]


def run_step(script: str, description: str, step_num: int, total: int) -> None:
    print()
    print(f"{'─' * 60}")
    print(f"  Step {step_num}/{total}: {description}")
    print(f"  Script: src/{script}")
    print(f"{'─' * 60}")

    t0 = time.time()
    result = subprocess.run(
        [sys.executable, str(SRC_DIR / script)],
        cwd=SRC_DIR.parent,  # run from project root so relative paths resolve
    )
    elapsed = time.time() - t0

    if result.returncode != 0:
        print(f"\n  ERROR: {script} exited with code {result.returncode}. Stopping.")
        sys.exit(result.returncode)

    print(f"\n  Completed in {elapsed:.1f}s")


def main():
    print("PEAD Backtest — Full Pipeline")
    print(f"Scripts directory: {SRC_DIR}")

    total = len(STEPS)
    pipeline_start = time.time()

    for i, (script, description) in enumerate(STEPS, start=1):
        path = SRC_DIR / script
        if not path.exists():
            print(f"\nERROR: {path} not found. Has the script been created?")
            sys.exit(1)
        run_step(script, description, i, total)

    total_elapsed = time.time() - pipeline_start
    print()
    print(f"{'=' * 60}")
    print(f"  Pipeline complete in {total_elapsed / 60:.1f} minutes.")
    print(f"  Chart: output/pead_returns_vs_sp500.png")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

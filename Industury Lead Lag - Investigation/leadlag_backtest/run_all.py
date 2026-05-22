"""
Run the full lead-lag backtest pipeline end-to-end.

Executes scripts 01–05 in order. Each script is idempotent — already-cached
data is skipped automatically, so re-running this is safe.

Usage:
    python run_all.py

To re-run a single step from scratch, delete the relevant cache file in data/
then run this again. See LEADLAG_BACKTEST_SPEC.md for which file each script writes.
"""

import subprocess
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"

STEPS = [
    ("01_fetch_earnings_triggers.py", "Fetch earnings for all 33 anchor tickers across 4 sectors"),
    ("02_build_universe.py",          "Build small-cap universes for 4 sectors (screener + peers)"),
    ("03_fetch_prices.py",            "Fetch price history via yfinance + apply liquidity filter (slow)"),
    ("04_run_backtest.py",            "Run lead-lag backtest across all 4 sectors + 12 parameter combos"),
    ("05_plot_results.py",            "Plot two-panel chart (vs SPY + excess return) and heatmap"),
]


def run_step(script: str, description: str, step_num: int, total: int) -> None:
    print()
    print(f"{'─' * 62}")
    print(f"  Step {step_num}/{total}: {description}")
    print(f"  Script: src/{script}")
    print(f"{'─' * 62}")

    t0     = time.time()
    result = subprocess.run(
        [sys.executable, str(SRC_DIR / script)],
        cwd=SRC_DIR.parent,
    )
    elapsed = time.time() - t0

    if result.returncode != 0:
        print(f"\n  ERROR: {script} exited with code {result.returncode}. Stopping.")
        sys.exit(result.returncode)

    print(f"\n  Completed in {elapsed:.1f}s")


def main():
    print("Lead-Lag Backtest — Full Pipeline")
    print(f"Scripts directory: {SRC_DIR}")

    total          = len(STEPS)
    pipeline_start = time.time()

    for i, (script, description) in enumerate(STEPS, start=1):
        path = SRC_DIR / script
        if not path.exists():
            print(f"\nERROR: {path} not found.")
            sys.exit(1)
        run_step(script, description, i, total)

    total_elapsed = time.time() - pipeline_start
    print()
    print(f"{'=' * 62}")
    print(f"  Pipeline complete in {total_elapsed / 60:.1f} minutes.")
    print(f"  Charts: output/leadlag_returns_vs_spy.png")
    print(f"          output/parameter_sweep_heatmap.png")
    print(f"{'=' * 62}")


if __name__ == "__main__":
    main()

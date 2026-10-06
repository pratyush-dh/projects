#!/usr/bin/env python3
"""Build a PRISM annual-precipitation dataset for pulse.html from the command line.

    python build_rain_years.py                    # 1991-2020 (downloads missing years)
    python build_rain_years.py --years 2000 2023

Output goes to pulse_data/prism-<start>-<end>/. For your own rasters, use the
Data dialog in pulse.html (needs `python serve.py`), or call
rain_engine.build_dataset() directly.
"""
import argparse

import rain_engine as eng


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--years", type=int, nargs=2, default=[1991, 2020], metavar=("START", "END"))
    args = ap.parse_args()
    meta = eng.build_prism(*args.years, progress=lambda p, m: print(f"{p:4.0%} {m}"))
    print(f"wrote pulse_data/{meta['id']}: {len(meta['years'])} periods, "
          f"{meta['rows']}x{meta['cols']} cells, decimate {meta['decimate']}")


if __name__ == "__main__":
    try:
        main()
    except eng.EngineError as e:
        raise SystemExit(f"error: {e}")

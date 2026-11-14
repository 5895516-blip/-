#!/usr/bin/env python3
"""Reads `xcrun simctl list devices available -j` from stdin and prints the UDID of a recent iPhone."""
import json
import sys

PREFERRED = ["iPhone 17 Pro", "iPhone 17", "iPhone 16 Pro", "iPhone 16", "iPhone 15 Pro", "iPhone 15"]


def runtime_version(runtime: str):
    # com.apple.CoreSimulator.SimRuntime.iOS-26-5 -> (26, 5)
    tail = runtime.rsplit("iOS-", 1)[-1]
    return tuple(int(part) for part in tail.split("-") if part.isdigit())


def main() -> None:
    devices = json.load(sys.stdin)["devices"]
    candidates = []
    for runtime, entries in devices.items():
        if "iOS" not in runtime:
            continue
        for entry in entries:
            name = entry.get("name", "")
            if not name.startswith("iPhone") or not entry.get("isAvailable", True):
                continue
            rank = PREFERRED.index(name) if name in PREFERRED else len(PREFERRED)
            candidates.append((runtime_version(runtime), -rank, entry["udid"]))
    if not candidates:
        sys.exit("no iPhone simulator found")
    print(max(candidates)[2])


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Test runner for LilyGO 433MHz Weather Gateway.
Discovers and executes all unit tests and live device integration tests.
Usage:
    python3 tests/run_tests.py
    or via nix-shell:
    nix-shell --run test
"""

import http.server
import os
import sys
import threading
import time
import unittest
import urllib.request


def is_url_reachable(url: str, timeout: float = 1.0) -> bool:
    try:
        req = urllib.request.Request(f"{url}/json", headers={"User-Agent": "LilyGOTest/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def main():
    print("\n" + "=" * 60)
    print(" LilyGO 433MHz Weather Gateway — Automated Test Suite")
    print("=" * 60)

    target_url = os.environ.get("BOARD_URL", "http://192.168.1.50")
    mock_server = None
    mock_thread = None

    if is_url_reachable(target_url, timeout=1.5):
        print(f" Target: LIVE HARDWARE at {target_url}\n")
    else:
        print(f" Target: {target_url} not reachable.")
        print(" Starting built-in Mock Simulator on http://127.0.0.1:8080...\n")
        from mock_server import GatewayMockHandler
        mock_server = http.server.HTTPServer(("127.0.0.1", 8080), GatewayMockHandler)
        mock_thread = threading.Thread(target=mock_server.serve_forever, daemon=True)
        mock_thread.start()
        time.sleep(0.3)
        os.environ["BOARD_URL"] = "http://127.0.0.1:8080"

    try:
        # Determine tests directory
        tests_dir = os.path.dirname(os.path.abspath(__file__))

        # Discover and load all test files in tests/
        loader = unittest.TestLoader()
        suite = loader.discover(start_dir=tests_dir, pattern="test_*.py")

        # Run tests with verbose output
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)

        print("\n" + "-" * 60)
        print(f"Tests run: {result.testsRun}")
        print(f"Errors: {len(result.errors)}")
        print(f"Failures: {len(result.failures)}")
        print(f"Skipped: {len(result.skipped)}")
        print("-" * 60)

        if result.wasSuccessful():
            print(" [SUCCESS] All tests passed cleanly!\n")
            sys.exit(0)
        else:
            print(" [FAILURE] Some tests failed.\n")
            sys.exit(1)
    finally:
        if mock_server:
            mock_server.shutdown()
            mock_server.server_close()


if __name__ == "__main__":
    main()

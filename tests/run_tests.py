#!/usr/bin/env python3
"""
Test runner for LilyGO 433MHz Weather Gateway.
Discovers and executes all unit tests and live device integration tests.
Usage:
    python3 tests/run_tests.py
    or via nix-shell:
    nix-shell --run test
"""

import os
import sys
import unittest


def main():
    print("\n" + "=" * 60)
    print(" LilyGO 433MHz Weather Gateway — Automated Test Suite")
    print("=" * 60)

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


if __name__ == "__main__":
    main()

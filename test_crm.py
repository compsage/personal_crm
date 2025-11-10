#!/usr/bin/env python3
"""
Quick test script to populate the CRM database with sample data from driver.json
"""

import sys
import json
import time
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from crm import process_request, view_all_data

# Load test inputs from driver.json
def load_test_inputs(limit=None):
    """Load user inputs from driver.json"""
    driver_path = Path(__file__).parent / "driver.json"
    with open(driver_path, "r") as f:
        data = json.load(f)

    inputs = [test["request"]["user_input"] for test in data["tests"]]

    if limit:
        return inputs[:limit]
    return inputs


def run_tests(inputs):
    print("="*60)
    print(f"Building CRM Database with {len(inputs)} Test Inputs")
    print("="*60)

    success_count = 0
    error_count = 0

    for i, user_input in enumerate(inputs, 1):
        # Wait 5 seconds between calls to avoid rate limiting
        if i > 1:
            print(f"\n⏳ Waiting 5 seconds to avoid rate limiting...")
            time.sleep(5)

        print(f"\n{'='*60}")
        print(f"Test {i}/{len(inputs)}")
        print(f"{'='*60}")
        print(f"Input: {user_input}")

        try:
            # Auto-confirm all operations in test mode
            # Returns 'y' for confirmations and '1' for disambiguation choices
            def mock_input(prompt):
                if 'Proceed with' in prompt or 'Y/n' in prompt:
                    return 'y'
                elif 'select an option' in prompt.lower():
                    return '1'
                return 'y'

            with patch('builtins.input', side_effect=mock_input):
                result = process_request(user_input)

            if result:
                print("✓ Success")
                success_count += 1
            else:
                print("⚠ Skipped/Ambiguous")
                error_count += 1
        except Exception as e:
            print(f"✗ Error: {e}")
            error_count += 1
            import traceback
            traceback.print_exc()

    print("\n\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total tests: {len(inputs)}")
    print(f"Successful: {success_count}")
    print(f"Errors/Skipped: {error_count}")
    print("="*60)

    print("\n\n" + "="*60)
    print("FINAL DATABASE STATE")
    print("="*60)
    view_all_data()

if __name__ == "__main__":
    # Check for command line argument for limit
    limit = 10  # default
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            print("Usage: python test_crm.py [limit]")
            print("  limit: number of tests to run (default: 10, use -1 for all)")
            sys.exit(1)

    # Load inputs with limit (-1 means all)
    if limit == -1:
        test_inputs = load_test_inputs(limit=None)
    elif limit > 0:
        test_inputs = load_test_inputs(limit=limit)
    else:
        print("Error: limit must be positive or -1 for all")
        sys.exit(1)

    print(f"Loading {len(test_inputs)} test inputs from driver.json\n")

    run_tests(test_inputs)

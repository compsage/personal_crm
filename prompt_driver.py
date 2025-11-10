#!/usr/bin/env python3
"""
Harness to run the entity extraction prompt against a suite of use cases.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from test_prompt import extract_entities


def load_tests(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text())
    tests = data.get("tests")
    if not tests:
        raise ValueError(f"No tests found in {path}")
    return tests


def split_path(path: str) -> List[Any]:
    tokens: List[Any] = []
    buffer = ""
    i = 0
    while i < len(path):
        char = path[i]
        if char == ".":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            i += 1
            continue
        if char == "[":
            if buffer:
                tokens.append(buffer)
                buffer = ""
            end = path.find("]", i)
            if end == -1:
                raise ValueError(f"Unclosed bracket in path '{path}'")
            idx = path[i + 1 : end]
            if not idx.isdigit():
                raise ValueError(f"Non-numeric index in path '{path}'")
            tokens.append(int(idx))
            i = end + 1
            continue
        buffer += char
        i += 1
    if buffer:
        tokens.append(buffer)
    return tokens


def get_value(data: Any, path: str) -> Any:
    current = data
    for token in split_path(path):
        try:
            if isinstance(token, int):
                current = current[token]
            else:
                current = current[token]
        except (KeyError, IndexError, TypeError) as exc:
            raise KeyError(f"Path '{path}' not found") from exc
    return current


def evaluate_expectation(expectation: Dict[str, Any], response: Dict[str, Any]) -> Tuple[bool, str]:
    path = expectation["path"]
    comparator = None
    for key in ("equals", "contains", "exists"):
        if key in expectation:
            comparator = key
            break
    if comparator is None:
        raise ValueError(f"Expectation missing comparator: {expectation}")

    try:
        actual = get_value(response, path)
    except KeyError as exc:
        if comparator == "exists" and not expectation.get("exists"):
            return True, f"{path} not present as expected"
        return False, str(exc)

    if comparator == "equals":
        expected = expectation["equals"]
        passed = actual == expected
        return passed, f"{path} equals '{actual}' (expected '{expected}')"

    if comparator == "contains":
        expected = expectation["contains"]
        if isinstance(actual, str):
            passed = expected.lower() in actual.lower()
        elif isinstance(actual, Iterable):
            passed = expected in actual
        else:
            passed = False
        return passed, f\"{path} contains '{expected}' within '{actual}'\"

    if comparator == "exists":
        should_exist = expectation["exists"]
        passed = bool(actual) if should_exist else actual is None
        return passed, f"{path} exists check ({'present' if should_exist else 'absent'})"

    raise ValueError(f"Unsupported comparator {comparator}")


def slugify(name: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in name).strip("_")


def run_harness(args: argparse.Namespace) -> int:
    driver_path = Path(args.driver)
    tests = load_tests(driver_path)
    save_dir = Path(args.save_responses) if args.save_responses else None
    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)

    total = len(tests)
    failed = 0

    for idx, test in enumerate(tests, start=1):
        name = test["name"]
        print(f"[{idx}/{total}] {name}")
        request = test["request"]
        response = extract_entities(
            request["user_input"],
            request.get("command_type", "ADD_NEW"),
            request.get("context"),
        )

        if save_dir:
            out_path = save_dir / f"{idx:02d}_{slugify(name)}.json"
            out_path.write_text(json.dumps(response, indent=2))

        expectations = test.get("expectations", [])
        test_passed = True
        for expectation in expectations:
            passed, message = evaluate_expectation(expectation, response)
            status = "PASS" if passed else "FAIL"
            print(f"  - {status}: {message}")
            if not passed:
                test_passed = False

        if not expectations:
            print("  (no expectations defined)")

        if not test_passed:
            failed += 1
            if args.fail_fast:
                print("Stopping early due to failure.")
                break

    print("\nSummary")
    print("-------")
    print(f"Total tests: {total}")
    print(f"Passed: {total - failed}")
    print(f"Failed: {failed}")

    return 0 if failed == 0 else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run driver tests for the entity extraction prompt.")
    parser.add_argument(
        "--driver",
        type=str,
        default="driver.json",
        help="Path to the driver/use-case JSON file.",
    )
    parser.add_argument(
        "--save-responses",
        type=str,
        help="Optional directory to store raw model responses.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failing test.",
    )
    return parser.parse_args()


def main() -> None:
    sys.exit(run_harness(parse_args()))


if __name__ == "__main__":
    main()

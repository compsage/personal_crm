#!/usr/bin/env python3
"""
Simple test script for the CRM API.
"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_endpoint(name, method, url, **kwargs):
    """Test an API endpoint."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    print(f"{method} {url}")

    try:
        if method == "GET":
            response = requests.get(url, **kwargs)
        elif method == "POST":
            response = requests.post(url, **kwargs)

        print(f"Status: {response.status_code}")
        print(f"Response:")
        print(json.dumps(response.json(), indent=2))
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    print("="*60)
    print("Personal CRM API Test Suite")
    print("="*60)

    # Test 1: Health check
    test_endpoint(
        "Health Check",
        "GET",
        f"{BASE_URL}/health"
    )

    # Test 2: Root endpoint
    test_endpoint(
        "Root Endpoint",
        "GET",
        f"{BASE_URL}/"
    )

    # Test 3: Add a person
    print("\n⏳ Adding person (this may take a few seconds due to LLM processing)...")
    result = test_endpoint(
        "Add Person (CREATE)",
        "POST",
        f"{BASE_URL}/process",
        json={"text": "Met Alice at a tech conference, she's a software engineer at Google"}
    )

    # Test 4: Get all people
    test_endpoint(
        "Get All People",
        "GET",
        f"{BASE_URL}/people"
    )

    # Test 5: Get stats
    test_endpoint(
        "Get Stats",
        "GET",
        f"{BASE_URL}/stats"
    )

    # Test 6: Search
    test_endpoint(
        "Search People",
        "GET",
        f"{BASE_URL}/people/search",
        params={"q": "engineer"}
    )

    # Test 7: Get specific person (if we have one)
    if result and result.get("data") and "people" in result["data"]:
        people = result["data"]["people"]
        if people:
            person_id = people[0]["id"]
            test_endpoint(
                "Get Specific Person",
                "GET",
                f"{BASE_URL}/people/{person_id}"
            )

    print("\n" + "="*60)
    print("✅ API Test Suite Complete!")
    print("="*60)
    print(f"\n📖 Full API docs: http://localhost:8000/docs")

if __name__ == "__main__":
    main()

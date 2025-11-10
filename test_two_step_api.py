#!/usr/bin/env python3
"""
Test script for the 2-step API workflow:
1. POST /analyze - Get the plan
2. POST /execute - Execute the plan
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def analyze(text: str):
    """Step 1: Analyze what would be done."""
    print(f"\n{'='*60}")
    print(f"STEP 1: Analyzing - '{text}'")
    print(f"{'='*60}")

    response = requests.post(
        f"{BASE_URL}/analyze",
        json={"text": text}
    )

    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"\nOperation: {result['operation']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Reasoning: {result['reasoning']}")
    print(f"Summary: {result['summary']}")
    print(f"\nExtraction:")
    print(json.dumps(result['extraction'], indent=2))

    return result

def execute(operation: str, extraction: dict):
    """Step 2: Execute the plan."""
    print(f"\n{'='*60}")
    print(f"STEP 2: Executing {operation} operation")
    print(f"{'='*60}")

    response = requests.post(
        f"{BASE_URL}/execute",
        json={
            "operation": operation,
            "extraction": extraction
        }
    )

    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"\nSuccess: {result['success']}")
    print(f"Message: {result['message']}")

    return result

def main():
    print("="*60)
    print("Personal CRM API - 2-Step Workflow Test")
    print("="*60)

    # Example 1: CREATE
    print("\n\n📝 Example 1: Creating a new person")
    text = "Met Alice at a tech conference, she's a software engineer at Google"

    # Step 1: Analyze
    analysis = analyze(text)

    # User can review the analysis here
    print("\n⏸️  [In production, user would review and approve here]")
    input("Press Enter to execute...")

    # Step 2: Execute
    result = execute(analysis['operation'], analysis['extraction'])
    print(f"\n✅ Created person!")

    # Example 2: READ
    print("\n\n📖 Example 2: Reading information")
    text = "What do I know about Alice?"

    # Step 1: Analyze
    analysis = analyze(text)

    # Step 2: Execute (no confirmation needed for READ)
    result = execute(analysis['operation'], analysis['extraction'])

    if result.get('data') and result['data'].get('results'):
        person = result['data']['results'][0]
        print(f"\n👤 Found: {person['name']}")
        print(f"   Occupation: {person['metadata'].get('occupation', 'N/A')}")
        print(f"   Facts: {len(person['facts'])}")

    print("\n" + "="*60)
    print("✅ 2-Step Workflow Complete!")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to server.")
        print("Make sure the server is running: uvicorn server:app --reload")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

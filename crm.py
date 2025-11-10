#!/usr/bin/env python3
"""
Multi-step Personal CRM with Pydantic validation.
Type-safe CRUD operations with automatic data validation.
"""

import os
import json
import hashlib
import logging
import time
from pathlib import Path
from openai import OpenAI
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import ValidationError

# Import Pydantic models
from models import (
    Database, Person, Fact, FactType, Metadata, SocialMedia,
    RouterResponse, ClarificationOption, CRUDOperation,
    CreateExtraction, UpdateExtraction, ReadExtraction, DeleteExtraction
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('crm.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get provider configuration
provider = os.getenv("LLM_PROVIDER", "groq").lower()

# Initialize LLM client based on provider
if provider == "groq":
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    logger.info(f"🚀 Initialized Groq provider with model: {model}")
    print(f"Using Groq LLM provider with model: {model}")
else:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-4")
    logger.info(f"🚀 Initialized OpenAI provider with model: {model}")
    print(f"Using OpenAI provider with model: {model}")

# Paths
DATA_FILE = Path(__file__).parent / "data.json"
ROUTER_PROMPT = Path(__file__).parent / "prompt_router.md"
CRUD_PROMPT = Path(__file__).parent / "prompt_crud.md"


def load_data() -> Database:
    """Load existing data from file with validation, or return empty structure."""
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r") as f:
                db = Database.model_validate_json(f.read())
            logger.info(f"📂 Loaded data: {len(db.people)} people")
            return db
        except ValidationError as e:
            logger.error(f"❌ Data validation failed: {e}")
            logger.error("Creating backup and starting fresh...")
            # Backup corrupted file
            backup_path = DATA_FILE.with_suffix('.backup.json')
            DATA_FILE.rename(backup_path)
            logger.info(f"Backed up corrupted data to {backup_path}")
            return Database()
    logger.info("📂 No existing data file, starting fresh")
    return Database()


def generate_person_hash(person: Person) -> str:
    """
    Generate a hash ID for a person based on their data.

    Args:
        person: Person object

    Returns:
        SHA256 hash string
    """
    # Create hashable data (exclude hash_id and timestamps)
    hashable_data = {
        "id": person.id,
        "name": person.name,
        "metadata": person.metadata.model_dump(exclude_none=True),
        "facts": [
            {
                "content": f.content,
                "type": f.type if isinstance(f.type, str) else f.type.value
            } for f in person.facts
        ],
        "tags": sorted(person.tags)  # Sort for consistency
    }

    # Convert to JSON string (sorted keys for consistency)
    json_str = json.dumps(hashable_data, sort_keys=True)

    # Generate SHA256 hash
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]  # First 16 chars


def add_hash_ids(db: Database) -> Database:
    """Add hash_id to each person in the database."""
    for person in db.people:
        person.hash_id = generate_person_hash(person)
    return db


def save_data(db: Database):
    """Save data to file with Pydantic serialization."""
    with open(DATA_FILE, "w") as f:
        f.write(db.model_dump_json(indent=2, exclude_none=True))
    logger.info(f"💾 Saved data: {len(db.people)} people to {DATA_FILE}")


def call_llm(prompt_file: Path, request_data: Dict[str, Any]) -> dict:
    """Generic LLM call helper."""
    start_time = time.time()
    prompt_name = prompt_file.stem

    logger.info(f"🤖 Calling LLM with {prompt_name} prompt...")

    with open(prompt_file, "r") as f:
        system_prompt = f.read()

    # Convert Pydantic models to dict for JSON serialization
    if isinstance(request_data.get("existing_data"), Database):
        request_data = {
            **request_data,
            "existing_data": json.loads(request_data["existing_data"].model_dump_json())
        }

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(request_data, indent=2)}
        ],
        response_format={"type": "json_object"}
    )

    elapsed = time.time() - start_time
    result = json.loads(response.choices[0].message.content)

    logger.info(f"✅ LLM response received in {elapsed:.2f}s from {prompt_name}")

    return result


def route_request(user_input: str, db: Database) -> RouterResponse:
    """
    Step 1: Determine which CRUD operation is needed.

    Returns:
        RouterResponse with operation, target_person_id, confidence, reasoning, etc.
    """
    print("\n[Step 1/2] Routing request...")

    request_data = {
        "user_input": user_input,
        "existing_data": db
    }

    routing_result = call_llm(ROUTER_PROMPT, request_data)

    # Validate with Pydantic
    try:
        router_response = RouterResponse.model_validate(routing_result)
    except ValidationError as e:
        logger.error(f"❌ Router response validation failed: {e}")
        raise

    print(f"  Operation: {router_response.operation.value}")
    print(f"  Confidence: {router_response.confidence:.2f}")
    print(f"  Reasoning: {router_response.reasoning}")

    if router_response.needs_clarification:
        print(f"\n  ⚠ Need Clarification:")
        if router_response.clarification_question:
            print(f"     {router_response.clarification_question}")

        # Display options if available
        options = router_response.clarification_options or []
        if options:
            print(f"\n     Options:")
            for i, option in enumerate(options, 1):
                print(f"       {i}. {option.person_name} - {option.distinguishing_details}")

    return router_response


def generate_person_id(name: str, existing_people: list[Person]) -> str:
    """Generate unique person ID."""
    # Clean name for ID
    clean_name = name.replace(" ", "_")
    base_id = f"person_{clean_name}"

    # Find next available number
    existing_ids = [p.id for p in existing_people]
    counter = 1
    while f"{base_id}_{counter:03d}" in existing_ids:
        counter += 1

    return f"{base_id}_{counter:03d}"


def execute_create(extraction: CreateExtraction, current_timestamp: datetime) -> Database:
    """
    Execute CREATE operation with Pydantic models.

    Args:
        extraction: Validated extraction with person data
        current_timestamp: Current timestamp

    Returns:
        Updated database
    """
    person_data = extraction.person
    logger.info(f"➕ Creating new person: {person_data.name}")

    # Load existing data
    db = load_data()
    person_id = generate_person_id(person_data.name, db.people)
    logger.info(f"  Generated ID: {person_id}")

    # Create facts with timestamps
    facts = [
        Fact(
            content=fact["content"],
            type=FactType(fact["type"]),
            timestamp=current_timestamp
        )
        for fact in person_data.facts
    ]

    # Build complete person record with validation
    new_person = Person(
        id=person_id,
        name=person_data.name,
        metadata=person_data.metadata,
        facts=facts,
        tags=person_data.tags,
        created_at=current_timestamp,
        last_updated=current_timestamp
    )

    # Add to database
    db.people.append(new_person)
    logger.info(f"  Added {len(facts)} facts with {len(person_data.tags)} tags")

    return db


def execute_update(extraction: UpdateExtraction, current_timestamp: datetime) -> Database:
    """
    Execute UPDATE operation with Pydantic models.

    Args:
        extraction: Validated extraction with updates
        current_timestamp: Current timestamp

    Returns:
        Updated database
    """
    person_id = extraction.person_id
    updates = extraction.updates
    logger.info(f"✏️  Updating person: {person_id}")

    # Load existing data
    db = load_data()

    # Find person
    person = db.find_by_id(person_id)
    if not person:
        logger.error(f"❌ Person {person_id} not found")
        raise ValueError(f"Person {person_id} not found")

    # Update metadata (merge, don't replace)
    if updates.metadata:
        for key, value in updates.metadata.items():
            if isinstance(value, dict):
                # Nested dict (like social_media)
                current_value = getattr(person.metadata, key, None)
                if isinstance(current_value, dict):
                    current_value.update(value)
                else:
                    setattr(person.metadata, key, value)
            else:
                setattr(person.metadata, key, value)

    # Add new facts with timestamps
    new_fact_count = 0
    if updates.new_facts:
        for fact_data in updates.new_facts:
            person.facts.append(Fact(
                content=fact_data["content"],
                type=FactType(fact_data["type"]),
                timestamp=current_timestamp
            ))
            new_fact_count += 1

    # Add new tags
    new_tag_count = 0
    if updates.new_tags:
        for tag in updates.new_tags:
            if tag not in person.tags:
                person.tags.append(tag)
                new_tag_count += 1

    # Update timestamp
    person.last_updated = current_timestamp

    logger.info(f"  Updated: {new_fact_count} new facts, {new_tag_count} new tags")

    return db


def execute_read(extraction: ReadExtraction) -> Dict[str, Any]:
    """
    Execute READ operation with Pydantic models.

    Args:
        extraction: Validated extraction with query info

    Returns:
        Query results
    """
    query = extraction.query
    logger.info(f"🔍 Reading data: {extraction.summary}")

    db = load_data()

    results = []

    if query.person_id:
        # Find specific person
        person = db.find_by_id(query.person_id)
        if person:
            results.append(person)
            logger.info(f"  Found person: {person.name}")
    elif query.search_criteria:
        # TODO: Implement search logic
        logger.info("  Search criteria not yet implemented")
        pass

    logger.info(f"  Returning {len(results)} result(s)")
    return {"operation": "READ", "results": results, "summary": extraction.summary}


def execute_delete(extraction: DeleteExtraction) -> Database:
    """
    Execute DELETE operation with Pydantic models.

    Args:
        extraction: Validated extraction with person_id to delete

    Returns:
        Updated database
    """
    person_id = extraction.person_id
    logger.info(f"🗑️  Deleting person: {person_id}")

    db = load_data()

    # Find person name before deleting
    person = db.find_by_id(person_id)
    person_name = person.name if person else "Unknown"

    # Remove person using database method
    deleted = db.delete_by_id(person_id)

    if deleted:
        logger.info(f"  Deleted: {person_name} ({person_id})")
    else:
        logger.warning(f"  Person {person_id} not found for deletion")

    return db


def execute_operation(routing_result: RouterResponse, user_input: str, db: Database) -> Optional[Dict[str, Any]]:
    """
    Step 2: Extract data from LLM, then execute CRUD operation with Python.

    Returns:
        Updated data or read results
    """
    print(f"\n[Step 2/2] Executing {routing_result.operation.value} operation...")

    # Step 2a: Get extraction from LLM
    request_data = {
        "operation": routing_result.operation.value,
        "user_input": user_input,
        "target_person_id": routing_result.target_person_id,
        "existing_data": db
    }

    extraction_dict = call_llm(CRUD_PROMPT, request_data)
    print(f"  ✓ Extracted: {extraction_dict.get('summary', 'Done')}")

    # Show what will be changed
    print(f"\n  📋 Extracted data:")
    for line in json.dumps(extraction_dict, indent=2).split('\n'):
        print(f"     {line}")

    # Step 2b: Verify before executing (skip for READ)
    operation = routing_result.operation
    if operation != CRUDOperation.READ:
        confirm = input(f"\n  ❓ Proceed with {operation.value}? (Y/n): ").strip().lower()
        if confirm == 'n' or confirm == 'no':
            print("  ✗ Operation cancelled")
            return None

    # Step 2c: Validate extraction and execute with Python
    current_timestamp = datetime.now(timezone.utc)

    try:
        if operation == CRUDOperation.CREATE:
            extraction = CreateExtraction.model_validate(extraction_dict)
            result_db = execute_create(extraction, current_timestamp)
            return {"people": result_db.people, "summary": extraction.summary}

        elif operation == CRUDOperation.UPDATE:
            extraction = UpdateExtraction.model_validate(extraction_dict)
            result_db = execute_update(extraction, current_timestamp)
            return {"people": result_db.people, "summary": extraction.summary}

        elif operation == CRUDOperation.READ:
            extraction = ReadExtraction.model_validate(extraction_dict)
            return execute_read(extraction)

        elif operation == CRUDOperation.DELETE:
            extraction = DeleteExtraction.model_validate(extraction_dict)
            result_db = execute_delete(extraction)
            return {"people": result_db.people, "summary": extraction.summary}

        else:
            raise ValueError(f"Unknown operation: {operation}")

    except ValidationError as e:
        logger.error(f"❌ Extraction validation failed: {e}")
        print(f"\n  ✗ Invalid data format from LLM: {e}")
        return None


def process_request(user_input: str) -> Optional[Dict[str, Any]]:
    """
    Main processing pipeline:
    1. Route to determine operation
    2. Execute operation
    3. Save or display results
    """
    start_time = time.time()
    logger.info(f"🎯 Processing request: {user_input[:50]}{'...' if len(user_input) > 50 else ''}")

    # Load current data
    db = load_data()

    # Step 1: Route
    routing_result = route_request(user_input, db)

    # Check for ambiguity
    if routing_result.needs_clarification:
        logger.info("⚠️  Request needs clarification")
        options = routing_result.clarification_options or []

        if options:
            # Let user choose
            print("\n  Please select an option (1-{}) or 'cancel':".format(len(options)))
            choice = input("  > ").strip()

            if choice.lower() == 'cancel':
                logger.info("❌ Request cancelled by user")
                print("\n  ⚠ Cancelled.")
                return None

            try:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(options):
                    # Update routing result with selected person
                    routing_result.target_person_id = options[choice_idx].person_id
                    routing_result.needs_clarification = False
                    routing_result.confidence = 0.95  # User confirmed
                    print(f"\n  ✓ Selected: {options[choice_idx].person_name}")
                else:
                    print("\n  ⚠ Invalid option. Cancelled.")
                    return None
            except ValueError:
                print("\n  ⚠ Invalid input. Cancelled.")
                return None
        else:
            print("\n  ⚠ Need clarification but no options provided.")
            return None

    # Step 2: Execute
    result = execute_operation(routing_result, user_input, db)

    if result is None:
        elapsed = time.time() - start_time
        logger.info(f"❌ Request cancelled after {elapsed:.2f}s")
        return None

    # Handle based on operation
    if routing_result.operation == CRUDOperation.READ:
        # Display results
        display_results(result.get("results", []))
        elapsed = time.time() - start_time
        logger.info(f"✅ Request completed in {elapsed:.2f}s (READ operation)")
        return result

    else:
        # Save updated data (CREATE, UPDATE, DELETE)
        # Create Database object from results
        updated_db = Database(people=result["people"])

        # Add hash_id to each person before saving
        updated_db = add_hash_ids(updated_db)
        save_data(updated_db)
        print(f"\n✓ Data saved to {DATA_FILE}")
        elapsed = time.time() - start_time
        logger.info(f"✅ Request completed in {elapsed:.2f}s ({routing_result.operation.value} operation)")
        return result


def display_results(results: list[Person]):
    """Display READ operation results in a nice format."""
    if not results:
        print("\n  No results found.")
        return

    print(f"\n{'='*60}")
    print(f"RESULTS ({len(results)} person/people)")
    print(f"{'='*60}\n")

    for person in results:
        print(f"┌─ {person.name} ({person.id})")
        print(f"│  Hash: {person.hash_id or 'N/A'}")
        print(f"│  Created: {person.created_at.isoformat()}")
        print(f"│  Updated: {person.last_updated.isoformat()}")
        print(f"│  Tags: {', '.join(person.tags)}")

        # Metadata
        meta = person.metadata
        if meta.phone:
            print(f"│  📞 {meta.phone}")
        if meta.email:
            print(f"│  📧 {meta.email}")
        if meta.occupation:
            print(f"│  💼 {meta.occupation}")
        if meta.location:
            print(f"│  📍 {meta.location}")

        # Social media
        social = meta.social_media
        social_list = []
        if social.twitter:
            social_list.append(f"twitter: {social.twitter}")
        if social.instagram:
            social_list.append(f"instagram: {social.instagram}")
        if social.linkedin:
            social_list.append(f"linkedin: {social.linkedin}")
        if social_list:
            print(f"│  🔗 {', '.join(social_list)}")

        # Facts
        if person.facts:
            print(f"│  Facts ({len(person.facts)}):")
            for fact in person.facts:
                timestamp_str = fact.timestamp.isoformat()[:10]  # Just date
                fact_type = fact.type if isinstance(fact.type, str) else fact.type.value
                print(f"│    [{fact_type}] {fact.content} ({timestamp_str})")

        print(f"└─\n")


def view_all_data():
    """Display all people in the CRM."""
    db = load_data()

    if not db.people:
        print("\nNo people in database yet.")
        return

    display_results(db.people)


def reset_database():
    """Reset the database to empty state."""
    confirm = input("\n⚠️  Are you sure you want to delete all data? (yes/no): ").strip().lower()
    if confirm == 'yes':
        empty_db = Database()
        save_data(empty_db)
        print("✓ Database has been reset to empty state.")
    else:
        print("✗ Reset cancelled.")


def main():
    """Interactive CLI"""
    print("=" * 60)
    print("PERSONAL CRM - Multi-Step CRUD System with Pydantic")
    print("=" * 60)

    while True:
        print("\nOptions:")
        print("  1. Add/update info (natural language)")
        print("  2. View all data")
        print("  3. Reset database (clear all data)")
        print("  4. Exit")

        choice = input("\nChoice: ").strip()

        if choice == "1":
            print("\nEnter your request (or 'back' to return):")
            print("Examples:")
            print("  - Met Sarah at yoga, she's a teacher")
            print("  - What do I know about Sarah?")
            print("  - Sarah's birthday is May 15")
            print("  - Remove John from contacts")
            user_input = input("\n> ").strip()

            if user_input.lower() == 'back':
                continue

            if user_input:
                try:
                    process_request(user_input)
                except Exception as e:
                    print(f"\n❌ Error: {e}")
                    import traceback
                    traceback.print_exc()

        elif choice == "2":
            view_all_data()

        elif choice == "3":
            reset_database()

        elif choice == "4":
            print("\nGoodbye!")
            break

        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()

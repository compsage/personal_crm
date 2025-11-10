#!/usr/bin/env python3
"""
FastAPI server for Personal CRM.
Simple REST API for natural language CRM operations.
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import logging

# Import CRM functions
from crm import (
    load_data, save_data, route_request, call_llm, add_hash_ids,
    execute_create, execute_update, execute_read, execute_delete,
    CRUD_PROMPT
)
from models import (
    Database, Person, CRUDOperation,
    CreateExtraction, UpdateExtraction, ReadExtraction, DeleteExtraction
)
from pydantic import ValidationError as PydanticValidationError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Personal CRM API",
    description="Natural language CRM with intelligent CRUD operations",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class AnalyzeRequest(BaseModel):
    """Request body for analyzing natural language input."""
    text: str = Field(..., min_length=1, description="Natural language input")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Met Sarah at yoga, she's a teacher and loves coffee"
            }
        }


class AnalyzeResponse(BaseModel):
    """Response from analyzing natural language input (before execution)."""
    operation: str
    confidence: float
    reasoning: str
    needs_clarification: bool
    clarification_question: Optional[str] = None
    clarification_options: Optional[List[Dict[str, Any]]] = None
    extraction: Dict[str, Any]
    summary: str


class ExecuteRequest(BaseModel):
    """Request body for executing a pre-analyzed operation."""
    operation: str
    extraction: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "operation": "CREATE",
                "extraction": {
                    "operation": "CREATE",
                    "person": {
                        "name": "Sarah",
                        "metadata": {},
                        "facts": [],
                        "tags": []
                    },
                    "summary": "New person Sarah"
                }
            }
        }


class ExecuteResponse(BaseModel):
    """Response from executing an operation."""
    success: bool
    operation: str
    message: str
    data: Optional[Dict[str, Any]] = None


class PersonResponse(BaseModel):
    """Response model for person data."""
    id: str
    name: str
    hash_id: Optional[str] = None
    metadata: Dict[str, Any]
    facts: List[Dict[str, Any]]
    tags: List[str]
    created_at: str
    last_updated: str


class StatsResponse(BaseModel):
    """Database statistics."""
    total_people: int
    total_facts: int
    recent_additions: List[str]  # Names of recently added people


# Endpoints

@app.get("/", tags=["General"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Personal CRM API",
        "version": "2.0.0",
        "docs": "/docs",
        "workflow": "1. POST /analyze (get plan) → 2. POST /execute (run plan)",
        "endpoints": {
            "analyze": "POST /analyze - Analyze natural language (returns plan)",
            "execute": "POST /execute - Execute analyzed plan",
            "get_all_people": "GET /people - Get all people",
            "get_person": "GET /people/{person_id} - Get specific person",
            "search": "GET /people/search?q=query - Search people",
            "stats": "GET /stats - Database statistics",
            "health": "GET /health - Health check"
        }
    }


@app.get("/health", tags=["General"])
async def health_check():
    """Health check endpoint."""
    try:
        db = load_data()
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "database": {
                "accessible": True,
                "people_count": len(db.people)
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )


@app.post("/analyze", response_model=AnalyzeResponse, tags=["CRM Operations"])
async def analyze_text(request: AnalyzeRequest):
    """
    Analyze natural language input and return what operation would be performed.

    This is Step 1 of a 2-step process:
    1. POST /analyze - Returns the planned operation and extraction
    2. POST /execute - Executes the plan

    Supports all CRUD operations:
    - CREATE: "Met Sarah at yoga, she's a teacher"
    - READ: "What do I know about Sarah?"
    - UPDATE: "Sarah's email is sarah@example.com"
    - DELETE: "Remove John from contacts"

    Returns the routing decision and extraction WITHOUT executing.
    """
    try:
        logger.info(f"Analyzing request: {request.text[:50]}...")

        # Load current database
        db = load_data()

        # Step 1: Route the request
        routing_result = route_request(request.text, db)

        # Step 2: Get extraction from LLM
        request_data = {
            "operation": routing_result.operation.value,
            "user_input": request.text,
            "target_person_id": routing_result.target_person_id,
            "existing_data": db
        }

        extraction_dict = call_llm(CRUD_PROMPT, request_data)

        # Return the analysis (don't execute yet)
        return AnalyzeResponse(
            operation=routing_result.operation.value,
            confidence=routing_result.confidence,
            reasoning=routing_result.reasoning,
            needs_clarification=routing_result.needs_clarification,
            clarification_question=routing_result.clarification_question,
            clarification_options=[opt.model_dump() for opt in (routing_result.clarification_options or [])],
            extraction=extraction_dict,
            summary=extraction_dict.get("summary", "Operation ready to execute")
        )

    except Exception as e:
        logger.error(f"Error analyzing request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing request: {str(e)}"
        )


@app.post("/execute", response_model=ExecuteResponse, tags=["CRM Operations"])
async def execute_operation_endpoint(request: ExecuteRequest):
    """
    Execute a previously analyzed operation.

    This is Step 2 of a 2-step process:
    1. POST /analyze - Returns the planned operation and extraction
    2. POST /execute - Executes the plan

    Takes the extraction JSON from /analyze and executes the actual CRUD operation.
    """
    try:
        logger.info(f"Executing {request.operation} operation...")

        operation = CRUDOperation(request.operation)
        extraction_dict = request.extraction
        current_timestamp = datetime.now(timezone.utc)

        # Validate and execute based on operation type
        try:
            if operation == CRUDOperation.CREATE:
                extraction = CreateExtraction.model_validate(extraction_dict)
                result_db = execute_create(extraction, current_timestamp)
                # Add hash IDs and save
                result_db = add_hash_ids(result_db)
                save_data(result_db)

                return ExecuteResponse(
                    success=True,
                    operation="CREATE",
                    message=extraction.summary,
                    data={"people": [p.model_dump() for p in result_db.people], "summary": extraction.summary}
                )

            elif operation == CRUDOperation.UPDATE:
                extraction = UpdateExtraction.model_validate(extraction_dict)
                result_db = execute_update(extraction, current_timestamp)
                # Add hash IDs and save
                result_db = add_hash_ids(result_db)
                save_data(result_db)

                return ExecuteResponse(
                    success=True,
                    operation="UPDATE",
                    message=extraction.summary,
                    data={"people": [p.model_dump() for p in result_db.people], "summary": extraction.summary}
                )

            elif operation == CRUDOperation.READ:
                extraction = ReadExtraction.model_validate(extraction_dict)
                result = execute_read(extraction)

                return ExecuteResponse(
                    success=True,
                    operation="READ",
                    message=extraction.summary,
                    data=result
                )

            elif operation == CRUDOperation.DELETE:
                extraction = DeleteExtraction.model_validate(extraction_dict)
                result_db = execute_delete(extraction)
                # Add hash IDs and save
                result_db = add_hash_ids(result_db)
                save_data(result_db)

                return ExecuteResponse(
                    success=True,
                    operation="DELETE",
                    message=extraction.summary,
                    data={"people": [p.model_dump() for p in result_db.people], "summary": extraction.summary}
                )

            else:
                raise ValueError(f"Unknown operation: {operation}")

        except PydanticValidationError as e:
            logger.error(f"Extraction validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid extraction format: {str(e)}"
            )

    except Exception as e:
        logger.error(f"Error executing operation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing operation: {str(e)}"
        )


@app.get("/people", response_model=List[PersonResponse], tags=["People"])
async def get_all_people():
    """
    Get all people in the CRM database.

    Returns a list of all contacts with their full information.
    """
    try:
        db = load_data()

        # Convert Person objects to dict for response
        people_data = []
        for person in db.people:
            person_dict = person.model_dump()
            # Convert datetime objects to ISO strings
            person_dict["created_at"] = person.created_at.isoformat()
            person_dict["last_updated"] = person.last_updated.isoformat()
            # Convert facts
            person_dict["facts"] = [
                {
                    "content": f.content,
                    "type": f.type if isinstance(f.type, str) else f.type.value,
                    "timestamp": f.timestamp.isoformat()
                }
                for f in person.facts
            ]
            people_data.append(person_dict)

        return people_data

    except Exception as e:
        logger.error(f"Error fetching people: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching people: {str(e)}"
        )


@app.get("/people/{person_id}", response_model=PersonResponse, tags=["People"])
async def get_person(person_id: str):
    """
    Get a specific person by ID.

    Args:
        person_id: The person's unique ID (e.g., person_Sarah_001)
    """
    try:
        db = load_data()
        person = db.find_by_id(person_id)

        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Person with ID '{person_id}' not found"
            )

        # Convert to dict for response
        person_dict = person.model_dump()
        person_dict["created_at"] = person.created_at.isoformat()
        person_dict["last_updated"] = person.last_updated.isoformat()
        person_dict["facts"] = [
            {
                "content": f.content,
                "type": f.type if isinstance(f.type, str) else f.type.value,
                "timestamp": f.timestamp.isoformat()
            }
            for f in person.facts
        ]

        return person_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching person {person_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching person: {str(e)}"
        )


@app.get("/people/search/", tags=["People"])
async def search_people(q: str):
    """
    Search for people by name, tags, or facts.

    Args:
        q: Search query string

    Example: /people/search?q=yoga
    """
    try:
        db = load_data()
        query_lower = q.lower()

        results = []
        for person in db.people:
            # Search in name
            if query_lower in person.name.lower():
                results.append(person)
                continue

            # Search in tags
            if any(query_lower in tag.lower() for tag in person.tags):
                results.append(person)
                continue

            # Search in facts
            if any(query_lower in fact.content.lower() for fact in person.facts):
                results.append(person)
                continue

            # Search in metadata
            if person.metadata.occupation and query_lower in person.metadata.occupation.lower():
                results.append(person)
                continue
            if person.metadata.company and query_lower in person.metadata.company.lower():
                results.append(person)
                continue

        # Convert to response format
        people_data = []
        for person in results:
            person_dict = person.model_dump()
            person_dict["created_at"] = person.created_at.isoformat()
            person_dict["last_updated"] = person.last_updated.isoformat()
            person_dict["facts"] = [
                {
                    "content": f.content,
                    "type": f.type if isinstance(f.type, str) else f.type.value,
                    "timestamp": f.timestamp.isoformat()
                }
                for f in person.facts
            ]
            people_data.append(person_dict)

        return {
            "query": q,
            "count": len(people_data),
            "results": people_data
        }

    except Exception as e:
        logger.error(f"Error searching people: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching: {str(e)}"
        )


@app.get("/stats", response_model=StatsResponse, tags=["General"])
async def get_stats():
    """
    Get database statistics.

    Returns counts and recent activity information.
    """
    try:
        db = load_data()

        total_people = len(db.people)
        total_facts = sum(len(p.facts) for p in db.people)

        # Get 5 most recently added people
        sorted_people = sorted(db.people, key=lambda p: p.created_at, reverse=True)
        recent_additions = [p.name for p in sorted_people[:5]]

        return StatsResponse(
            total_people=total_people,
            total_facts=total_facts,
            recent_additions=recent_additions
        )

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching stats: {str(e)}"
        )


# Run with: uvicorn server:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

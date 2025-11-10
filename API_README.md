# Personal CRM API

FastAPI server for natural language CRM operations.

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the server
```bash
uvicorn server:app --reload
```

Server will start at: http://localhost:8000

### 3. View API docs
- Interactive docs: http://localhost:8000/docs
- Alternative docs: http://localhost:8000/redoc

## API Endpoints

### 🎯 Core Operations

#### POST /process
Process natural language input for CRM operations.

**Request:**
```bash
curl -X POST "http://localhost:8000/process" \
  -H "Content-Type: application/json" \
  -d '{"text": "Met Sarah at yoga, she is a teacher and loves coffee"}'
```

**Response:**
```json
{
  "success": true,
  "operation": "CREATE/UPDATE/DELETE",
  "message": "New person Sarah created",
  "data": { ... }
}
```

**Examples:**
- CREATE: `"Met John at the gym, he's a personal trainer"`
- READ: `"What do I know about Sarah?"`
- UPDATE: `"Sarah's email is sarah@yoga.com"`
- DELETE: `"Remove John from contacts"`

---

### 👥 People Endpoints

#### GET /people
Get all people in the database.

**Request:**
```bash
curl "http://localhost:8000/people"
```

**Response:**
```json
[
  {
    "id": "person_Sarah_001",
    "name": "Sarah",
    "hash_id": "f19d8fce849ff331",
    "metadata": {
      "phone": "555-1234",
      "occupation": "teacher",
      ...
    },
    "facts": [
      {
        "content": "Met at yoga",
        "type": "activity",
        "timestamp": "2025-11-10T14:30:00Z"
      }
    ],
    "tags": ["yoga", "teacher"],
    "created_at": "2025-11-10T14:30:00Z",
    "last_updated": "2025-11-10T19:15:00Z"
  }
]
```

---

#### GET /people/{person_id}
Get a specific person by ID.

**Request:**
```bash
curl "http://localhost:8000/people/person_Sarah_001"
```

**Response:**
```json
{
  "id": "person_Sarah_001",
  "name": "Sarah",
  ...
}
```

---

#### GET /people/search?q={query}
Search for people by name, tags, facts, or occupation.

**Request:**
```bash
curl "http://localhost:8000/people/search?q=yoga"
```

**Response:**
```json
{
  "query": "yoga",
  "count": 1,
  "results": [
    {
      "id": "person_Sarah_001",
      "name": "Sarah",
      ...
    }
  ]
}
```

---

### 📊 Utility Endpoints

#### GET /health
Health check endpoint.

**Request:**
```bash
curl "http://localhost:8000/health"
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-10T20:00:00Z",
  "database": {
    "accessible": true,
    "people_count": 5
  }
}
```

---

#### GET /stats
Get database statistics.

**Request:**
```bash
curl "http://localhost:8000/stats"
```

**Response:**
```json
{
  "total_people": 5,
  "total_facts": 15,
  "recent_additions": ["Sarah", "John", "Mike"]
}
```

---

#### GET /
Root endpoint with API information.

**Request:**
```bash
curl "http://localhost:8000/"
```

## Python Client Example

```python
import requests

# Base URL
BASE_URL = "http://localhost:8000"

# Process natural language input
def add_person(text: str):
    response = requests.post(
        f"{BASE_URL}/process",
        json={"text": text}
    )
    return response.json()

# Get all people
def get_all_people():
    response = requests.get(f"{BASE_URL}/people")
    return response.json()

# Get specific person
def get_person(person_id: str):
    response = requests.get(f"{BASE_URL}/people/{person_id}")
    return response.json()

# Search people
def search_people(query: str):
    response = requests.get(
        f"{BASE_URL}/people/search",
        params={"q": query}
    )
    return response.json()

# Example usage
if __name__ == "__main__":
    # Add a new person
    result = add_person("Met Alice, she's a software engineer at Google")
    print(f"Added: {result}")

    # Get all people
    people = get_all_people()
    print(f"Total people: {len(people)}")

    # Search
    results = search_people("engineer")
    print(f"Found {results['count']} engineers")
```

## JavaScript/TypeScript Client Example

```typescript
const BASE_URL = 'http://localhost:8000';

// Process natural language input
async function addPerson(text: string) {
  const response = await fetch(`${BASE_URL}/process`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  });
  return response.json();
}

// Get all people
async function getAllPeople() {
  const response = await fetch(`${BASE_URL}/people`);
  return response.json();
}

// Get specific person
async function getPerson(personId: string) {
  const response = await fetch(`${BASE_URL}/people/${personId}`);
  return response.json();
}

// Search people
async function searchPeople(query: string) {
  const response = await fetch(`${BASE_URL}/people/search?q=${query}`);
  return response.json();
}

// Example usage
(async () => {
  // Add a new person
  const result = await addPerson("Met Bob, he loves hiking and photography");
  console.log('Added:', result);

  // Get all people
  const people = await getAllPeople();
  console.log('Total people:', people.length);

  // Search
  const results = await searchPeople("hiking");
  console.log(`Found ${results.count} hikers`);
})();
```

## cURL Examples

```bash
# Add a person
curl -X POST "http://localhost:8000/process" \
  -H "Content-Type: application/json" \
  -d '{"text": "Met Emma at a conference, she works on AI safety"}'

# Get all people
curl "http://localhost:8000/people"

# Get specific person
curl "http://localhost:8000/people/person_Emma_001"

# Search for people
curl "http://localhost:8000/people/search?q=AI"

# Get stats
curl "http://localhost:8000/stats"

# Health check
curl "http://localhost:8000/health"
```

## Production Deployment

### Using Gunicorn (recommended for production)
```bash
gunicorn server:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Using Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t crm-api .
docker run -p 8000:8000 crm-api
```

## Configuration

The API uses the same `.env` file as the CLI:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_api_key
GROQ_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
```

## CORS

CORS is enabled for all origins by default. For production, update `server.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourfrontend.com"],  # Specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Notes

- **Auto-confirmation**: The API auto-confirms all operations (no interactive prompts)
- **Disambiguation**: Automatically selects the first option when multiple people match
- **Validation**: All requests/responses validated with Pydantic
- **Logging**: Comprehensive logging to console and `crm.log`

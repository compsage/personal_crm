# Two-Step API Workflow

The CRM API now uses a **2-step workflow** that separates analysis from execution:

## Workflow

```
1. POST /analyze  → Get plan (what will be done)
2. POST /execute  → Execute plan (actually do it)
```

This gives you **full control** to review what will happen before committing.

---

## Step 1: POST /analyze

**Analyze natural language and get the execution plan.**

### Request
```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "Content-Type: application/json" \
  -d '{"text": "Met Alice, she is a software engineer at Google"}'
```

### Response
```json
{
  "operation": "CREATE",
  "confidence": 0.95,
  "reasoning": "User met a new person named Alice...",
  "needs_clarification": false,
  "clarification_question": null,
  "clarification_options": null,
  "extraction": {
    "operation": "CREATE",
    "person": {
      "name": "Alice",
      "metadata": {
        "occupation": "software engineer",
        "company": "Google",
        ...
      },
      "facts": [...],
      "tags": ["tech", "engineer"]
    },
    "summary": "New person Alice - software engineer at Google"
  },
  "summary": "New person Alice - software engineer at Google"
}
```

### What You Get:
- **operation**: What CRUD operation will be performed (CREATE/READ/UPDATE/DELETE)
- **confidence**: How confident the AI is (0.0-1.0)
- **reasoning**: Why this operation was chosen
- **extraction**: The exact data that will be used
- **summary**: Human-readable description

**→ Review this before proceeding to Step 2**

---

## Step 2: POST /execute

**Execute the analyzed plan.**

### Request
```bash
curl -X POST "http://localhost:8000/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "CREATE",
    "extraction": {
      "operation": "CREATE",
      "person": {
        "name": "Alice",
        "metadata": { "occupation": "software engineer", "company": "Google" },
        "facts": [],
        "tags": ["tech", "engineer"]
      },
      "summary": "New person Alice"
    }
  }'
```

### Response
```json
{
  "success": true,
  "operation": "CREATE",
  "message": "New person Alice - software engineer at Google",
  "data": {
    "people": [...],
    "summary": "New person Alice - software engineer at Google"
  }
}
```

---

## Complete Example (Python)

```python
import requests

BASE_URL = "http://localhost:8000"

# Step 1: Analyze
response = requests.post(
    f"{BASE_URL}/analyze",
    json={"text": "Met Bob at the gym, he's a personal trainer"}
)
analysis = response.json()

print(f"Operation: {analysis['operation']}")
print(f"Summary: {analysis['summary']}")
print(f"Confidence: {analysis['confidence']}")

# Review the extraction
print("\nExtraction:")
print(analysis['extraction'])

# User approves...

# Step 2: Execute
response = requests.post(
    f"{BASE_URL}/execute",
    json={
        "operation": analysis['operation'],
        "extraction": analysis['extraction']
    }
)
result = response.json()

print(f"\nSuccess: {result['success']}")
print(f"Message: {result['message']}")
```

---

## Complete Example (cURL)

```bash
# Step 1: Analyze
curl -X POST "http://localhost:8000/analyze" \
  -H "Content-Type: application/json" \
  -d '{"text": "Met Sarah at yoga, she is a teacher"}' \
  > analysis.json

# Review analysis.json...

# Step 2: Execute
curl -X POST "http://localhost:8000/execute" \
  -H "Content-Type: application/json" \
  -d @analysis.json
```

---

## Complete Example (JavaScript)

```javascript
const BASE_URL = 'http://localhost:8000';

// Step 1: Analyze
const analyzeResponse = await fetch(`${BASE_URL}/analyze`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    text: 'Met Emma who loves photography'
  })
});

const analysis = await analyzeResponse.json();

console.log('Operation:', analysis.operation);
console.log('Summary:', analysis.summary);
console.log('Confidence:', analysis.confidence);

// User reviews and approves...

// Step 2: Execute
const executeResponse = await fetch(`${BASE_URL}/execute`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    operation: analysis.operation,
    extraction: analysis.extraction
  })
});

const result = await executeResponse.json();

console.log('Success:', result.success);
console.log('Message:', result.message);
```

---

## All Supported Operations

### CREATE
```json
{"text": "Met Alice at a conference, she's a data scientist"}
```

### READ
```json
{"text": "What do I know about Alice?"}
```

### UPDATE
```json
{"text": "Alice's email is alice@example.com"}
```

### DELETE
```json
{"text": "Remove Alice from my contacts"}
```

---

## Benefits of 2-Step Workflow

1. **Review Before Execute** - See exactly what will happen
2. **Modify If Needed** - Edit the extraction JSON before executing
3. **Audit Trail** - Log what was planned vs what was executed
4. **Safer** - No accidental deletions or updates
5. **Flexible** - Can build approval workflows on top

---

## Quick Test

```bash
# Run the test script
python3 test_two_step_api.py
```

---

## API Documentation

Interactive docs: **http://localhost:8000/docs**

View all endpoints and try them out in your browser!

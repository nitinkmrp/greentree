# 📡 HubSpot Deals ETL Service - REST API Documentation (Task 1.4)

Interactive OpenAPI / Swagger documentation is rendered live at `http://localhost:5200/docs/`.

---

## 📋 Overview

The `hubspot_deals` microservice provides REST API endpoints for initiating, monitoring, canceling, and retrieving HubSpot CRM deal extraction jobs via DLT pipelines.

### Key Specifications
- **API Version**: `1.0.0`
- **Base Path**: `/api`
- **Content Type**: `application/json`
- **Default Port**: `5200` (Dev), `5201` (Stage), `5202` (Prod)

---

## 🔐 Authentication Requirements

Endpoints requiring authorization expect a Bearer Access Token passed via HTTP headers:

```http
Authorization: Bearer <YOUR_HUBSPOT_PRIVATE_APP_TOKEN>
X-Tenant-ID: org-acme-corp
Content-Type: application/json
```

---

## 🌐 Endpoints Summary

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `GET` | `/health` | Service health status check | No |
| `POST` | `/api/scan/start` | Start asynchronous background scan | Yes |
| `GET` | `/api/scan/{scan_id}/status` | Get scan progress & state details | Yes |
| `GET` | `/api/scan/{scan_id}/results` | Retrieve extracted deal records | Yes |
| `POST` | `/api/scan/{scan_id}/cancel` | Cancel active extraction job | Yes |
| `GET` | `/api/pipeline/info` | Pipeline schema & metadata info | Yes |

---

## 🔍 Request & Response Schemas

### 1. Start Deal Scan Job (`POST /api/scan/start`)

**Request Payload Schema**:
```json
{
  "type": "object",
  "required": ["scan_id", "tenant_id"],
  "properties": {
    "scan_id": {
      "type": "string",
      "example": "scan-deals-20260817-001",
      "description": "Unique external tracking identifier"
    },
    "tenant_id": {
      "type": "string",
      "example": "org-acme-corp",
      "description": "Multi-tenant tenant ID header"
    },
    "batch_size": {
      "type": "integer",
      "default": 100,
      "minimum": 1,
      "maximum": 100
    },
    "properties": {
      "type": "array",
      "items": { "type": "string" },
      "example": ["dealname", "amount", "dealstage", "pipeline", "closedate"]
    }
  }
}
```

**Response Payload (202 Accepted)**:
```json
{
  "status": "success",
  "message": "Scan job initiated successfully",
  "scan_id": "scan-deals-20260817-001",
  "job_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "timestamp": "2026-08-17T15:52:00.000Z"
}
```

---

### 2. Get Scan Status (`GET /api/scan/{scan_id}/status`)

**Response Payload (200 OK)**:
```json
{
  "scan_id": "scan-deals-20260817-001",
  "status": "running",
  "total_items": 500,
  "processed_items": 250,
  "failed_items": 0,
  "started_at": "2026-08-17T15:52:00.000Z",
  "completed_at": null,
  "cursor_token": "NTB",
  "error_message": null
}
```

---

### 3. Get Extracted Results (`GET /api/scan/{scan_id}/results`)

**Query Parameters**:
- `page` (integer, default 1)
- `page_size` (integer, default 50, max 500)

**Response Payload (200 OK)**:
```json
{
  "scan_id": "scan-deals-20260817-001",
  "page": 1,
  "page_size": 50,
  "total_count": 250,
  "data": [
    {
      "id": "15493208741",
      "dealname": "Acme Renewal #1",
      "amount": 5099.99,
      "dealstage": "presentationscheduled",
      "pipeline": "default",
      "closedate": "2026-03-31T23:59:59.000Z",
      "createdate": "2026-01-15T10:30:00.000Z",
      "hs_lastmodifieddate": "2026-02-10T14:22:10.123Z",
      "hubspot_owner_id": "9018247",
      "hs_deal_stage_probability": 0.65,
      "custom_properties": {},
      "_tenant_id": "org-acme-corp",
      "_scan_id": "scan-deals-20260817-001",
      "_extracted_at": "2026-08-17T15:52:05.123Z",
      "_source_service": "hubspot_deals"
    }
  ]
}
```

---

## ⚠️ Status Codes & Error Responses

| Status Code | Code String | Meaning |
|-------------|-------------|---------|
| `200 OK` | `SUCCESS` | Request processed successfully |
| `202 Accepted` | `ACCEPTED` | Async background scan job initiated |
| `400 Bad Request` | `VALIDATION_ERROR` | Missing parameters or invalid payload |
| `401 Unauthorized` | `UNAUTHORIZED` | Invalid or missing authentication token |
| `404 Not Found` | `NOT_FOUND` | Scan job ID does not exist |
| `409 Conflict` | `CONFLICT` | Scan job with specified `scan_id` is already running |
| `429 Rate Limited` | `RATE_LIMIT_EXCEEDED` | HubSpot API rate limit reached |
| `500 Internal Error` | `INTERNAL_ERROR` | Server exception encountered |

**Sample Error Response**:
```json
{
  "status": "error",
  "error_code": "VALIDATION_ERROR",
  "message": "Missing required field 'scan_id' in request body",
  "timestamp": "2026-08-17T15:52:00.000Z"
}
```

---

## 💻 Example Requests

### **cURL Examples**

#### 1. Start Scan Job
```bash
curl -X POST "http://localhost:5200/api/scan/start" \
  -H "Authorization: Bearer pat-na1-xxxx-xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "scan_id": "scan-deals-20260817-001",
    "tenant_id": "org-acme-corp",
    "batch_size": 100
  }'
```

#### 2. Check Status
```bash
curl -X GET "http://localhost:5200/api/scan/scan-deals-20260817-001/status" \
  -H "Authorization: Bearer pat-na1-xxxx-xxxx"
```

#### 3. Get Extracted Deals
```bash
curl -X GET "http://localhost:5200/api/scan/scan-deals-20260817-001/results?page=1&page_size=50" \
  -H "Authorization: Bearer pat-na1-xxxx-xxxx"
```

---

### **Python Request Example**

```python
import requests

BASE_URL = "http://localhost:5200"
HEADERS = {
    "Authorization": "Bearer pat-na1-xxxx-xxxx",
    "Content-Type": "application/json"
}

# 1. Start Scan
start_resp = requests.post(f"{BASE_URL}/api/scan/start", json={
    "scan_id": "scan-deals-py-001",
    "tenant_id": "org-acme-corp",
    "batch_size": 100
}, headers=HEADERS)
print("Start Scan:", start_resp.json())

# 2. Check Status
status_resp = requests.get(f"{BASE_URL}/api/scan/scan-deals-py-001/status", headers=HEADERS)
print("Status:", status_resp.json())
```
# HubSpot Deals ETL Service - Test Results & Phase 3 Validation Report

**Service Name**: `hubspot-deals-etl`  
**Execution Environment**: Development (`PORT=5200`, PostgreSQL `hubspot_deals_data_dev`)  
**Validation Date**: August 17, 2026  
**Status**: `PASSED` (7/7 Test Cases Succeeded)

---

## 1. Summary of Test Execution

| Test ID | Test Category | Endpoint / Component | Result | Status Code / Details |
|---|---|---|---|---|
| `test_01` | Health Check | `GET /health` | **PASSED** | HTTP `200 OK` |
| `test_02` | Root Index | `GET /` | **PASSED** | HTTP `200 OK` (Returns Endpoints Index) |
| `test_03` | Token Validation | `HubSpotAPIService.validate_token` | **PASSED** | Token Scope Probing Validated |
| `test_04` | Data Source | `create_data_source` (DLT Resource) | **PASSED** | Resource Initialized (`primary_key='id'`) |
| `test_05` | Schema Transformation | Property Casting & Custom Props Isolation | **PASSED** | Float Conversion & `JSONB` Isolation Verified |
| `test_06` | Checkpoint Interruption | State Resumption & Cursor Tracking | **PASSED** | Checkpoint Callback Payload Verified |
| `test_07` | Live API Extraction | `GET /crm/v3/objects/deals` | **PASSED** | **5 Test Deals Successfully Extracted** (817.18 ms) |

---

## 2. Health Endpoint Verification

### `GET http://localhost:5200/health`
```json
{
  "documentation": "/docs",
  "service": "hubspot_deals",
  "status": "healthy",
  "version": "1.0.0"
}
```

---

## 3. Live HubSpot API Extraction Proof

- **Target Endpoint**: `https://api.hubapi.com/crm/v3/objects/deals`
- **Authentication**: Private App Token (`Authorization: Bearer pat-na2-f8...bbe9`)
- **Total Records Extracted**: `5`
- **Response Duration**: `817.18 ms`

### Sample Extracted Deal Payload:
```json
{
  "id": "341763907320",
  "properties": {
    "amount": "5000",
    "closedate": "2026-08-31T05:22:50.368Z",
    "createdate": "2026-08-13T05:29:12.531Z",
    "dealname": "test1",
    "dealstage": "qualifiedtobuy",
    "hs_lastmodifieddate": "2026-08-13T05:29:19.450Z",
    "hs_object_id": "341763907320",
    "pipeline": "default"
  },
  "createdAt": "2026-08-13T05:29:12.531Z",
  "updatedAt": "2026-08-13T05:29:19.450Z",
  "archived": false,
  "url": "https://app-na2.hubspot.com/contacts/247015770/record/0-3/341763907320"
}
```

---

## 4. Schema & Data Transformation Verification

The extracted record is transformed into PostgreSQL table structure with the following type mappings and audit metadata:

```sql
-- Transformed Record Structure in postgres_dev
SELECT 
    id,                         -- VARCHAR(255) PRIMARY KEY ('341763907320')
    dealname,                   -- VARCHAR(255) ('test1')
    amount,                     -- NUMERIC(15,2) (5000.00)
    dealstage,                  -- VARCHAR(100) ('qualifiedtobuy')
    pipeline,                   -- VARCHAR(100) ('default')
    closedate,                  -- TIMESTAMP WITH TIME ZONE ('2026-08-31T05:22:50.368Z')
    createdate,                 -- TIMESTAMP WITH TIME ZONE ('2026-08-13T05:29:12.531Z')
    hs_lastmodifieddate,        -- TIMESTAMP WITH TIME ZONE ('2026-08-13T05:29:19.450Z')
    custom_properties,          -- JSONB (Isolated dynamic custom properties)
    _tenant_id,                 -- VARCHAR(100) Multi-tenant provenance ID
    _scan_id,                   -- VARCHAR(255) Scan Job reference ID
    _extracted_at,              -- TIMESTAMP WITH TIME ZONE Ingestion timestamp
    _source_service,            -- VARCHAR(100) ('hubspot_deals')
    _page_number                -- INT Page sequence number
FROM hubspot_deals_dev.hubspot_deals;
```

---

## 5. Checkpoint Interruption & Resumption Protocol

State persistence is handled via cursor tokens (`paging.next.after`) stored in PostgreSQL `scan_jobs` table:

```json
{
  "phase": "main_data",
  "records_processed": 5,
  "cursor": "NTA=",
  "page_number": 1,
  "batch_size": 100
}
```

---

## 6. Swagger API Documentation Verification

- **Documentation URL**: [http://localhost:5200/docs/](http://localhost:5200/docs/)
- **Swagger JSON Definition**: Loaded cleanly with interactive Try-It-Out UI for all endpoints (`/api/v1/scan/start`, `/api/v1/scan/{id}/status`, `/api/v1/scan/list`).

# 📋 hubspot_deals - Integration with HubSpot CRM API v3 (Deals Endpoint)

This document details the HubSpot CRM API v3 Deals endpoints and extraction logic implemented in `hubspot-deals-etl` for automated data ingestion and transformations.

---

## 📋 Overview

The `hubspot_deals` service integrates with HubSpot CRM API v3 to retrieve deal object records, property metadata, and pipeline associations.

### ✅ **Required Endpoint (Essential)**
| **API Endpoint** | **Purpose** | **Version** | **Required Scopes** | **Usage** |
|------------------|-------------|-------------|---------------------|-----------|
| `/crm/v3/objects/deals` | List and paginate all deal records | v3 | `crm.objects.deals.read` | **Required** |

### 🔧 **Optional Endpoints (Advanced Features)**
| **API Endpoint** | **Purpose** | **Version** | **Required Scopes** | **Usage** |
|------------------|-------------|-------------|---------------------|-----------|
| `/crm/v3/objects/deals/{dealId}` | Get single deal record details | v3 | `crm.objects.deals.read` | Optional |
| `/crm/v3/properties/deals` | Fetch custom & standard deal property definitions | v3 | `crm.schemas.deals.read` | Optional |
| `/crm/v3/pipelines/deals` | Retrieve pipeline stages & win probabilities | v3 | `crm.objects.deals.read` | Optional |

---

## 🔐 Authentication Requirements

HubSpot API v3 authentication utilizes **Private App Access Tokens** passed in standard HTTP headers.

```http
Authorization: Bearer <YOUR_PRIVATE_APP_ACCESS_TOKEN>
Content-Type: application/json
```

### **Required Scopes**
- `crm.objects.deals.read` - Read access to HubSpot deal records
- `crm.schemas.deals.read` - Read access to deal property schema definitions

---

## 🌐 HubSpot CRM API Endpoints

### 🎯 **PRIMARY ENDPOINT (Deals Listing & Extraction)**

### 1. **List Deals** - `/crm/v3/objects/deals` ✅ **REQUIRED**

**Purpose**: Fetch paginated deal records with specified property fields using cursor-based pagination.

**Method**: `GET`

**URL**: `https://api.hubapi.com/crm/v3/objects/deals`

**Query Parameters**:
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `limit` | integer | No | Maximum items to return per page (max 100, default 10) | `limit=100` |
| `after` | string | No | Paging cursor token for fetching next page (`paging.next.after`) | `after=NTB` |
| `properties` | string | No | Comma-separated list of deal properties to include | `properties=dealname,amount,dealstage,closedate,pipeline` |
| `archived` | boolean | No | Whether to include archived deals (default `false`) | `archived=false` |
| `associations` | string | No | Related objects to return | `associations=contacts,companies` |

**Request Example**:
```http
GET https://api.hubapi.com/crm/v3/objects/deals?limit=100&properties=dealname,amount,dealstage,pipeline,closedate,createdate,hs_lastmodifieddate,hubspot_owner_id,hs_deal_stage_probability&archived=false
Authorization: Bearer pat-na1-xxxx-xxxx-xxxx
Content-Type: application/json
```

**Response Structure**:
```json
{
  "results": [
    {
      "id": "15493208741",
      "properties": {
        "amount": "5099.99",
        "closedate": "2026-03-31T23:59:59.000Z",
        "createdate": "2026-01-15T10:30:00.000Z",
        "dealname": "Enterprise Deal #1",
        "dealstage": "presentationscheduled",
        "hs_deal_stage_probability": "0.65",
        "hs_lastmodifieddate": "2026-02-10T14:22:10.123Z",
        "hubspot_owner_id": "9018247",
        "pipeline": "default"
      },
      "createdAt": "2026-01-15T10:30:00.000Z",
      "updatedAt": "2026-02-10T14:22:10.123Z",
      "archived": false
    }
  ],
  "paging": {
    "next": {
      "link": "https://api.hubapi.com/crm/v3/objects/deals?limit=100&after=NTB",
      "after": "NTB"
    }
  }
}
```

---

## ⚡ Data Extraction & Transformation Logic

### **Extracted Record Field Mapping**
During ingestion via DLT, records are parsed and mapped as follows:

| Field Name | Type | Ingestion Rule |
|------------|------|----------------|
| `id` | String | Primary Key |
| `dealname` | String | Standard Deal Name |
| `amount` | Float | Parsed from String to Double Precision |
| `dealstage` | String | Stage identifier |
| `pipeline` | String | Pipeline identifier |
| `closedate` | ISO Timestamp | Parsed to UTC ISO 8601 |
| `createdate` | ISO Timestamp | Parsed to UTC ISO 8601 |
| `hs_lastmodifieddate` | ISO Timestamp | Parsed to UTC ISO 8601 |
| `hs_deal_stage_probability` | Float | Parsed to Double Precision |
| `custom_properties` | JSONB | Isolated non-standard fields |
| `_tenant_id` | String | Multi-tenancy metadata tag |
| `_scan_id` | String | Background execution scan ID |
| `_extracted_at` | ISO Timestamp | Ingestion timestamp |

---

## ⚡ Performance & Rate Limits

- **Rate Limit**: 100 requests per 10 seconds per Private App Access Token (Professional/Enterprise tiers allow higher thresholds).
- **Batch Size**: `100` deals per request (`limit=100`).
- **Resilience**: Cursor state checkpointing stores `paging.next.after` for resuming after server interruptions.

---

## 🧪 Quick Test (cURL)

```bash
curl -X GET \
  "https://api.hubapi.com/crm/v3/objects/deals?limit=5&properties=dealname,amount,dealstage" \
  -H "Authorization: Bearer YOUR_HUBSPOT_TOKEN" \
  -H "Content-Type: application/json"
```
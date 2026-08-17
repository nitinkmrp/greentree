# 🗄️ HubSpot Deals ETL Database Schema Specification (Task 1.3)

This document specifies the PostgreSQL database schema for the `hubspot-deals-etl` service, including data type mappings from HubSpot CRM v3 API, ETL metadata fields, indexing for search/filter optimization, and multi-tenant data isolation architecture.

---

## 📋 Overview

The `hubspot-deals-etl` storage layer comprises two core relational tables in PostgreSQL:

1. **`scan_jobs`**: Job state machine, progress counters, execution logs, and checkpoint continuation tokens.
2. **`hubspot_deals`**: Ingested HubSpot Deals with normalized field types, custom properties `JSONB` storage, and multi-tenant audit provenance headers.

---

## 🏗️ 1. PostgreSQL Table Structure & Type Mapping

### **HubSpot API v3 Property to PostgreSQL Type Mapping**

| HubSpot Property | HubSpot Type | PostgreSQL Data Type | Nullable | Transformation / Constraint |
|------------------|--------------|----------------------|----------|-----------------------------|
| `id` | String / ID | `VARCHAR(50)` | **No** | Primary Key (HubSpot Deal ID) |
| `dealname` | String | `VARCHAR(255)` | **No** | Deal Title / Name |
| `amount` | Number (String) | `DOUBLE PRECISION` | Yes | Cast to Double Precision Float |
| `dealstage` | String | `VARCHAR(100)` | **No** | Indexed Stage Code (e.g. `closedwon`) |
| `pipeline` | String | `VARCHAR(100)` | **No** | Indexed Pipeline ID (e.g. `default`) |
| `closedate` | Date/Time (ISO/epoch)| `TIMESTAMP WITH TIME ZONE` | Yes | Standardized to UTC ISO 8601 |
| `createdate` | Date/Time (ISO/epoch)| `TIMESTAMP WITH TIME ZONE` | **No** | Standardized to UTC ISO 8601 |
| `hs_lastmodifieddate` | Date/Time (ISO/epoch)| `TIMESTAMP WITH TIME ZONE` | **No** | Standardized to UTC ISO 8601 |
| `hubspot_owner_id` | String / ID | `VARCHAR(50)` | Yes | Owner Account ID |
| `hs_deal_stage_probability` | Number (String) | `DOUBLE PRECISION` | Yes | Probability Float (`0.00` to `1.00`) |
| Custom Properties | Dynamic Key-Value | `JSONB` | Yes | Unmapped custom properties dynamic object |

---

## 🛡️ 2. ETL Metadata & Audit Fields

Every deal record inserted into `hubspot_deals` includes four standard metadata fields for data lineage, provenance, and auditability:

| ETL Field | Type | Nullable | Purpose & Source |
|-----------|------|----------|------------------|
| `_extracted_at` | `TIMESTAMP WITH TIME ZONE` | **No** | Ingestion timestamp generated at runtime (UTC) |
| `_scan_id` | `VARCHAR(100)` | **No** | ID of the scan job that extracted this record |
| `_tenant_id` | `VARCHAR(100)` | **No** | Organization/Tenant ID for multi-tenant isolation |
| `_source_service` | `VARCHAR(50)` | **No** | Constant provenance tag (`hubspot_deals`) |

---

## 📝 3. DDL SQL Schema Definition

```sql
-- Enforce UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Table 1: scan_jobs
CREATE TABLE IF NOT EXISTS scan_jobs (
    id VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    scan_id VARCHAR(100) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    scan_type VARCHAR(50) NOT NULL DEFAULT 'hubspot_deals',
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    organization_id VARCHAR(100),
    cursor_token VARCHAR(255),
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    total_items INTEGER DEFAULT 0 CHECK (total_items >= 0),
    processed_items INTEGER DEFAULT 0 CHECK (processed_items >= 0),
    failed_items INTEGER DEFAULT 0 CHECK (failed_items >= 0),
    success_rate VARCHAR(10),
    batch_size INTEGER DEFAULT 100 CHECK (batch_size > 0),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Table 2: hubspot_deals
CREATE TABLE IF NOT EXISTS hubspot_deals (
    id VARCHAR(50) PRIMARY KEY,
    scan_job_id VARCHAR(36) NOT NULL REFERENCES scan_jobs(id) ON DELETE CASCADE,
    dealname VARCHAR(255) NOT NULL,
    amount DOUBLE PRECISION,
    dealstage VARCHAR(100) NOT NULL,
    pipeline VARCHAR(100) NOT NULL,
    closedate TIMESTAMP WITH TIME ZONE,
    createdate TIMESTAMP WITH TIME ZONE NOT NULL,
    hs_lastmodifieddate TIMESTAMP WITH TIME ZONE NOT NULL,
    hubspot_owner_id VARCHAR(50),
    hs_deal_stage_probability DOUBLE PRECISION,
    description TEXT,
    custom_properties JSONB DEFAULT '{}'::jsonb,
    _tenant_id VARCHAR(100) NOT NULL,
    _scan_id VARCHAR(100) NOT NULL,
    _extracted_at TIMESTAMP WITH TIME ZONE NOT NULL,
    _source_service VARCHAR(50) NOT NULL DEFAULT 'hubspot_deals',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

---

## ⚡ 4. Indexes & Performance Optimization

To ensure fast query execution across large multi-tenant datasets, the following B-Tree and GIN indexes are established:

```sql
-- Scan Jobs Lookup Indexes
CREATE INDEX idx_scan_id_status ON scan_jobs(scan_id, status);
CREATE INDEX idx_scan_status_created ON scan_jobs(status, created_at DESC);
CREATE INDEX idx_scan_org ON scan_jobs(organization_id);

-- HubSpot Deals Multi-tenant & Filtering Indexes
CREATE INDEX idx_deals_tenant ON hubspot_deals(_tenant_id);
CREATE INDEX idx_deals_tenant_scan ON hubspot_deals(_tenant_id, _scan_id);
CREATE INDEX idx_deals_stage_pipeline ON hubspot_deals(dealstage, pipeline);
CREATE INDEX idx_deals_dates ON hubspot_deals(createdate DESC, closedate DESC);
CREATE INDEX idx_deals_lastmodified ON hubspot_deals(hs_lastmodifieddate DESC);
CREATE INDEX idx_deals_owner ON hubspot_deals(hubspot_owner_id);

-- GIN Index for dynamic custom properties search
CREATE INDEX idx_deals_custom_props ON hubspot_deals USING gin(custom_properties);
```

---

## 🔐 5. Multi-Tenant Data Isolation Strategy

Multi-tenancy in `hubspot-deals-etl` is implemented via **Logical Tenant Segregation with Row-Level Security (RLS)**:

1. **Mandatory Tenant Header**: Every query and database transaction filters strictly by `_tenant_id`.
2. **Row-Level Security (RLS) Policy**:
   ```sql
   ALTER TABLE hubspot_deals ENABLE ROW LEVEL SECURITY;

   CREATE POLICY tenant_isolation_policy ON hubspot_deals
       FOR ALL
       USING (_tenant_id = current_setting('app.current_tenant_id', true));
   ```
3. **Partitioning Strategy (Optional for High-Volume Deployments)**:
   For enterprise volume (>10M deals), `hubspot_deals` can be partitioned by list on `_tenant_id` or hash-partitioned to guarantee complete physical chunking.

---

**Document Version**: 2.0.0  
**Target Engine**: PostgreSQL 13+
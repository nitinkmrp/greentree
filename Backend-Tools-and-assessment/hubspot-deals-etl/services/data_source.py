import dlt
import logging
from typing import Dict, List, Any, Iterator, Optional, Callable
from datetime import datetime, timezone
from .hubspot_api_service import HubSpotAPIService
from loki_logger import get_logger, log_business_event, log_security_event


def create_data_source(
    job_config: Dict[str, Any],
    auth_config: Dict[str, Any],
    filters: Dict[str, Any],
    checkpoint_callback: Optional[Callable] = None,
    check_cancel_callback: Optional[Callable] = None,
    check_pause_callback: Optional[Callable] = None,
    resume_from: Optional[Dict[str, Any]] = None,
):
    """
    Create DLT source function for hubspot_deals data extraction with checkpoint support
    """
    logger = get_logger(__name__)
    api_service = HubSpotAPIService(base_url="https://api.hubapi.com", timeout=30)

    access_token = auth_config.get("accessToken")
    if not access_token:
        raise ValueError("No access token found in auth configuration")

    organization_id = job_config.get("organizationId", filters.get("tenant_id", "default_tenant"))

    logger.info(
        "Starting hubspot_deals data extraction",
        extra={
            "organization_id": organization_id,
            "filters": filters,
            "job_config": job_config,
        },
    )

    @dlt.resource(name="hubspot_deals", write_disposition="replace", primary_key="id")
    def get_main_data() -> Iterator[Dict[str, Any]]:
        """
        Extract deal records from HubSpot CRM API v3 with checkpoint support
        """
        if resume_from:
            after = resume_from.get("cursor")
            page_count = resume_from.get("page_number", 0)
            total_records = resume_from.get("records_processed", 0)
            logger.info(
                "Resuming hubspot_deals extraction",
                extra={
                    "operation": "data_extraction",
                    "page_number": page_count + 1,
                    "total_processed": total_records,
                },
            )
        else:
            after = None
            page_count = 0
            total_records = 0
            logger.info(
                "Starting fresh hubspot_deals extraction",
                extra={"operation": "data_extraction", "source": "hubspot_deals"},
            )

        checkpoint_interval = 10
        job_id = filters.get("scan_id", "unknown")
        batch_size = filters.get("batch_size", 100)

        while page_count < 1000:  # Safety limit
            try:
                # Check cancellation
                if check_cancel_callback and check_cancel_callback(job_id):
                    logger.info("Extraction cancelled by user", extra={"job_id": job_id})
                    if checkpoint_callback:
                        checkpoint_callback(job_id, {
                            "phase": "main_data_cancelled",
                            "records_processed": total_records,
                            "cursor": after,
                            "page_number": page_count,
                            "batch_size": batch_size
                        })
                    break

                # Check pause
                if check_pause_callback and check_pause_callback(job_id):
                    logger.info("Extraction paused by user", extra={"job_id": job_id})
                    if checkpoint_callback:
                        checkpoint_callback(job_id, {
                            "phase": "main_data_paused",
                            "records_processed": total_records,
                            "cursor": after,
                            "page_number": page_count,
                            "batch_size": batch_size
                        })
                    break

                # Fetch page of deal records
                data = api_service.get_deals(
                    access_token=access_token,
                    limit=batch_size,
                    after=after,
                    properties=filters.get("properties")
                )

                page_records = 0
                results = data.get("results", [])

                for record in results:
                    raw_props = record.get("properties", {})
                    
                    # Extract standard deal fields
                    transformed = {
                        "id": str(record.get("id")),
                        "dealname": raw_props.get("dealname", "Unnamed Deal"),
                        "dealstage": raw_props.get("dealstage", "unknown"),
                        "pipeline": raw_props.get("pipeline", "default"),
                        "closedate": raw_props.get("closedate"),
                        "createdate": raw_props.get("createdate") or record.get("createdAt"),
                        "hs_lastmodifieddate": raw_props.get("hs_lastmodifieddate") or record.get("updatedAt"),
                        "hubspot_owner_id": raw_props.get("hubspot_owner_id"),
                        "description": raw_props.get("description")
                    }

                    # Numeric property parsing
                    try:
                        transformed["amount"] = float(raw_props["amount"]) if raw_props.get("amount") is not None else None
                    except (ValueError, TypeError):
                        transformed["amount"] = None

                    try:
                        transformed["hs_deal_stage_probability"] = float(raw_props["hs_deal_stage_probability"]) if raw_props.get("hs_deal_stage_probability") is not None else None
                    except (ValueError, TypeError):
                        transformed["hs_deal_stage_probability"] = None

                    # Dynamic Custom Properties Isolation
                    standard_fields = {
                        "dealname", "amount", "dealstage", "pipeline", "closedate",
                        "createdate", "hs_lastmodifieddate", "hubspot_owner_id",
                        "hs_deal_stage_probability", "description"
                    }
                    custom_props = {k: v for k, v in raw_props.items() if k not in standard_fields}
                    transformed["custom_properties"] = custom_props

                    # Multi-Tenancy & Ingestion Audit Metadata
                    transformed.update({
                        "_tenant_id": organization_id,
                        "_scan_id": job_id,
                        "_extracted_at": datetime.now(timezone.utc).isoformat(),
                        "_source_service": "hubspot_deals",
                        "_page_number": page_count + 1,
                    })

                    yield transformed
                    page_records += 1

                total_records += page_records
                page_count += 1

                # Extract cursor for next page
                next_cursor = None
                paging = data.get("paging", {})
                if paging and "next" in paging and "after" in paging["next"]:
                    next_cursor = paging["next"]["after"]

                # Periodic Checkpoint
                if checkpoint_callback and page_count % checkpoint_interval == 0:
                    checkpoint_callback(job_id, {
                        "phase": "main_data",
                        "records_processed": total_records,
                        "cursor": next_cursor,
                        "page_number": page_count,
                        "batch_size": batch_size
                    })

                if next_cursor:
                    after = next_cursor
                else:
                    # Completed all records
                    if checkpoint_callback:
                        checkpoint_callback(job_id, {
                            "phase": "main_data_completed",
                            "records_processed": total_records,
                            "cursor": None,
                            "page_number": page_count,
                            "batch_size": batch_size
                        })
                    logger.info("hubspot_deals extraction finished", extra={"total_records": total_records})
                    break

            except Exception as e:
                logger.error("Error during hubspot_deals extraction", extra={"error": str(e)}, exc_info=True)
                if checkpoint_callback:
                    checkpoint_callback(job_id, {
                        "phase": "main_data_error",
                        "records_processed": total_records,
                        "cursor": after,
                        "page_number": page_count,
                        "error": str(e)
                    })
                raise e

    return [get_main_data]
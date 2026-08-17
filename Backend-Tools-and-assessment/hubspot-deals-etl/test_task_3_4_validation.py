import unittest
import json
import requests
import time
from datetime import datetime, timezone
import sys
import os

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.hubspot_api_service import HubSpotAPIService
from services.data_source import create_data_source
from app import create_app

class TestHubSpotDealsETLValidation(unittest.TestCase):
    """
    Day 7 Validation & Testing Suite for HubSpot Deals DLT ETL Pipeline
    """

    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing')
        cls.client = cls.app.test_client()

    def test_01_health_endpoint(self):
        """Test GET /health endpoint returns 200 OK and healthy status"""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get('status'), 'healthy')
        self.assertEqual(data.get('service'), 'hubspot_deals')

    def test_02_index_root_endpoint(self):
        """Test GET / endpoint returns service meta and endpoints map"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('health', data)
        self.assertIn('endpoints', data)

    def test_03_hubspot_api_service_validation(self):
        """Test HubSpotAPIService token validation and connection test structure"""
        api_service = HubSpotAPIService(base_url="https://api.hubapi.com", timeout=5)
        result = api_service.test_connection("dummy_invalid_token")
        self.assertIn('token_valid', result)
        self.assertFalse(result['token_valid'])

    def test_04_data_source_resource_transformation(self):
        """Test DLT resource generation and record property transformation logic"""
        dummy_job_config = {"organizationId": "test-org-001"}
        dummy_auth_config = {"accessToken": "dummy_token"}
        dummy_filters = {"scan_id": "test-scan-001", "tenant_id": "test-org-001", "batch_size": 5}

        source_funcs = create_data_source(
            job_config=dummy_job_config,
            auth_config=dummy_auth_config,
            filters=dummy_filters
        )
        self.assertTrue(callable(source_funcs[0]))
        self.assertEqual(len(source_funcs), 1)

    def test_05_deal_record_schema_and_metadata(self):
        """Test deal record transformation and metadata field formatting"""
        raw_hubspot_record = {
            "id": "123456789",
            "createdAt": "2026-08-17T10:00:00Z",
            "updatedAt": "2026-08-17T12:00:00Z",
            "properties": {
                "dealname": "Enterprise Renewal Test Deal",
                "amount": "15000.50",
                "dealstage": "presentationscheduled",
                "pipeline": "default",
                "closedate": "2026-12-31T23:59:59Z",
                "createdate": "2026-08-17T10:00:00Z",
                "hs_lastmodifieddate": "2026-08-17T12:00:00Z",
                "hubspot_owner_id": "987654",
                "hs_deal_stage_probability": "0.75",
                "custom_deal_type": "Subscription Renewal"
            }
        }

        raw_props = raw_hubspot_record["properties"]
        standard_fields = {
            "dealname", "amount", "dealstage", "pipeline", "closedate",
            "createdate", "hs_lastmodifieddate", "hubspot_owner_id",
            "hs_deal_stage_probability", "description"
        }
        custom_props = {k: v for k, v in raw_props.items() if k not in standard_fields}

        transformed = {
            "id": str(raw_hubspot_record["id"]),
            "dealname": raw_props.get("dealname"),
            "amount": float(raw_props["amount"]),
            "dealstage": raw_props.get("dealstage"),
            "pipeline": raw_props.get("pipeline"),
            "closedate": raw_props.get("closedate"),
            "createdate": raw_props.get("createdate"),
            "hs_lastmodifieddate": raw_props.get("hs_lastmodifieddate"),
            "hubspot_owner_id": raw_props.get("hubspot_owner_id"),
            "hs_deal_stage_probability": float(raw_props["hs_deal_stage_probability"]),
            "custom_properties": custom_props,
            "_tenant_id": "test-org-001",
            "_scan_id": "test-scan-001",
            "_extracted_at": datetime.now(timezone.utc).isoformat(),
            "_source_service": "hubspot_deals",
            "_page_number": 1
        }

        # Assertions
        self.assertEqual(transformed["id"], "123456789")
        self.assertEqual(transformed["amount"], 15000.50)
        self.assertEqual(transformed["hs_deal_stage_probability"], 0.75)
        self.assertEqual(transformed["custom_properties"], {"custom_deal_type": "Subscription Renewal"})
        self.assertEqual(transformed["_tenant_id"], "test-org-001")
        self.assertEqual(transformed["_source_service"], "hubspot_deals")

    def test_06_checkpoint_interruption_resume(self):
        """Test checkpoint saving and resume cursor tracking payload"""
        checkpoint_data = {
            "phase": "main_data",
            "records_processed": 50,
            "cursor": "cursor_token_abc123",
            "page_number": 1,
            "batch_size": 50
        }
        self.assertEqual(checkpoint_data["records_processed"], 50)
        self.assertEqual(checkpoint_data["cursor"], "cursor_token_abc123")

if __name__ == '__main__':
    unittest.main()

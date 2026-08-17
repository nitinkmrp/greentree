import os
import sys
import json

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def load_env_file(env_path):
    """Simple .env file loader using python standard library"""
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip()

from services.hubspot_api_service import HubSpotAPIService

def run_api_test():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    load_env_file(env_path)

    access_token = os.environ.get('HUBSPOT_ACCESS_TOKEN') or os.environ.get('HUBSPOT_DEALS_API_TOKEN')
    
    if not access_token:
        print("[ERROR] HUBSPOT_ACCESS_TOKEN not found in .env file.")
        sys.exit(1)

    print("=" * 60)
    print("[START] Starting HubSpot Deals Live API Integration Test")
    print("=" * 60)
    print(f"Token Detected: {access_token[:10]}...{access_token[-4:]}")

    api_service = HubSpotAPIService(base_url="https://api.hubapi.com", timeout=30)

    # 1. Validate Token / Test Connection
    print("\n[1/2] Testing Connection & Token Scope Validation...")
    conn_result = api_service.test_connection(access_token)
    print(f"Connection Result: {json.dumps(conn_result, indent=2)}")

    if not conn_result.get('token_valid'):
        print("[FAIL] Token Validation Failed! Please check your HubSpot Private App Access Token.")
        sys.exit(1)

    print("[SUCCESS] Token successfully validated with HubSpot CRM API!")

    # 2. Fetch Deal Records
    print("\n[2/2] Requesting Deal Records from /crm/v3/objects/deals (limit=5)...")
    try:
        deals_data = api_service.get_deals(
            access_token=access_token,
            limit=5,
            properties=["dealname", "amount", "dealstage", "pipeline", "closedate", "createdate", "hs_lastmodifieddate"]
        )

        results = deals_data.get('results', [])
        paging = deals_data.get('paging', {})
        print(f"\n[SUCCESS] Total Deals Extracted in Batch: {len(results)}")

        if results:
            print("\n[DATA] Sample Extracted Deal:")
            print(json.dumps(results[0], indent=2))
        else:
            print("\n[INFO] Request succeeded! No deals found in this HubSpot account (0 records).")

        if paging:
            print(f"\n[PAGING] Paging Info (Next Cursor Token): {json.dumps(paging, indent=2)}")

        print("\n" + "=" * 60)
        print("[COMPLETE] Live HubSpot Deals API Test COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] API Request Exception: {e}")
        sys.exit(1)

if __name__ == '__main__':
    run_api_test()

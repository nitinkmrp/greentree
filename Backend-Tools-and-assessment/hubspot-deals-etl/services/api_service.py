import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
import time
import json
from loki_logger import get_logger, log_api_call


class APIService:
    """
    Service for interacting with HubSpot CRM API v3 (Deals Endpoint)
    """
    
    def __init__(self, base_url: str = "https://api.hubapi.com", test_delay_seconds: float = 0):
        self.base_url = base_url.rstrip('/')
        self.test_delay_seconds = test_delay_seconds
        self.logger = get_logger(__name__)
        self.session = requests.Session()
        
        # Set default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'HubSpot-Deals-Data-Extraction-Service/1.0'
        })
        
        self.logger.debug(
            "API service initialized",
            extra={
                'operation': 'api_service_init', 
                'base_url': base_url,
                'test_delay_seconds': test_delay_seconds
            }
        )
    
    def set_access_token(self, token: str):
        """Set the HubSpot API access token"""
        self.session.headers.update({
            'Authorization': f'Bearer {token}'
        })
        self.logger.debug("Access token set", extra={'operation': 'token_set'})
    
    def get_data(self, 
                 access_token: str,
                 limit: int = 100, 
                 after: Optional[str] = None,
                 properties: Optional[List[str]] = None,
                 **kwargs) -> Dict[str, Any]:
        """
        Get deal records from HubSpot CRM API v3 (/crm/v3/objects/deals)
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            self.logger.info(
                "Starting data retrieval from HubSpot API",
                extra={
                    'operation': 'get_data',
                    'limit': limit,
                    'has_cursor': after is not None,
                    'test_delay_seconds': self.test_delay_seconds
                }
            )
            
            if self.test_delay_seconds > 0:
                time.sleep(self.test_delay_seconds)
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            params = {
                'limit': min(limit, 100),
                'archived': 'false'
            }
            
            if after:
                params['after'] = after
                
            if properties:
                params['properties'] = ','.join(properties) if isinstance(properties, list) else properties
            else:
                params['properties'] = 'dealname,amount,dealstage,pipeline,closedate,createdate,hs_lastmodifieddate,hubspot_owner_id,hs_deal_stage_probability,description'
            
            for key, value in kwargs.items():
                if not key.startswith('_test_') and key not in ['scan_id', 'organization_id']:
                    params[key] = value
            
            url = f"{self.base_url}/crm/v3/objects/deals"
            
            response = self.session.get(url, params=params, headers=headers)
            
            # Handle rate limiting (429 Too Many Requests)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 2))
                self.logger.warning(
                    "HubSpot API Rate limited, retrying",
                    extra={
                        'operation': 'get_data',
                        'retry_after': retry_after,
                        'status_code': 429
                    }
                )
                time.sleep(retry_after)
                response = self.session.get(url, params=params, headers=headers)
            
            response.raise_for_status()
            
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            result = response.json()
            
            self.logger.info(
                "HubSpot deal data retrieved successfully",
                extra={
                    'operation': 'get_data',
                    'status_code': response.status_code,
                    'duration_ms': round(duration_ms, 2),
                    'result_count': len(result.get('results', [])),
                    'has_more': result.get('paging', {}).get('next') is not None
                }
            )
            
            log_api_call(
                self.logger,
                "hubspot_deals_get_data",
                method='GET',
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2)
            )
            
            return result
            
        except requests.exceptions.RequestException as e:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            self.logger.error(
                "Error fetching deal data from HubSpot",
                extra={
                    'operation': 'get_data',
                    'error': str(e),
                    'duration_ms': round(duration_ms, 2),
                    'status_code': getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
                },
                exc_info=True
            )
            
            log_api_call(
                self.logger,
                "hubspot_deals_get_data",
                method='GET',
                status_code=getattr(e.response, 'status_code', None) if hasattr(e, 'response') else 500,
                duration_ms=round(duration_ms, 2)
            )
            
            raise

    def validate_token(self, access_token: str) -> bool:
        """
        Validate HubSpot API access token by calling deals endpoint limit=1
        """
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            url = f"{self.base_url}/crm/v3/objects/deals"
            params = {'limit': 1}
            
            response = self.session.get(url, params=params, headers=headers)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def test_connection(self, access_token: str) -> Dict[str, Any]:
        """
        Test connection to HubSpot Deals API
        """
        is_valid = self.validate_token(access_token)
        return {
            'token_valid': is_valid,
            'api_reachable': is_valid,
            'data_accessible': is_valid,
            'error': None if is_valid else "Failed to validate HubSpot Private App token"
        }
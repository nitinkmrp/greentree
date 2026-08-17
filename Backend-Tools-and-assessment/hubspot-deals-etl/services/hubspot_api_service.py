import requests
import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from loki_logger import get_logger, log_api_call


class HubSpotAPIError(Exception):
    """Base exception for HubSpot API errors"""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class HubSpotAuthenticationError(HubSpotAPIError):
    """Raised on HTTP 401 Unauthorized (Invalid Token)"""
    pass


class HubSpotPermissionError(HubSpotAPIError):
    """Raised on HTTP 403 Forbidden (Missing Scope)"""
    pass


class HubSpotNotFoundError(HubSpotAPIError):
    """Raised on HTTP 404 Not Found"""
    pass


class HubSpotRateLimitError(HubSpotAPIError):
    """Raised on HTTP 429 Rate Limited (150 requests / 10s exceeded)"""
    pass


class HubSpotServerError(HubSpotAPIError):
    """Raised on HTTP 5xx Server Errors"""
    pass


class HubSpotAPIService:
    """
    Dedicated API Service for interacting with HubSpot CRM API v3 (Deals Endpoints)
    Implements authentication, pagination, 150 req/10s rate limiting, and structured logging.
    """

    def __init__(self, base_url: str = "https://api.hubapi.com", timeout: int = 30, test_delay_seconds: float = 0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.test_delay_seconds = test_delay_seconds
        self.logger = get_logger(__name__)
        self.session = requests.Session()
        
        # Configure standard HTTP headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'HubSpot-Deals-ETL-Service/1.0'
        })
        
        self.logger.info(
            "HubSpot API Service initialized",
            extra={
                'operation': 'hubspot_api_init', 
                'base_url': self.base_url,
                'timeout': self.timeout
            }
        )

    def set_access_token(self, access_token: str):
        """Configure Bearer Access Token authentication"""
        if not access_token:
            self.logger.error("Attempted to set an empty access token")
            raise ValueError("Access token cannot be empty")

        self.session.headers.update({
            'Authorization': f'Bearer {access_token}'
        })
        self.logger.debug("HubSpot access token attached to session headers", extra={'operation': 'set_access_token'})

    def get_deals(
        self, 
        access_token: str, 
        limit: int = 100, 
        after: Optional[str] = None, 
        properties: Optional[List[str]] = None,
        archived: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Fetch paginated deal records from HubSpot CRM API v3 (/crm/v3/objects/deals)
        with rate limit (150 req / 10s) management and robust error handling.
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            self.logger.info(
                "Requesting deal records from HubSpot API v3",
                extra={
                    'operation': 'get_deals',
                    'limit': limit,
                    'has_after_cursor': after is not None,
                    'archived': archived
                }
            )

            if self.test_delay_seconds > 0:
                self.logger.debug(f"Applying test delay of {self.test_delay_seconds} seconds")
                time.sleep(self.test_delay_seconds)

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            params = {
                'limit': min(limit, 100),
                'archived': str(archived).lower()
            }

            if after:
                params['after'] = after

            if properties:
                params['properties'] = ','.join(properties) if isinstance(properties, list) else properties
            else:
                params['properties'] = 'dealname,amount,dealstage,pipeline,closedate,createdate,hs_lastmodifieddate,hubspot_owner_id,hs_deal_stage_probability,description'

            for key, val in kwargs.items():
                if not key.startswith('_test_') and key not in ['scan_id', 'organization_id']:
                    params[key] = val

            url = f"{self.base_url}/crm/v3/objects/deals"

            response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)

            # Rate Limiting Handling (HubSpot 150 req/10s limit)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 2))
                self.logger.warning(
                    "HubSpot 150 req/10s rate limit exceeded. Retrying after delay...",
                    extra={'retry_after': retry_after, 'status_code': 429}
                )
                time.sleep(retry_after)
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)

            # Specific HTTP Error Handling
            if response.status_code == 401:
                self.logger.error("HubSpot Authentication Failed: Invalid Access Token")
                raise HubSpotAuthenticationError("Invalid or expired HubSpot Private App Access Token", status_code=401)
            
            elif response.status_code == 403:
                self.logger.error("HubSpot Permission Denied: Missing crm.objects.deals.read scope")
                raise HubSpotPermissionError("Insufficient scopes. Mandatory scope: crm.objects.deals.read", status_code=403)
                
            elif response.status_code == 404:
                self.logger.error("HubSpot Endpoint Not Found")
                raise HubSpotNotFoundError("Requested endpoint /crm/v3/objects/deals not found", status_code=404)

            elif response.status_code >= 500:
                self.logger.error(f"HubSpot Server Error ({response.status_code})")
                raise HubSpotServerError(f"HubSpot server returned error status {response.status_code}", status_code=response.status_code)

            response.raise_for_status()

            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            data = response.json()
            results = data.get('results', [])

            self.logger.info(
                "HubSpot deal records retrieved successfully",
                extra={
                    'operation': 'get_deals',
                    'status_code': response.status_code,
                    'duration_ms': round(duration_ms, 2),
                    'results_count': len(results),
                    'has_more': data.get('paging', {}).get('next') is not None
                }
            )

            log_api_call(
                self.logger,
                "hubspot_get_deals",
                method='GET',
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2)
            )

            return data

        except requests.exceptions.RequestException as e:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            self.logger.error(
                "HTTP exception during HubSpot deals API call",
                extra={
                    'operation': 'get_deals',
                    'error': str(e),
                    'duration_ms': round(duration_ms, 2)
                },
                exc_info=True
            )
            raise HubSpotAPIError(f"HubSpot API request failed: {e}")

    def validate_token(self, access_token: str) -> bool:
        """
        Credential Validation Method: Validates access token against /crm/v3/objects/deals
        """
        self.logger.info("Validating HubSpot access token credentials...")
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            url = f"{self.base_url}/crm/v3/objects/deals"
            response = self.session.get(url, params={'limit': 1}, headers=headers, timeout=self.timeout)
            
            if response.status_code == 200:
                self.logger.info("Credential validation successful: Token is valid")
                return True
            else:
                self.logger.warning(f"Credential validation failed with status code {response.status_code}")
                return False

        except Exception as e:
            self.logger.error("Credential validation failed due to network error", extra={'error': str(e)})
            return False

    def test_connection(self, access_token: str) -> Dict[str, Any]:
        """
        Comprehensive Connection Test Method
        """
        self.logger.info("Testing full connection to HubSpot Deals API")
        is_valid = self.validate_token(access_token)
        return {
            'token_valid': is_valid,
            'api_reachable': is_valid,
            'service': 'hubspot_deals',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

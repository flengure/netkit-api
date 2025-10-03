"""
OIDC/OAuth2 token validation with JWKS support

Supports OpenID Connect providers like:
- Authentik
- Auth0
- Keycloak
- Azure AD
- Google Identity
- Any OIDC-compliant provider
"""

import logging
import time
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin
import requests
import jwt
from jwt import PyJWKClient
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OIDCConfig:
    """OIDC provider configuration"""
    issuer: str
    audience: Optional[str] = None
    jwks_uri: Optional[str] = None
    required_scopes: Optional[List[str]] = None
    cache_ttl: int = 3600  # JWKS cache TTL in seconds

    def __post_init__(self):
        """Auto-discover JWKS URI if not provided"""
        if not self.jwks_uri:
            # Try standard OIDC discovery endpoint
            discovery_url = urljoin(self.issuer.rstrip('/') + '/', '.well-known/openid-configuration')
            try:
                response = requests.get(discovery_url, timeout=5)
                response.raise_for_status()
                config = response.json()
                self.jwks_uri = config.get('jwks_uri')
                logger.info(f"Auto-discovered JWKS URI: {self.jwks_uri}")
            except Exception as e:
                logger.warning(f"Failed to auto-discover JWKS URI from {discovery_url}: {e}")
                # Fallback to common pattern
                self.jwks_uri = urljoin(self.issuer.rstrip('/') + '/', 'protocol/openid-connect/certs')
                logger.info(f"Using fallback JWKS URI: {self.jwks_uri}")


class OIDCValidator:
    """
    Validate OIDC/OAuth2 access tokens using JWKS

    Features:
    - JWKS public key validation (no shared secrets needed)
    - Automatic key rotation support via JWKS endpoint
    - Token expiration validation
    - Issuer validation
    - Audience validation (optional)
    - Scope validation (optional)
    - Key caching with TTL

    Example usage:
        config = OIDCConfig(
            issuer="https://auth.u.tomage.net/application/o/netkit/",
            audience="netkit-api",
            required_scopes=["netkit.exec"]
        )
        validator = OIDCValidator(config)

        # Validate token from Authorization header
        payload = validator.validate_token("Bearer eyJ...")
        if payload:
            print(f"Valid token for subject: {payload['sub']}")
    """

    def __init__(self, config: OIDCConfig):
        self.config = config
        self.jwks_client = None

        if config.jwks_uri:
            try:
                self.jwks_client = PyJWKClient(
                    config.jwks_uri,
                    cache_keys=True,
                    max_cached_keys=10,
                    lifespan=config.cache_ttl
                )
                logger.info(f"OIDC validator initialized for issuer: {config.issuer}")
            except Exception as e:
                logger.error(f"Failed to initialize JWKS client: {e}")
                self.jwks_client = None
        else:
            logger.error(f"No JWKS URI available for issuer: {config.issuer}")

    def validate_token(self, auth_header: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Validate OIDC access token from Authorization header

        Args:
            auth_header: Authorization header value (e.g., "Bearer eyJ...")

        Returns:
            Token payload if valid, None otherwise
        """
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        if not self.jwks_client:
            logger.error("JWKS client not initialized")
            return None

        token = auth_header.split(" ", 1)[1]

        try:
            # Get signing key from JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            # Decode and validate token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "ES256"],  # Common OIDC algorithms
                issuer=self.config.issuer,
                audience=self.config.audience,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_iss": True,
                    "verify_aud": self.config.audience is not None,
                    "require_exp": True,
                }
            )

            # Validate scopes if required
            if self.config.required_scopes:
                token_scopes = self._get_scopes(payload)
                if not self._has_required_scopes(token_scopes, self.config.required_scopes):
                    missing = set(self.config.required_scopes) - set(token_scopes)
                    logger.warning(f"Token missing required scopes: {missing}")
                    return None

            logger.info(f"Valid OIDC token for subject: {payload.get('sub', 'unknown')}")
            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("OIDC token expired")
            return None
        except jwt.InvalidIssuerError:
            logger.warning(f"Invalid issuer (expected: {self.config.issuer})")
            return None
        except jwt.InvalidAudienceError:
            logger.warning(f"Invalid audience (expected: {self.config.audience})")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid OIDC token: {e}")
            return None
        except Exception as e:
            logger.error(f"OIDC token validation error: {e}", exc_info=True)
            return None

    def _get_scopes(self, payload: Dict[str, Any]) -> List[str]:
        """Extract scopes from token payload"""
        # Try different scope claim formats
        if "scope" in payload:
            # Space-separated string (OAuth2 standard)
            if isinstance(payload["scope"], str):
                return payload["scope"].split()
            # List format (some providers)
            elif isinstance(payload["scope"], list):
                return payload["scope"]

        # Alternative: "scopes" claim
        if "scopes" in payload:
            if isinstance(payload["scopes"], list):
                return payload["scopes"]

        return []

    def _has_required_scopes(self, token_scopes: List[str], required: List[str]) -> bool:
        """Check if token has all required scopes"""
        return all(scope in token_scopes for scope in required)

    def is_enabled(self) -> bool:
        """Check if validator is properly configured"""
        return self.jwks_client is not None


class MultiOIDCValidator:
    """
    Support multiple OIDC providers simultaneously

    Example:
        validators = MultiOIDCValidator([
            OIDCConfig(issuer="https://auth.company.com/", required_scopes=["netkit.exec"]),
            OIDCConfig(issuer="https://accounts.google.com", audience="client-id"),
        ])

        payload = validators.validate_token("Bearer eyJ...")
    """

    def __init__(self, configs: List[OIDCConfig]):
        self.validators = [OIDCValidator(config) for config in configs]
        enabled = sum(1 for v in self.validators if v.is_enabled())
        logger.info(f"Multi-OIDC validator initialized with {enabled}/{len(configs)} providers")

    def validate_token(self, auth_header: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Try to validate token against all configured providers

        Returns payload from first successful validation
        """
        for validator in self.validators:
            if not validator.is_enabled():
                continue

            payload = validator.validate_token(auth_header)
            if payload:
                return payload

        return None

    def is_enabled(self) -> bool:
        """Check if any validator is enabled"""
        return any(v.is_enabled() for v in self.validators)

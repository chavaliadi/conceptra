import os
import base64
import logging
from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)

def get_clerk_domain() -> str:
    """Resolve Clerk domain from environment variables."""
    # 1. Check if direct Clerk API URL is set
    clerk_api_url = os.getenv("CLERK_API_URL")
    if clerk_api_url:
        return clerk_api_url.replace("https://", "").replace("http://", "").split("/")[0]

    # 2. Check publishable key
    pub_key = os.getenv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY")
    if pub_key:
        try:
            parts = pub_key.split('_')
            if len(parts) >= 3:
                b64_part = parts[-1]
                # Add padding
                b64_part += '=' * (-len(b64_part) % 4)
                decoded = base64.b64decode(b64_part).decode('utf-8')
                return decoded.rstrip('$')
        except Exception as e:
            logger.error(f"Failed to parse Clerk domain from publishable key: {e}")

    # Fallback default (from environment values)
    return "immune-crane-96.clerk.accounts.dev"

CLERK_DOMAIN = get_clerk_domain()
CLERK_JWKS_URL = f"https://{CLERK_DOMAIN}/.well-known/jwks.json"
CLERK_ISSUER = f"https://{CLERK_DOMAIN}"

# PyJWT JWK Client for key retrieval and caching
jwks_client = jwt.PyJWKClient(CLERK_JWKS_URL)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[dict]:
    """
    FastAPI dependency to verify Clerk JWT and return user claims.
    If auth is optional on a route, it returns None.
    If credentials are provided but invalid, raises HTTP 401.
    """
    if not credentials:
        return None

    token = credentials.credentials
    try:
        # Get signing key from Clerk's JWKS
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Verify and decode
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=CLERK_ISSUER,
            options={"verify_exp": True, "verify_aud": False}
        )
        return payload
    except jwt.ExpiredSignatureError as e:
        logger.warning(f"Clerk JWT expired: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid Clerk JWT: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Error validating Clerk JWT: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_required_user(
    current_user: Optional[dict] = Depends(get_current_user)
) -> dict:
    """Dependency requiring user to be logged in."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user

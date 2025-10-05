"""
netkit-api v2.0 - Remote operations toolkit

Unified API for SSH execution + network diagnostics, scanning, and security auditing.
Maintains backward compatibility with ssh-api v1.x /run endpoint.
"""

import os
import sys
import jwt
import hmac
import logging
from fastapi import FastAPI, Request, HTTPException, Header, status
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import uvicorn

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from executors import get_tool_registry
from rate_limiter import RateLimiter
from target_validator import TargetValidator
from job_manager import JobManager
from capabilities import get_capabilities_info
from config_loader import load_config
from oidc_validator import OIDCConfig, MultiOIDCValidator

app = FastAPI(
    title="netkit-api",
    description="""
Remote operations toolkit for network diagnostics, scanning, and security auditing.

## Authentication

Supports three authentication methods (can be enabled simultaneously):
- **API Key** - Simple key-based auth (X-API-Key header or ApiKey scheme)
- **JWT** - Shared secret token authentication
- **OIDC** - OAuth2/OpenID Connect (recommended for production)

## Two-Tier Security Model

**Private Instance (Full Capabilities):**
- Root user with CAP_NET_RAW + CAP_NET_ADMIN
- Full toolset: nmap -sS, traceroute, mtr, masscan
- Internal use only (localhost)

**Public Instance (Safe Mode):**
- Non-root with no capabilities
- Safe tools only: nmap -sT, dig, curl, whois
- For controlled public access

## Rate Limiting

All endpoints are rate-limited per IP, per API key, and globally.
Exceeding limits returns 429 Too Many Requests.
""",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "tools", "description": "Tool execution and discovery"},
        {"name": "jobs", "description": "Async job management"},
        {"name": "system", "description": "Health checks and statistics"}
    ],
    servers=[
        {"url": "http://localhost:8090", "description": "Local development"},
        {"url": "https://api.example.com", "description": "Production"}
    ]
)

# Add security schemes to OpenAPI spec
app.openapi_schema = None  # Reset to regenerate with custom security

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    from fastapi.openapi.utils import get_openapi

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=app.servers,
        tags=app.openapi_tags
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "ApiKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key authentication via X-API-Key header"
        },
        "ApiKeyAuth": {
            "type": "http",
            "scheme": "bearer",
            "description": "API key via Authorization: ApiKey <key>"
        },
        "BearerJWT": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token via Authorization: Bearer <token>"
        },
        "BearerOIDC": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "OIDC token via Authorization: Bearer <token>"
        }
    }

    # Add security to all endpoints (they're optional based on AUTH_ENABLED)
    for path in openapi_schema["paths"].values():
        for operation in path.values():
            if isinstance(operation, dict) and "operationId" in operation:
                operation["security"] = [
                    {"ApiKeyHeader": []},
                    {"ApiKeyAuth": []},
                    {"BearerJWT": []},
                    {"BearerOIDC": []}
                ]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== Configuration =====

# Load config from file (if present) + environment variables
config = load_config()

# Authentication
JWT_SECRET = config.get_string("jwt_secret", "JWT_SECRET", "")
API_KEYS = config.get_list("api_keys", "API_KEYS", [])

# OIDC Configuration
OIDC_ENABLED = config.get_bool("oidc_enabled", "OIDC_ENABLED", False)
OIDC_ISSUER = config.get_string("oidc_issuer", "OIDC_ISSUER", "")
OIDC_AUDIENCE = config.get_string("oidc_audience", "OIDC_AUDIENCE", "")
OIDC_JWKS_URI = config.get_string("oidc_jwks_uri", "OIDC_JWKS_URI", "")
OIDC_REQUIRED_SCOPES = config.get_list("oidc_required_scopes", "OIDC_REQUIRED_SCOPES", [])

# Initialize OIDC validator if enabled
oidc_validator = None
if OIDC_ENABLED and OIDC_ISSUER:
    try:
        oidc_config = OIDCConfig(
            issuer=OIDC_ISSUER,
            audience=OIDC_AUDIENCE or None,
            jwks_uri=OIDC_JWKS_URI or None,
            required_scopes=OIDC_REQUIRED_SCOPES if OIDC_REQUIRED_SCOPES else None
        )
        oidc_validator = MultiOIDCValidator([oidc_config])
        if oidc_validator.is_enabled():
            logger.info(f"OIDC authentication enabled for issuer: {OIDC_ISSUER}")
        else:
            logger.warning("OIDC enabled but validator failed to initialize")
            oidc_validator = None
    except Exception as e:
        logger.error(f"Failed to initialize OIDC validator: {e}")
        oidc_validator = None

# Enable auth if ANY method is configured
AUTH_ENABLED = bool(JWT_SECRET or API_KEYS or (oidc_validator and oidc_validator.is_enabled()))

if AUTH_ENABLED:
    auth_methods = []
    if JWT_SECRET:
        auth_methods.append("JWT")
    if API_KEYS:
        auth_methods.append("API Keys")
    if oidc_validator and oidc_validator.is_enabled():
        auth_methods.append("OIDC")
    logger.info(f"Authentication enabled: {', '.join(auth_methods)}")
    if JWT_SECRET and JWT_SECRET == "dev-secret":
        logger.warning("Using default JWT secret - this is insecure for production!")
else:
    logger.warning("Authentication DISABLED - all requests will be accepted")

SSH_DIR = os.path.expanduser(config.get_string("ssh_dir", "SSH_DIR", "~/.ssh"))
API_PORT = config.get_int("api_port", "API_PORT", 8090)

# Rate limiting
RATE_LIMIT_GLOBAL = config.get_int("rate_limit_global", "RATE_LIMIT_GLOBAL", 100)
RATE_LIMIT_PER_IP = config.get_int("rate_limit_per_ip", "RATE_LIMIT_PER_IP", 20)
RATE_LIMIT_PER_KEY = config.get_int("rate_limit_per_key", "RATE_LIMIT_PER_KEY", 50)

# Target validation (lists are merged: file + env)
SCAN_WHITELIST = config.get_list("scan_whitelist", "SCAN_WHITELIST", [])
SCAN_BLACKLIST = config.get_list("scan_blacklist", "SCAN_BLACKLIST", [])
ALLOW_PRIVATE_IPS = config.get_bool("allow_private_ips", "ALLOW_PRIVATE_IPS", False)

# Job management
MAX_CONCURRENT_JOBS = config.get_int("max_concurrent_jobs", "MAX_CONCURRENT_JOBS", 100)
JOB_CLEANUP_INTERVAL = config.get_int("job_cleanup_interval", "JOB_CLEANUP_INTERVAL", 3600)

# Request limits
MAX_REQUEST_SIZE = 1024 * 1024  # 1MB

# ===== Initialize components =====

rate_limiter = RateLimiter(
    global_limit=RATE_LIMIT_GLOBAL,
    per_ip_limit=RATE_LIMIT_PER_IP,
    per_key_limit=RATE_LIMIT_PER_KEY
)

target_validator = TargetValidator(
    whitelist=SCAN_WHITELIST or None,
    blacklist=SCAN_BLACKLIST or None,
    allow_private=ALLOW_PRIVATE_IPS
)

job_manager = JobManager(
    max_jobs=MAX_CONCURRENT_JOBS,
    cleanup_interval=JOB_CLEANUP_INTERVAL
)

# Tool registry
TOOL_REGISTRY = get_tool_registry(target_validator)

logger.info(f"netkit-api initialized with {len(TOOL_REGISTRY)} tools")

# ===== Pydantic models =====

class ExecRequest(BaseModel):
    command: Optional[str] = Field(None, description="Command to execute (tool name + args as string, e.g. 'dig google.com +short')")
    tool: Optional[str] = Field(None, description="Tool name (if using 'args' parameter)")
    args: Optional[list] = Field(None, description="Command arguments as list (requires 'tool' parameter)")
    timeout: Optional[int] = Field(None, description="Execution timeout in seconds")
    async_exec: Optional[bool] = Field(False, alias="async", description="Execute asynchronously")
    output_format: Optional[str] = Field("text", description="Output format")
    host: Optional[str] = Field(None, description="For SSH: target hostname")
    user: Optional[str] = Field(None, description="For SSH: username")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "examples": [
                {
                    "command": "dig google.com +short"
                },
                {
                    "tool": "dig",
                    "args": ["google.com", "+short"]
                },
                {
                    "tool": "nmap",
                    "command": "-sS -p 80,443 example.com"
                }
            ]
        }

class JobResponse(BaseModel):
    job_id: str
    status: str
    tool: str

# ===== Helper functions =====

def verify_jwt(auth_header: Optional[str]) -> Optional[Dict[str, Any]]:
    """Verify JWT token from Authorization header"""
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        logger.info(f"Valid JWT token for subject: {payload.get('sub', 'unknown')}")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError:
        logger.warning("Invalid JWT token")
        return None
    except Exception as e:
        logger.error(f"JWT verification error: {e}")
        return None


def verify_api_key(request: Request, x_api_key: Optional[str], authorization: Optional[str]) -> Optional[str]:
    """Verify API key from request headers, return key if valid"""
    key = x_api_key
    if not key and authorization and authorization.startswith("ApiKey "):
        key = authorization.split(" ", 1)[1]

    if not key or not API_KEYS:
        return None

    for valid in API_KEYS:
        if hmac.compare_digest(key, valid):
            logger.info("Valid API key authentication")
            return key

    logger.warning(f"Invalid API key attempted from {request.client.host}")
    return None


def check_auth(request: Request, authorization: Optional[str], x_api_key: Optional[str]) -> tuple[bool, Optional[str]]:
    """
    Check authentication (OIDC, JWT, or API key)

    Priority order:
    1. OIDC Bearer token (if enabled)
    2. JWT Bearer token (if configured)
    3. API Key (if configured)

    Returns:
        (authenticated: bool, api_key: Optional[str])
    """
    # Try OIDC first (if enabled)
    if oidc_validator and oidc_validator.is_enabled():
        oidc_payload = oidc_validator.validate_token(authorization)
        if oidc_payload:
            return (True, None)

    # Try JWT (shared secret)
    jwt_valid = verify_jwt(authorization)
    if jwt_valid:
        return (True, None)

    # Try API key
    api_key = verify_api_key(request, x_api_key, authorization)

    return (api_key is not None, api_key)


# ===== Middleware =====

@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """Security checks and headers"""
    # Check request size
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_SIZE:
        logger.warning(f"Request too large: {content_length} bytes from {request.client.host}")
        return JSONResponse(
            status_code=413,
            content={"error": "Request too large"}
        )

    response = await call_next(request)

    # Add security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    return response


# ===== API Endpoints =====

@app.get("/healthz", tags=["system"])
async def healthz():
    """Health check with capability reporting"""
    return {
        "ok": True,
        "version": "2.0.0",
        "service": "netkit-api",
        "capabilities": get_capabilities_info()
    }


@app.get("/tools", tags=["tools"])
async def list_tools():
    """List all available tools with status"""
    tools = {}

    for name, executor in TOOL_REGISTRY.items():
        tools[name] = {
            "name": name,
            "description": executor.DESCRIPTION,
            "available": executor.is_available(),
            "requires_capability": executor.REQUIRES_CAP_NET_RAW
        }

    return {"tools": tools}


@app.get("/tools/{tool_name}", tags=["tools"])
async def get_tool_info(tool_name: str):
    """Get detailed information about a specific tool"""
    if tool_name not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown tool: {tool_name}")

    executor = TOOL_REGISTRY[tool_name]

    return {
        "name": tool_name,
        "description": executor.DESCRIPTION,
        "available": executor.is_available(),
        "requires_capability": executor.REQUIRES_CAP_NET_RAW,
        "max_timeout": executor.MAX_TIMEOUT,
        "min_timeout": executor.MIN_TIMEOUT,
        "default_timeout": executor.DEFAULT_TIMEOUT
    }


@app.post("/exec", tags=["tools"])
async def exec_tool(
    request: Request,
    body: ExecRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Execute any registered tool

    Supports both synchronous and asynchronous execution.

    **Three ways to specify the command:**

    1. Using `command` (full command string):
       ```json
       {"command": "dig google.com +short"}
       ```

    2. Using `tool` + `args` array:
       ```json
       {"tool": "dig", "args": ["google.com", "+short"]}
       ```

    3. Using `tool` + `command` string:
       ```json
       {"tool": "dig", "command": "google.com +short"}
       ```

    **For async execution:**
    ```json
    {"command": "nmap -sT -p 1-65535 example.com", "async": true}
    ```
    """
    # Authentication (if enabled)
    api_key = None
    if AUTH_ENABLED:
        authenticated, api_key = check_auth(request, authorization, x_api_key)
        if not authenticated:
            logger.warning(f"Unauthorized access attempt from {request.client.host}")
            raise HTTPException(status_code=401, detail="Unauthorized")

    # Rate limiting
    allowed, reason = rate_limiter.check_limit(
        ip=request.client.host,
        api_key=api_key
    )
    if not allowed:
        logger.warning(f"Rate limit exceeded from {request.client.host}: {reason}")
        raise HTTPException(status_code=429, detail=reason)

    # Determine tool name and build execution params
    tool_name = None
    exec_params = body.model_dump(by_alias=True, exclude_none=True)

    # Case 1: Full command string (e.g., "dig google.com +short")
    if body.command and not body.tool:
        # Parse tool name from command
        import shlex
        try:
            parts = shlex.split(body.command)
            if not parts:
                raise HTTPException(status_code=400, detail="Empty command")

            tool_name = parts[0]
            if tool_name not in TOOL_REGISTRY:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown tool: {tool_name}. See /tools for available tools"
                )

            # Rebuild params with args for the executor
            exec_params = {
                "args": parts[1:] if len(parts) > 1 else [],
                "timeout": body.timeout,
                "output_format": body.output_format or "text",
                "async": body.async_exec
            }
            # Add SSH-specific params if present
            if body.host:
                exec_params["host"] = body.host
            if body.user:
                exec_params["user"] = body.user

        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid command syntax: {e}")

    # Case 2: Tool + args/command (e.g., {"tool": "dig", "args": [...]})
    elif body.tool:
        tool_name = body.tool
        if tool_name not in TOOL_REGISTRY:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown tool: {tool_name}. See /tools for available tools"
            )
        # exec_params already has everything from model_dump

    # Case 3: Neither format provided
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either 'command' (full command string) or 'tool' (with args/command)"
        )

    executor = TOOL_REGISTRY[tool_name]

    # Check if tool is available
    if not executor.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"Tool '{tool_name}' is not installed or not available"
        )

    # Log execution
    logger.info(f"Tool execution request: {tool_name} from {request.client.host}")

    # Async execution option
    if body.async_exec:
        try:
            job_id = job_manager.create_job(
                executor_fn=lambda p: executor.execute(p),
                params=exec_params,
                metadata={
                    "tool": tool_name,
                    "ip": request.client.host,
                    "api_key": api_key[:8] + "..." if api_key else None
                }
            )
            logger.info(f"Async job created: {job_id} for tool {tool_name}")
            return JSONResponse(
                status_code=202,
                content={
                    "job_id": job_id,
                    "status": "pending",
                    "tool": tool_name
                }
            )

        except RuntimeError as e:
            logger.error(f"Job creation failed: {e}")
            raise HTTPException(status_code=503, detail=str(e))

    # Sync execution
    try:
        result = executor.execute(exec_params)
        return result

    except PermissionError as e:
        logger.error(f"Permission error for {tool_name}: {e}")
        raise HTTPException(status_code=403, detail=str(e))

    except ValueError as e:
        logger.error(f"Validation error for {tool_name}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except RuntimeError as e:
        logger.error(f"Runtime error for {tool_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(f"Unexpected error for {tool_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/jobs/{job_id}", tags=["jobs"])
async def get_job(
    request: Request,
    job_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """Get status and result of async job"""
    # Authentication
    authenticated, _ = check_auth(request, authorization, x_api_key)
    if not authenticated:
        raise HTTPException(status_code=401, detail="Unauthorized")

    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@app.delete("/jobs/{job_id}", tags=["jobs"])
async def delete_job(
    request: Request,
    job_id: str,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """Delete/cancel async job"""
    # Authentication
    authenticated, _ = check_auth(request, authorization, x_api_key)
    if not authenticated:
        raise HTTPException(status_code=401, detail="Unauthorized")

    deleted = job_manager.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"message": "Job deleted", "job_id": job_id}


@app.get("/jobs", tags=["jobs"])
async def list_jobs(
    request: Request,
    status: Optional[str] = None,
    limit: int = 100,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """List all jobs (optionally filtered by status)"""
    # Authentication
    authenticated, _ = check_auth(request, authorization, x_api_key)
    if not authenticated:
        raise HTTPException(status_code=401, detail="Unauthorized")

    jobs = job_manager.list_jobs(status=status, limit=limit)

    return {
        "jobs": jobs,
        "count": len(jobs)
    }


@app.get("/stats", tags=["system"])
async def get_stats(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """Get API statistics (rate limits, jobs, etc.)"""
    # Authentication (if enabled)
    if AUTH_ENABLED:
        authenticated, _ = check_auth(request, authorization, x_api_key)
        if not authenticated:
            raise HTTPException(status_code=401, detail="Unauthorized")

    return {
        "rate_limiter": rate_limiter.get_stats(),
        "job_manager": job_manager.get_stats(),
        "tools": {
            "total": len(TOOL_REGISTRY),
            "available": sum(1 for e in TOOL_REGISTRY.values() if e.is_available())
        }
    }


if __name__ == "__main__":
    logger.info(f"Starting netkit-api v2.0 on port {API_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)

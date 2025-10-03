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

app = FastAPI(
    title="netkit-api",
    description="Remote operations toolkit - SSH execution + network diagnostics, scanning, and security auditing",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== Configuration =====

# Authentication
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
if JWT_SECRET == "dev-secret":
    logger.warning("Using default JWT secret - this is insecure for production!")

API_KEYS = [k.strip() for k in os.environ.get("API_KEYS", "").split(",") if k.strip()]
SSH_DIR = os.path.expanduser(os.environ.get("SSH_DIR", "~/.ssh"))
API_PORT = int(os.environ.get("API_PORT", "8090"))

# Rate limiting
RATE_LIMIT_GLOBAL = int(os.environ.get("RATE_LIMIT_GLOBAL", "100"))
RATE_LIMIT_PER_IP = int(os.environ.get("RATE_LIMIT_PER_IP", "20"))
RATE_LIMIT_PER_KEY = int(os.environ.get("RATE_LIMIT_PER_KEY", "50"))

# Target validation
SCAN_WHITELIST = [x.strip() for x in os.environ.get("SCAN_WHITELIST", "").split(",") if x.strip()]
SCAN_BLACKLIST = [x.strip() for x in os.environ.get("SCAN_BLACKLIST", "").split(",") if x.strip()]
ALLOW_PRIVATE_IPS = os.environ.get("ALLOW_PRIVATE_IPS", "false").lower() == "true"

# Job management
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "100"))
JOB_CLEANUP_INTERVAL = int(os.environ.get("JOB_CLEANUP_INTERVAL", "3600"))

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
    Check authentication (JWT or API key)

    Returns:
        (authenticated: bool, api_key: Optional[str])
    """
    jwt_valid = verify_jwt(authorization)
    api_key = verify_api_key(request, x_api_key, authorization)

    return (jwt_valid is not None or api_key is not None), api_key


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

@app.get("/healthz")
async def healthz():
    """Health check with capability reporting"""
    return {
        "ok": True,
        "version": "2.0.0",
        "service": "netkit-api",
        "capabilities": get_capabilities_info()
    }


@app.get("/tools")
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


@app.get("/tools/{tool_name}")
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


@app.post("/exec")
async def exec_tool(
    request: Request,
    body: ExecRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Execute any registered tool

    Supports both synchronous and asynchronous execution.

    **Two ways to specify the command:**

    1. Using `command` (full command string):
       ```json
       {"command": "dig google.com +short"}
       ```

    2. Using `tool` + `args` (or `command`):
       ```json
       {"tool": "dig", "args": ["google.com", "+short"]}
       {"tool": "dig", "command": "google.com +short"}
       ```
    """
    # Authentication
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


@app.get("/jobs/{job_id}")
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


@app.delete("/jobs/{job_id}")
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


@app.get("/jobs")
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


@app.get("/stats")
async def get_stats(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """Get API statistics (rate limits, jobs, etc.)"""
    # Authentication
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

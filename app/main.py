import os
import logging
import jwt
from fastapi import FastAPI, HTTPException, Depends, Header, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from app.agents.finsense_agent import run_agent

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Supabase Auth Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# Initialize JWKS client if SUPABASE_URL is provided for asymmetric (ES256/RS256) validation
jwks_client = None
if SUPABASE_URL:
    jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    try:
        jwks_client = jwt.PyJWKClient(jwks_url)
        logger.info(f"Initialized Supabase JWKS client for URL: {jwks_url}")
    except Exception as e:
        logger.error(f"Failed to initialize JWKS client: {e}")

if not SUPABASE_JWT_SECRET:
    logger.warning(
        "WARNING: SUPABASE_JWT_SECRET environment variable is not set. "
        "The backend will run in secure-bypass development mode (authentication is bypassed)."
    )


app = FastAPI(
    title="FinSense AI Backend",
    description="India-specific personal finance agent backend",
    version="1.0.0"
)

# CORS Configuration - Allow all origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for validation
class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="The personal finance query (between 10 and 500 characters)"
    )

class QueryResponse(BaseModel):
    answer: str
    recommendation: str
    key_points: list[str]
    sources: list[dict]
    tools_used: list[str]
    calculations: dict | None
    disclaimer: str
    last_updated: str

# Authentication Dependency
async def get_current_user(authorization: str = Header(None)):
    """
    Dependency to extract and verify the Supabase JWT.
    If SUPABASE_JWT_SECRET is not configured, it runs in bypass mode.
    """
    if not SUPABASE_JWT_SECRET:
        # Bypass mode: return a dummy user payload
        return {
            "email": "dev@finsense.ai",
            "user_metadata": {}
        }

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    
    token = authorization.split(" ")[1]
    try:
        # Check token header to find the algorithm
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg", "HS256")
        
        if alg == "HS256":
            # Decode and verify Supabase JWT symmetrically
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated"
            )
        else:
            # Decode and verify Supabase JWT asymmetrically using JWKS signing key
            if not jwks_client:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="JWKS client is not initialized for asymmetric token decoding"
                )
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated"
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )


@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest, current_user: dict = Depends(get_current_user)):
    """
    Endpoint to submit personal finance queries.
    Requires a valid JWT token. Uses LangGraph agent to process.
    """
    user_email = current_user.get("email", "unknown")
    logger.info(f"Received query from {user_email}: '{request.query}'")
    try:
        response_data = await run_agent(request.query)
        
        # Log request and tools used
        tools_used = response_data.get("tools_used", [])
        logger.info(f"Successfully processed query for {user_email}. Tools used: {tools_used}")
        
        return response_data
    except Exception as e:
        logger.error(f"Error executing agent for query '{request.query}': {e}", exc_info=True)
        return QueryResponse(
            answer=f"Sorry, an unexpected error occurred while processing your request: {str(e)}",
            recommendation="Please try again later or consult a financial professional.",
            key_points=["Error encountered during processing"],
            sources=[],
            tools_used=[],
            calculations=None,
            disclaimer="This is for informational purposes only. Consult a financial advisor.",
            last_updated="2025-26"
        )

@app.get("/api/config")
async def config_endpoint():
    """
    Endpoint to share public Supabase keys with the client-side JavaScript.
    """
    return {
        "supabaseUrl": SUPABASE_URL,
        "supabaseAnonKey": SUPABASE_ANON_KEY
    }

@app.get("/api/health")
async def health_endpoint():
    """
    Health check endpoint.
    """
    return {
        "status": "ok",
        "model": "llama-3.3-70b-versatile"
    }

# Serving landing.html at the root path
@app.get("/")
async def read_index():
    return FileResponse("app/landing.html")

# Mounting other app assets and pages under root static path
app.mount("/", StaticFiles(directory="app"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

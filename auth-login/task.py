import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import create_client

# ---------- Stage 0: setup ----------
# Read SUPABASE_URL and SUPABASE_KEY (anon key) from the git-ignored .env file.
load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
print("Server running and connected to Supabase")

app = FastAPI(title="Auth API", description="Supabase Auth + protected routes")


# Make every error look like {"error": "..."} instead of FastAPI's default {"detail": ...}
@app.exception_handler(HTTPException)
async def error_format(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})


# ---------- Stage 1: sign up and log in ----------
# Fields are Optional so a missing field reaches our code and we return 400 ourselves
# (otherwise FastAPI would answer 422 before our code runs).
class Credentials(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None


def require_fields(body: Credentials):
    if not body.email or not body.password or not body.email.strip() or not body.password.strip():
        raise HTTPException(status_code=400, detail="Email and password are required")


@app.post("/auth/signup", status_code=201, summary="Create a new account", tags=["auth"])
def signup(body: Credentials):
    require_fields(body)
    try:
        result = supabase.auth.sign_up({"email": body.email, "password": body.password})
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    user = result.user
    return {"id": str(user.id), "email": user.email, "created_at": str(user.created_at)}


@app.post("/auth/login", summary="Log in and get a JWT", tags=["auth"])
def login(body: Credentials):
    require_fields(body)
    try:
        result = supabase.auth.sign_in_with_password({"email": body.email, "password": body.password})
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid login credentials")
    if result.session is None:
        raise HTTPException(status_code=401, detail="Invalid login credentials")
    return {
        "access_token": result.session.access_token,
        "refresh_token": result.session.refresh_token,
    }


# ---------- Stage 2: public route ----------
@app.get("/public/info", summary="Public info (no auth)", tags=["public"])
def public_info():
    return {"message": "Welcome stranger! This info is public."}


# ---------- Stages 3 + 4: the guard (a FastAPI dependency) ----------
# auto_error=False lets us return our own 401 JSON instead of FastAPI's default.
# HTTPBearer also makes the "Authorize" padlock appear in /docs (Stage 5).
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)):
    # Missing header, wrong scheme (not "Bearer"), or empty token -> 401
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Access token required")
    token = credentials.credentials
    try:
        # Network call to Supabase: it checks signature and expiry for us
        result = supabase.auth.get_user(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if result is None or result.user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return result.user


# Both routes below reuse the same guard, with no new auth code.
@app.get("/protected/profile", summary="Your profile (auth required)", tags=["protected"])
def profile(user=Depends(get_current_user)):
    return {"id": str(user.id), "email": user.email, "created_at": str(user.created_at)}


@app.get("/protected/dashboard", summary="Dashboard (auth required)", tags=["protected"])
def dashboard(user=Depends(get_current_user)):
    return {"message": f"Welcome back, {user.email}!"}


@app.post("/auth/logout", status_code=204, summary="Log out (auth required)", tags=["auth"])
def logout(user=Depends(get_current_user)):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass  # the session may already be gone; logout should still succeed
    return Response(status_code=204)
"""Authentication for the admin API: a tenant API key sent as 'Authorization: Bearer <key>'."""
import hashlib
import secrets

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db, repositories as repo
from .errors import Unauthorized

bearer = HTTPBearer(auto_error=False, description="Your tenant API key")


def new_api_key():
    return "fr_" + secrets.token_urlsafe(24)


def hash_key(api_key):
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def current_tenant(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    """Dependency: every admin route that names it is protected, and gets the tenant row."""
    if creds is None or not creds.credentials:
        raise Unauthorized("Missing API key", headers={"WWW-Authenticate": "Bearer"})
    with db.session() as conn:
        tenant = repo.get_tenant_by_key_hash(conn, hash_key(creds.credentials))
    if tenant is None:
        raise Unauthorized("Invalid API key", headers={"WWW-Authenticate": "Bearer"})
    return dict(tenant)

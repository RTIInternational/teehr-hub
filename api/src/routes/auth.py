from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..auth import AuthIdentity, get_admin_identity, get_request_identity

router = APIRouter(prefix="/auth", tags=["Auth"])


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=list)


@router.get("/me")
async def me(identity: AuthIdentity = Depends(get_request_identity)):
    return {
        "subject": identity.subject,
        "auth_type": identity.auth_type,
        "roles": identity.roles,
        "scopes": identity.scopes,
        "authenticated": identity.is_authenticated,
    }


@router.get("/api-keys")
async def list_api_keys(
    request: Request,
    identity: AuthIdentity = Depends(get_admin_identity),
):
    keys = await request.app.state.api_key_store.list_keys()
    return {"items": keys}


@router.post("/api-keys", status_code=201)
async def create_api_key(
    request: Request,
    payload: ApiKeyCreateRequest,
    identity: AuthIdentity = Depends(get_admin_identity),
):
    created = await request.app.state.api_key_store.create_key(
        owner_sub=identity.subject,
        name=payload.name,
        scopes=payload.scopes,
    )
    return created


@router.delete("/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    request: Request,
    identity: AuthIdentity = Depends(get_admin_identity),
):
    revoked = await request.app.state.api_key_store.revoke_key(identity.subject, key_id)
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")

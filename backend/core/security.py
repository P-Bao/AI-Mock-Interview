from fastapi import Header, HTTPException, status


async def optional_user_id_header(x_user_id: str | None = Header(default=None)) -> str | None:
    return x_user_id


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if x_api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

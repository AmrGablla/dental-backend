"""Authentication endpoints for the dental backend API."""

from datetime import timedelta

from dental_backend_common.audit import audit_logger
from dental_backend_common.auth import (
    ClientCredentials,
    Token,
    User,
    authenticate_client,
    authenticate_user,
    create_access_token,
    create_refresh_token,
)
from dental_backend_common.config import get_settings
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from dental_backend.api.dependencies import get_current_active_user

# Get settings
settings = get_settings()

# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token", response_model=Token)
async def login_for_access_token(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends()
) -> Token:
    """OAuth2 password flow for obtaining access token."""
    user = authenticate_user(form_data.username, form_data.password)

    if not user:
        # Log failed login attempt
        audit_logger.log_login_failure(
            username=form_data.username,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            error="Invalid credentials",
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Log successful login
    audit_logger.log_login_success(
        user=user,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
    )

    # Create tokens
    access_token_expires = timedelta(
        minutes=settings.security.access_token_expire_minutes
    )
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role.value},
        expires_delta=access_token_expires,
    )

    refresh_token = create_refresh_token(
        data={"sub": user.id, "username": user.username, "role": user.role.value}
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.security.access_token_expire_minutes * 60,
    )


@router.post("/client-token", response_model=Token)
async def get_client_token(request: Request, credentials: ClientCredentials) -> Token:
    """OAuth2 client credentials flow for service-to-service authentication."""
    user = authenticate_client(credentials.client_id, credentials.client_secret)

    if not user:
        # Log failed client authentication
        audit_logger.log_event(
            event_type="client_authentication_failure",
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            action="client_auth",
            outcome="failure",
            error_message="Invalid client credentials",
            details={"client_id": credentials.client_id},
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create tokens
    access_token_expires = timedelta(
        minutes=settings.security.access_token_expire_minutes
    )
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role.value},
        expires_delta=access_token_expires,
    )

    refresh_token = create_refresh_token(
        data={"sub": user.id, "username": user.username, "role": user.role.value}
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.security.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=Token)
async def refresh_access_token(request: Request, refresh_token: str) -> Token:
    """Refresh access token using refresh token."""
    from dental_backend_common.auth import TokenType, verify_token

    # Verify refresh token
    token_data = verify_token(refresh_token)
    if not token_data or token_data.token_type != TokenType.REFRESH:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user
    if token_data.username == "admin":
        from dental_backend_common.auth import MOCK_USERS

        user = MOCK_USERS["admin"]
    elif token_data.username == "operator":
        from dental_backend_common.auth import MOCK_USERS

        user = MOCK_USERS["operator"]
    elif token_data.username == "service":
        from dental_backend_common.auth import MOCK_USERS

        user = MOCK_USERS["service"]
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Log token refresh
    audit_logger.log_event(
        event_type="token_refresh",
        user=user,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
        action="token_refresh",
    )

    # Create new tokens
    access_token_expires = timedelta(
        minutes=settings.security.access_token_expire_minutes
    )
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role.value},
        expires_delta=access_token_expires,
    )

    new_refresh_token = create_refresh_token(
        data={"sub": user.id, "username": user.username, "role": user.role.value}
    )

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.security.access_token_expire_minutes * 60,
    )


@router.post("/logout")
async def logout(request: Request):
    """Logout endpoint (client should discard tokens)."""
    # In a real implementation, you might want to blacklist the token
    # For now, we'll just log the logout event

    # Try to get user from token
    user = None
    try:
        if "authorization" in request.headers:
            auth_header = request.headers["authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                from dental_backend_common.auth import MOCK_USERS, verify_token

                token_data = verify_token(token)
                if token_data and token_data.username:
                    user = MOCK_USERS.get(token_data.username)
    except Exception:
        pass

    # Log logout event
    audit_logger.log_event(
        event_type="logout",
        user=user,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
        action="logout",
    )

    return {"message": "Successfully logged out"}


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Get current user information."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
    }

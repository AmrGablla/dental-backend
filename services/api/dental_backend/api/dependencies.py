"""FastAPI dependencies for authentication and authorization."""

from dental_backend_common.audit import audit_logger
from dental_backend_common.auth import (
    User,
    UserRole,
    authenticate_client,
    check_permission,
    verify_token,
)
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security.oauth2 import OAuth2PasswordBearer

# Security schemes
security = HTTPBearer()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_data = verify_token(credentials.credentials)
    if token_data is None:
        raise credentials_exception

    # In production, this would fetch from database
    # For now, we'll use mock data
    if token_data.username == "admin":
        from dental_backend_common.auth import MOCK_USERS

        return MOCK_USERS["admin"]
    elif token_data.username == "operator":
        from dental_backend_common.auth import MOCK_USERS

        return MOCK_USERS["operator"]
    elif token_data.username == "service":
        from dental_backend_common.auth import MOCK_USERS

        return MOCK_USERS["service"]

    raise credentials_exception


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_role(required_role: UserRole):
    """Dependency to require specific role."""

    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if not check_permission(current_user.role, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role.value}",
            )
        return current_user

    return role_checker


# Role-specific dependencies
require_admin = require_role(UserRole.ADMIN)
require_operator = require_role(UserRole.OPERATOR)
require_service = require_role(UserRole.SERVICE)


async def get_client_user(
    request: Request, client_id: str, client_secret: str
) -> User | None:
    """Get user from OAuth2 client credentials."""
    user = authenticate_client(client_id, client_secret)
    if user:
        # Log client authentication
        audit_logger.log_event(
            event_type="client_authentication",
            user=user,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            action="client_auth",
        )
    return user


class AuditMiddleware:
    """Middleware for request/response auditing."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # For now, we'll skip audit logging in middleware to avoid complexity
            # Audit logging will be done in individual endpoints
            await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """Middleware to add security headers."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Add security headers to response
            async def send_with_headers(message):
                if message["type"] == "http.response.start":
                    message.setdefault("headers", [])
                    message["headers"].extend(
                        [
                            (b"X-Content-Type-Options", b"nosniff"),
                            (b"X-Frame-Options", b"DENY"),
                            (b"X-XSS-Protection", b"1; mode=block"),
                            (
                                b"Strict-Transport-Security",
                                b"max-age=31536000; includeSubDomains",
                            ),
                            (b"Content-Security-Policy", b"default-src 'self'"),
                            (b"Referrer-Policy", b"strict-origin-when-cross-origin"),
                        ]
                    )
                await send(message)

            await self.app(scope, receive, send_with_headers)
        else:
            await self.app(scope, receive, send)


class RateLimitMiddleware:
    """Simple rate limiting middleware."""

    def __init__(self, app):
        self.app = app
        self.requests = {}

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # For now, we'll skip rate limiting in middleware to avoid complexity
            # Rate limiting can be implemented in individual endpoints if needed
            await self.app(scope, receive, send)
        else:
            await self.app(scope, receive, send)


# Global rate limiter instance (will be initialized when used)
rate_limiter = None

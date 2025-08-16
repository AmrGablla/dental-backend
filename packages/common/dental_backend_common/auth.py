"""Authentication and authorization system for the dental backend."""

import hashlib
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from dental_backend_common.config import get_settings
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field

# Get settings
settings = get_settings()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRole(str, Enum):
    """User roles for RBAC."""

    ADMIN = "admin"
    OPERATOR = "operator"
    SERVICE = "service"


class TokenType(str, Enum):
    """Token types."""

    ACCESS = "access"
    REFRESH = "refresh"


class User(BaseModel):
    """User model."""

    id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    role: UserRole = Field(..., description="User role")
    is_active: bool = Field(default=True, description="User active status")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TokenData(BaseModel):
    """Token data model."""

    user_id: str | None = None
    username: str | None = None
    role: UserRole | None = None
    token_type: TokenType = TokenType.ACCESS


class Token(BaseModel):
    """Token response model."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class Credentials(BaseModel):
    """User credentials model."""

    username: str
    password: str


class ClientCredentials(BaseModel):
    """OAuth2 client credentials model."""

    client_id: str
    client_secret: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.security.access_token_expire_minutes
        )

    to_encode.update({"exp": expire, "type": TokenType.ACCESS})
    encoded_jwt = jwt.encode(
        to_encode, settings.security.secret_key, algorithm=settings.security.algorithm
    )
    return encoded_jwt


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        days=settings.security.refresh_token_expire_days
    )

    to_encode.update({"exp": expire, "type": TokenType.REFRESH})
    encoded_jwt = jwt.encode(
        to_encode, settings.security.secret_key, algorithm=settings.security.algorithm
    )
    return encoded_jwt


def verify_token(token: str) -> TokenData | None:
    """Verify and decode JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.security.secret_key,
            algorithms=[settings.security.algorithm],
        )
        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        role: str = payload.get("role")
        token_type: str = payload.get("type", TokenType.ACCESS)

        if user_id is None or username is None or role is None:
            return None

        return TokenData(
            user_id=user_id,
            username=username,
            role=UserRole(role),
            token_type=TokenType(token_type),
        )
    except JWTError:
        return None


def generate_pseudonym(patient_id: str, salt: str | None = None) -> str:
    """Generate pseudonym for patient identifier."""
    if not settings.pseudonymization_enabled:
        return patient_id

    if salt is None:
        salt = settings.security.secret_key

    # Create a deterministic but non-reversible pseudonym
    pseudonym_data = f"{patient_id}:{salt}"
    pseudonym_hash = hashlib.sha256(pseudonym_data.encode()).hexdigest()

    # Return first 16 characters for readability
    return pseudonym_hash[:16]


def check_permission(user_role: UserRole, required_role: UserRole) -> bool:
    """Check if user has required role permission."""
    role_hierarchy = {
        UserRole.ADMIN: 3,
        UserRole.OPERATOR: 2,
        UserRole.SERVICE: 1,
    }

    return role_hierarchy.get(user_role, 0) >= role_hierarchy.get(required_role, 0)


def require_role(required_role: UserRole):
    """Decorator to require specific role."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            # This would be used with FastAPI dependency injection
            # The actual implementation would depend on the request context
            pass

        return wrapper

    return decorator


# Mock user database for development
# In production, this would be replaced with a real database
MOCK_USERS = {
    "admin": User(
        id="admin-001",
        username="admin",
        email="admin@dental-backend.com",
        role=UserRole.ADMIN,
        is_active=True,
    ),
    "operator": User(
        id="operator-001",
        username="operator",
        email="operator@dental-backend.com",
        role=UserRole.OPERATOR,
        is_active=True,
    ),
    "service": User(
        id="service-001",
        username="service",
        email="service@dental-backend.com",
        role=UserRole.SERVICE,
        is_active=True,
    ),
}

# Mock password hashes (in production, these would be stored securely)
MOCK_PASSWORD_HASHES = {
    "admin": get_password_hash("admin123"),
    "operator": get_password_hash("operator123"),
    "service": get_password_hash("service123"),
}


def authenticate_user(username: str, password: str) -> User | None:
    """Authenticate user with username and password."""
    if username not in MOCK_USERS:
        return None

    user = MOCK_USERS[username]
    if not user.is_active:
        return None

    if username not in MOCK_PASSWORD_HASHES:
        return None

    if not verify_password(password, MOCK_PASSWORD_HASHES[username]):
        return None

    return user


def authenticate_client(client_id: str, client_secret: str) -> User | None:
    """Authenticate OAuth2 client credentials."""
    # In production, this would validate against a client database
    if client_id == "service-client" and client_secret == "service-secret":
        return MOCK_USERS["service"]
    return None

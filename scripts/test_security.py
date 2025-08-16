#!/usr/bin/env python3
"""Security and compliance test script for EPIC E2."""

import asyncio
import sys

import httpx
from dental_backend_common.audit import PIIFilter
from dental_backend_common.auth import (
    UserRole,
    authenticate_client,
    authenticate_user,
    create_access_token,
    generate_pseudonym,
    verify_token,
)
from dental_backend_common.config import get_settings
from dental_backend_common.encryption import (
    db_encryption,
    decrypt_pii,
    encrypt_pii,
    encryption_manager,
)

# Get settings
settings = get_settings()


def test_authentication() -> bool:
    """Test authentication system."""
    print("🔐 Testing authentication system...")

    try:
        # Test user authentication
        user = authenticate_user("admin", "admin123")
        if not user or user.role != UserRole.ADMIN:
            print("  ✗ Admin authentication failed")
            return False
        print("  ✓ Admin authentication successful")

        # Test operator authentication
        user = authenticate_user("operator", "operator123")
        if not user or user.role != UserRole.OPERATOR:
            print("  ✗ Operator authentication failed")
            return False
        print("  ✓ Operator authentication successful")

        # Test service authentication
        user = authenticate_user("service", "service123")
        if not user or user.role != UserRole.SERVICE:
            print("  ✗ Service authentication failed")
            return False
        print("  ✓ Service authentication successful")

        # Test invalid credentials
        user = authenticate_user("admin", "wrongpassword")
        if user:
            print("  ✗ Invalid credentials accepted")
            return False
        print("  ✓ Invalid credentials rejected")

        # Test client authentication
        user = authenticate_client("service-client", "service-secret")
        if not user or user.role != UserRole.SERVICE:
            print("  ✗ Client authentication failed")
            return False
        print("  ✓ Client authentication successful")

        return True
    except Exception as e:
        print(f"  ✗ Authentication test failed: {e}")
        return False


def test_jwt_tokens() -> bool:
    """Test JWT token creation and verification."""
    print("🎫 Testing JWT tokens...")

    try:
        # Create tokens
        user_data = {"sub": "test-user", "username": "test", "role": "admin"}
        access_token = create_access_token(user_data)
        # Note: refresh_token would be used in a real implementation
        # refresh_token = create_access_token(user_data)

        # Verify tokens
        token_data = verify_token(access_token)
        if not token_data or token_data.username != "test":
            print("  ✗ Token verification failed")
            return False
        print("  ✓ Token creation and verification successful")

        # Test invalid token
        invalid_token = "invalid.token.here"
        token_data = verify_token(invalid_token)
        if token_data:
            print("  ✗ Invalid token accepted")
            return False
        print("  ✓ Invalid token rejected")

        return True
    except Exception as e:
        print(f"  ✗ JWT token test failed: {e}")
        return False


def test_encryption() -> bool:
    """Test encryption utilities."""
    print("🔒 Testing encryption utilities...")

    try:
        # Test local encryption
        test_data = "sensitive patient data"
        encrypted = encryption_manager.encrypt_data(test_data)
        decrypted = encryption_manager.decrypt_data(encrypted)

        if decrypted != test_data:
            print("  ✗ Local encryption/decryption failed")
            return False
        print("  ✓ Local encryption/decryption successful")

        # Test PII encryption
        pii_data = "patient@email.com"
        encrypted_pii = encrypt_pii(pii_data)
        decrypted_pii = decrypt_pii(encrypted_pii)

        if decrypted_pii != pii_data:
            print("  ✗ PII encryption/decryption failed")
            return False
        print("  ✓ PII encryption/decryption successful")

        # Test database encryption
        db_data = {"patient_id": "12345", "diagnosis": "cavity"}
        encrypted_db = db_encryption.encrypt_json_field(db_data)
        decrypted_db = db_encryption.decrypt_json_field(encrypted_db)

        if decrypted_db != db_data:
            print("  ✗ Database encryption/decryption failed")
            return False
        print("  ✓ Database encryption/decryption successful")

        return True
    except Exception as e:
        print(f"  ✗ Encryption test failed: {e}")
        return False


def test_pii_filtering() -> bool:
    """Test PII filtering and scrubbing."""
    print("🛡️  Testing PII filtering...")

    try:
        # Test PII scrubbing
        test_text = (
            "Patient email: john.doe@email.com, phone: 555-123-4567, SSN: 123-45-6789"
        )
        scrubbed = PIIFilter.scrub_pii(test_text)

        if (
            "john.doe@email.com" in scrubbed
            or "555-123-4567" in scrubbed
            or "123-45-6789" in scrubbed
        ):
            print("  ✗ PII not properly scrubbed")
            return False
        print("  ✓ PII scrubbing successful")

        # Test dictionary scrubbing
        test_dict = {
            "patient_info": {
                "email": "patient@email.com",
                "phone": "555-987-6543",
                "notes": "Patient has cavity",
            }
        }
        scrubbed_dict = PIIFilter.scrub_dict(test_dict)

        if "patient@email.com" in str(scrubbed_dict) or "555-987-6543" in str(
            scrubbed_dict
        ):
            print("  ✗ Dictionary PII not properly scrubbed")
            return False
        print("  ✓ Dictionary PII scrubbing successful")

        return True
    except Exception as e:
        print(f"  ✗ PII filtering test failed: {e}")
        return False


def test_pseudonymization() -> bool:
    """Test patient identifier pseudonymization."""
    print("🕵️  Testing pseudonymization...")

    try:
        # Test pseudonym generation
        patient_id = "PATIENT12345"
        pseudonym1 = generate_pseudonym(patient_id)
        pseudonym2 = generate_pseudonym(patient_id)

        # Should be deterministic
        if pseudonym1 != pseudonym2:
            print("  ✗ Pseudonym generation not deterministic")
            return False

        # Should be different from original
        if pseudonym1 == patient_id:
            print("  ✗ Pseudonym same as original")
            return False

        print("  ✓ Pseudonymization successful")
        return True
    except Exception as e:
        print(f"  ✗ Pseudonymization test failed: {e}")
        return False


async def test_api_security() -> bool:
    """Test API security endpoints."""
    print("🌐 Testing API security endpoints...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            base_url = "http://localhost:8000"

            # Test authentication endpoint
            auth_data = {"username": "admin", "password": "admin123"}
            response = await client.post(f"{base_url}/auth/token", data=auth_data)

            if response.status_code != 200:
                print("  ✗ Authentication endpoint failed")
                return False

            token_data = response.json()
            if "access_token" not in token_data:
                print("  ✗ No access token in response")
                return False

            access_token = token_data["access_token"]
            headers = {"Authorization": f"Bearer {access_token}"}

            print("  ✓ Authentication endpoint successful")

            # Test protected endpoints
            protected_endpoints = [
                "/protected/admin",
                "/protected/operator",
                "/protected/service",
            ]

            for endpoint in protected_endpoints:
                response = await client.get(f"{base_url}{endpoint}", headers=headers)
                if response.status_code != 200:
                    print(f"  ✗ Protected endpoint {endpoint} failed")
                    return False
                print(f"  ✓ Protected endpoint {endpoint} successful")

            # Test unauthorized access
            response = await client.get(f"{base_url}/protected/admin")
            if response.status_code != 401:
                print("  ✗ Unauthorized access not properly blocked")
                return False
            print("  ✓ Unauthorized access properly blocked")

            return True
    except Exception as e:
        print(f"  ✗ API security test failed: {e}")
        return False


async def test_compliance_endpoints() -> bool:
    """Test compliance endpoints."""
    print("📋 Testing compliance endpoints...")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            base_url = "http://localhost:8000"

            # Get admin token
            auth_data = {"username": "admin", "password": "admin123"}
            response = await client.post(f"{base_url}/auth/token", data=auth_data)
            token_data = response.json()
            access_token = token_data["access_token"]
            headers = {"Authorization": f"Bearer {access_token}"}

            # Test compliance status
            response = await client.get(
                f"{base_url}/compliance/compliance-status", headers=headers
            )
            if response.status_code != 200:
                print("  ✗ Compliance status endpoint failed")
                return False
            print("  ✓ Compliance status endpoint successful")

            # Test data retention purge (dry run)
            purge_data = {"resource_type": "dental_case", "dry_run": True}
            response = await client.post(
                f"{base_url}/compliance/data-retention/purge",
                json=purge_data,
                headers=headers,
            )
            if response.status_code != 200:
                print("  ✗ Data retention purge endpoint failed")
                return False
            print("  ✓ Data retention purge endpoint successful")

            # Test right to erasure (dry run)
            erasure_data = {
                "patient_id": "PATIENT123",
                "reason": "GDPR Article 17 request",
                "dry_run": True,
            }
            response = await client.post(
                f"{base_url}/compliance/right-to-erasure",
                json=erasure_data,
                headers=headers,
            )
            if response.status_code != 200:
                print("  ✗ Right to erasure endpoint failed")
                return False
            print("  ✓ Right to erasure endpoint successful")

            return True
    except Exception as e:
        print(f"  ✗ Compliance endpoints test failed: {e}")
        return False


async def main():
    """Run all security and compliance tests."""
    print("🔒 Dental Backend Security & Compliance Test")
    print("=" * 60)

    tests = [
        ("Authentication", test_authentication),
        ("JWT Tokens", test_jwt_tokens),
        ("Encryption", test_encryption),
        ("PII Filtering", test_pii_filtering),
        ("Pseudonymization", test_pseudonymization),
        ("API Security", test_api_security),
        ("Compliance Endpoints", test_compliance_endpoints),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ✗ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
        print()

    # Summary
    print("📊 Security Test Results Summary")
    print("=" * 60)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All security and compliance tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

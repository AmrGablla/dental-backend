"""Encryption utilities for the dental backend."""

import base64
import hashlib
import json
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet
from dental_backend_common.config import get_settings

# Get settings
settings = get_settings()


class EncryptionManager:
    """Manages encryption for sensitive data."""

    def __init__(self):
        self.fernet_key = self._get_or_create_fernet_key()
        self.cipher_suite = Fernet(self.fernet_key)

        # Initialize AWS KMS client if configured
        self.kms_client = None
        if settings.security.kms_key_id:
            try:
                self.kms_client = boto3.client("kms")
            except Exception as e:
                print(f"Warning: Could not initialize KMS client: {e}")

    def _get_or_create_fernet_key(self) -> bytes:
        """Get or create Fernet key for local encryption."""
        key_file = "/tmp/dental-backend-fernet.key"

        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(key)
            return key

    def encrypt_data(self, data: str, use_kms: bool = False) -> str:
        """Encrypt data using either local encryption or KMS."""
        if not settings.encryption_enabled:
            return data

        if use_kms and self.kms_client and settings.security.kms_key_id:
            return self._encrypt_with_kms(data)
        else:
            return self._encrypt_locally(data)

    def decrypt_data(self, encrypted_data: str, use_kms: bool = False) -> str:
        """Decrypt data using either local encryption or KMS."""
        if not settings.encryption_enabled:
            return encrypted_data

        if use_kms and self.kms_client and settings.security.kms_key_id:
            return self._decrypt_with_kms(encrypted_data)
        else:
            return self._decrypt_locally(encrypted_data)

    def _encrypt_locally(self, data: str) -> str:
        """Encrypt data using local Fernet encryption."""
        encrypted = self.cipher_suite.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()

    def _decrypt_locally(self, encrypted_data: str) -> str:
        """Decrypt data using local Fernet encryption."""
        encrypted = base64.b64decode(encrypted_data.encode())
        decrypted = self.cipher_suite.decrypt(encrypted)
        return decrypted.decode()

    def _encrypt_with_kms(self, data: str) -> str:
        """Encrypt data using AWS KMS."""
        try:
            response = self.kms_client.encrypt(
                KeyId=settings.security.kms_key_id, Plaintext=data.encode()
            )
            return base64.b64encode(response["CiphertextBlob"]).decode()
        except ClientError as e:
            print(f"KMS encryption failed: {e}")
            # Fallback to local encryption
            return self._encrypt_locally(data)

    def _decrypt_with_kms(self, encrypted_data: str) -> str:
        """Decrypt data using AWS KMS."""
        try:
            ciphertext = base64.b64decode(encrypted_data.encode())
            response = self.kms_client.decrypt(CiphertextBlob=ciphertext)
            return response["Plaintext"].decode()
        except ClientError as e:
            print(f"KMS decryption failed: {e}")
            # Fallback to local decryption
            return self._decrypt_locally(encrypted_data)


class S3Encryption:
    """S3 encryption utilities."""

    def __init__(self):
        self.s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3.endpoint_url,
            aws_access_key_id=settings.s3.access_key_id,
            aws_secret_access_key=settings.s3.secret_access_key,
            region_name=settings.s3.region_name,
            use_ssl=settings.s3.use_ssl,
        )

    def get_sse_kms_config(self) -> dict[str, str]:
        """Get S3 Server-Side Encryption with KMS configuration."""
        if settings.security.kms_key_id:
            return {
                "ServerSideEncryption": "aws:kms",
                "SSEKMSKeyId": settings.security.kms_key_id,
            }
        else:
            return {"ServerSideEncryption": "AES256"}

    def upload_file_encrypted(self, file_path: str, bucket: str, key: str) -> bool:
        """Upload file with encryption."""
        try:
            extra_args = self.get_sse_kms_config()
            self.s3_client.upload_file(file_path, bucket, key, ExtraArgs=extra_args)
            return True
        except ClientError as e:
            print(f"S3 upload failed: {e}")
            return False

    def download_file_encrypted(self, bucket: str, key: str, file_path: str) -> bool:
        """Download encrypted file."""
        try:
            self.s3_client.download_file(bucket, key, file_path)
            return True
        except ClientError as e:
            print(f"S3 download failed: {e}")
            return False


class DatabaseEncryption:
    """Database encryption utilities."""

    def __init__(self):
        self.encryption_manager = EncryptionManager()

    def encrypt_field(self, value: str) -> str:
        """Encrypt a database field."""
        if not value:
            return value
        return self.encryption_manager.encrypt_data(value)

    def decrypt_field(self, encrypted_value: str) -> str:
        """Decrypt a database field."""
        if not encrypted_value:
            return encrypted_value
        return self.encryption_manager.decrypt_data(encrypted_value)

    def encrypt_json_field(self, data: dict[str, Any]) -> str:
        """Encrypt JSON data for database storage."""
        if not data:
            return ""
        json_str = json.dumps(data)
        return self.encryption_manager.encrypt_data(json_str)

    def decrypt_json_field(self, encrypted_json: str) -> dict[str, Any]:
        """Decrypt JSON data from database storage."""
        if not encrypted_json:
            return {}
        decrypted = self.encryption_manager.decrypt_data(encrypted_json)
        return json.loads(decrypted)


# Global instances
encryption_manager = EncryptionManager()
s3_encryption = S3Encryption()
db_encryption = DatabaseEncryption()


def encrypt_pii(data: str) -> str:
    """Encrypt PII data."""
    if not settings.pii_encryption_enabled:
        return data
    return encryption_manager.encrypt_data(data)


def decrypt_pii(encrypted_data: str) -> str:
    """Decrypt PII data."""
    if not settings.pii_encryption_enabled:
        return encrypted_data
    return encryption_manager.decrypt_data(encrypted_data)


def hash_sensitive_data(data: str) -> str:
    """Create a one-way hash of sensitive data."""
    return hashlib.sha256(data.encode()).hexdigest()


def verify_data_integrity(data: str, expected_hash: str) -> bool:
    """Verify data integrity using hash."""
    actual_hash = hash_sensitive_data(data)
    return actual_hash == expected_hash

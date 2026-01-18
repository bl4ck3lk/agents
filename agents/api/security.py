"""Security utilities for API key encryption."""

import os
from base64 import urlsafe_b64decode, urlsafe_b64encode

from cryptography.fernet import Fernet


class APIKeyEncryption:
    """Handles encryption and decryption of API keys using Fernet."""

    def __init__(self, key: bytes | None = None) -> None:
        """Initialize with encryption key.

        Args:
            key: 32-byte encryption key. If not provided, reads from ENCRYPTION_KEY env var.
        """
        if key is None:
            env_key = os.getenv("ENCRYPTION_KEY")
            if env_key:
                # Ensure key is 32 bytes, URL-safe base64 encoded
                key = urlsafe_b64decode(env_key.encode())
            else:
                # Generate a new key for development (not recommended for production)
                key = Fernet.generate_key()
                print(f"WARNING: Generated new encryption key. Set ENCRYPTION_KEY env var.")
                print(f"ENCRYPTION_KEY={key.decode()}")

        # Fernet requires URL-safe base64 encoded 32-byte key
        if len(key) == 32:
            self._fernet = Fernet(urlsafe_b64encode(key))
        else:
            # Assume it's already a Fernet key
            self._fernet = Fernet(key)

    def encrypt(self, api_key: str) -> str:
        """Encrypt an API key.

        Args:
            api_key: The plaintext API key.

        Returns:
            Base64-encoded encrypted key.
        """
        encrypted = self._fernet.encrypt(api_key.encode())
        return encrypted.decode()

    def decrypt(self, encrypted_key: str) -> str:
        """Decrypt an API key.

        Args:
            encrypted_key: Base64-encoded encrypted key.

        Returns:
            The plaintext API key.
        """
        decrypted = self._fernet.decrypt(encrypted_key.encode())
        return decrypted.decode()

    def mask_key(self, api_key: str, visible_chars: int = 4) -> str:
        """Mask an API key for display.

        Args:
            api_key: The plaintext API key.
            visible_chars: Number of characters to show at start and end.

        Returns:
            Masked key like "sk-...1234"
        """
        if len(api_key) <= visible_chars * 2:
            return "*" * len(api_key)

        return f"{api_key[:visible_chars]}...{api_key[-visible_chars:]}"

    @staticmethod
    def generate_key() -> str:
        """Generate a new Fernet encryption key.

        Returns:
            URL-safe base64-encoded 32-byte key.
        """
        return Fernet.generate_key().decode()


# Global encryption instance
_encryption: APIKeyEncryption | None = None


def get_encryption() -> APIKeyEncryption:
    """Get or create encryption singleton."""
    global _encryption
    if _encryption is None:
        _encryption = APIKeyEncryption()
    return _encryption

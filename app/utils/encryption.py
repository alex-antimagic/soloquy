"""
Encryption utilities for securing sensitive data like OAuth tokens
Uses Fernet symmetric encryption
"""
import os
from cryptography.fernet import Fernet


class EncryptionService:
    """Service for encrypting and decrypting sensitive data"""

    def __init__(self):
        """Initialize encryption service with key from environment"""
        encryption_key = os.environ.get('ENCRYPTION_KEY')

        if not encryption_key:
            # Generate a key for development (NEVER use this in production)
            print("WARNING: ENCRYPTION_KEY not set. Generating temporary key for development only.")
            encryption_key = Fernet.generate_key().decode()
            print(f"Generated key: {encryption_key}")
            print("Add this to your .env file: ENCRYPTION_KEY={encryption_key}")

        # Ensure key is bytes
        if isinstance(encryption_key, str):
            encryption_key = encryption_key.encode()

        try:
            self.cipher = Fernet(encryption_key)
        except Exception as e:
            raise ValueError(f"Invalid ENCRYPTION_KEY: {e}")

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string

        Args:
            plaintext: String to encrypt

        Returns:
            Encrypted string (base64 encoded)
        """
        if not plaintext:
            return None

        # Convert to bytes if string
        if isinstance(plaintext, str):
            plaintext = plaintext.encode()

        # Encrypt and return as string
        encrypted = self.cipher.encrypt(plaintext)
        return encrypted.decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a string

        Args:
            ciphertext: Encrypted string (base64 encoded)

        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return None

        # Convert to bytes if string
        if isinstance(ciphertext, str):
            ciphertext = ciphertext.encode()

        # Decrypt and return as string
        decrypted = self.cipher.decrypt(ciphertext)
        return decrypted.decode()


# Singleton instance
encryption_service = EncryptionService()

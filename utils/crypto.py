# utils/crypto.py
"""
Cifrado y descifrado simétrico AES-256 (Fernet)
para proteger las claves API almacenadas en la base de datos.
"""

import base64
import os
from cryptography.fernet import Fernet
from utils.logger import logger


def get_cipher():
    """Crea un objeto Fernet a partir de APP_ENCRYPTION_KEY."""
    key = os.getenv("APP_ENCRYPTION_KEY", None)
    if not key:
        logger.warning("⚠️ No se ha configurado APP_ENCRYPTION_KEY, los datos no se cifrarán.")
        return None
    try:
        if len(key) != 44:
            key = base64.urlsafe_b64encode(key.encode().ljust(32, b"0"))
        return Fernet(key)
    except Exception as e:
        logger.error(f"Error creando cipher AES: {e}")
        return None


def encrypt_value(value: str) -> str:
    """Cifra un valor de texto plano."""
    if not value:
        return ""
    cipher = get_cipher()
    if not cipher:
        return value
    return cipher.encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    """Descifra un valor cifrado."""
    if not value:
        return ""
    cipher = get_cipher()
    if not cipher:
        return value
    try:
        return cipher.decrypt(value.encode()).decode()
    except Exception:
        logger.warning("No se pudo descifrar valor, devolviendo texto plano.")
        return value

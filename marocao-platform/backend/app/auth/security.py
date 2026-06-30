# backend/app/auth/security.py
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from backend.app.config import settings

# Initialisation d'Argon2id par défaut
ph = PasswordHasher()

class SecurityManager:
    @staticmethod
    def hash_password(password: str) -> str:
        """Hache un mot de passe en utilisant Argon2id."""
        return ph.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Vérifie un mot de passe par rapport à son hash Argon2id."""
        try:
            return ph.verify(hashed_password, plain_password)
        except VerifyMismatchError:
            return False

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Génère un jeton JWT signé avec l'algorithme spécifié dans l'environnement."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def decode_access_token(token: str) -> Optional[dict]:
        """Décode et valide un token JWT reçu du client."""
        try:
            return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        except jwt.PyJWTError:
            return None
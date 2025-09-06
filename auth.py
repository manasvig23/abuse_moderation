# auth.py - Complete Authentication System
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import SessionLocal
import models

# Password hashing configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = "abuse-moderation-secret-key-change-in-production-2024"  # Change this!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour tokens

# Token dependency for Bearer authentication
security = HTTPBearer()

def hash_password(password: str) -> str:
    """
    Convert plain password to secure hash
    Why: Never store plain passwords in database
    Example: "password123" -> "$2b$12$EixZaYVK1fsbw1ZfbX3OXe..."
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Check if entered password matches stored hash
    Why: Used during login to verify user identity
    """
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    """
    Create JWT token for authenticated sessions
    Why: Instead of sending username/password every request,
         user gets a token that expires automatically
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_db():
    """Database session dependency - reusable across all endpoints"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), 
                    db: Session = Depends(get_db)):
    """
    Extract user info from JWT token
    Why: This runs on every protected endpoint to identify who is making the request
    Returns: User object if token is valid
    Raises: 401 if token is invalid/expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode the JWT token
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Convert to int (user IDs are integers)
        user_id = int(user_id)
        
    except (JWTError, ValueError):
        raise credentials_exception
    
    # Get user from database
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    
    # Check if user account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user

def get_current_moderator(current_user: models.User = Depends(get_current_user)):
    """
    Ensure current user is a moderator
    Why: Restrict certain endpoints to moderators only
    Usage: Add as dependency to moderator-only endpoints
    """
    if current_user.role not in ["moderator", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Moderator or admin role required."
        )
    return current_user

def authenticate_user(db: Session, username: str, password: str):
    """
    Verify login credentials
    Why: Used in login endpoint to check if user exists and password is correct
    Returns: User object if successful, False if failed
    """
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return False  # User doesn't exist
    
    if not user.is_active:
        return False  # Account disabled
        
    if not verify_password(password, user.password_hash):
        return False  # Wrong password
        
    return user  # Login successful

# Optional: Create default moderator account
def create_default_moderator(db: Session):
    """
    Create a default moderator account for testing
    Why: Need at least one moderator to test the system
    """
    existing_mod = db.query(models.User).filter(
        models.User.username == "admin",
        models.User.role == "moderator"
    ).first()
    
    if not existing_mod:
        admin_user = models.User(
            username="admin",
            email="admin@example.com",
            password_hash=hash_password("admin123"),
            role="moderator"
        )
        db.add(admin_user)
        db.commit()
        print("Default moderator created: username=admin, password=admin123")
        return admin_user
    
    return existing_mod
from fastapi import APIRouter, HTTPException, Depends, Body, Response, status, Header
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from models import verify_user, create_user, get_user, AVAILABLE_DOMAINS
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import jwt
from bson import ObjectId

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# Secret key for JWT (in production, use a proper secret key from environment variables)
SECRET_KEY = "your-secret-key-here"
ALGORITHM = "HS256"

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    interests: List[str] = []
    role: str = 'user'

router = APIRouter()

@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    print(f"Login attempt for user: {form_data.username}")
    user = verify_user(form_data.username, form_data.password)
    if not user:
        print("Login failed: Invalid credentials")
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    print(f"User data from database: {user}")
    print(f"User interests from database: {user.get('interests')}")
    
    # Create JWT token
    token_data = {
        "sub": user["username"],
        "user_id": str(user["_id"]),
        "exp": datetime.utcnow() + timedelta(days=1)
    }
    
    token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    
    response_data = {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user["_id"]),
            "username": user["username"],
            "email": user.get("email", ""),
            "interests": user.get("interests", [])
        }
    }
    
    print(f"Login response data: {response_data}")
    return response_data

@router.post("/register")
async def register(user_data: UserCreate):
    # Validate domains/interests
    if not all(domain in AVAILABLE_DOMAINS for domain in user_data.interests):
        raise HTTPException(status_code=400, detail="Invalid domain(s) provided")
    
    # Check if user already exists
    if get_user(user_data.username) or get_user(user_data.email):
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    # Create user
    user = create_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        role=user_data.role,
        interests=user_data.interests
    )
    
    if not user[0]:  # create_user returns (user_id, error_message)
        raise HTTPException(status_code=400, detail=user[1])
        
    return {"message": "User created successfully", "user_id": user[0]}

@router.post("/logout")
async def logout(response: Response):
    # In a real app, you might want to add the token to a blacklist
    response.delete_cookie("access_token")
    return {"message": "Successfully logged out"}

# Get current user based on the token
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = get_user(username)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get("/me", response_model=Dict[str, Any])
async def read_users_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get the current user's profile information.
    """
    # Convert ObjectId to string for JSON serialization
    user_data = dict(current_user)
    if '_id' in user_data:
        user_data['_id'] = str(user_data['_id'])
    # Remove sensitive data
    user_data.pop('hashed_password', None)
    return user_data

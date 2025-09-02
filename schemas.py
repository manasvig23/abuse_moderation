from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    email: str

class PostCreate(BaseModel):
    content: str

class CommentCreate(BaseModel):
    text: str
    user_id: int
    post_id: int

from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True)
    
    # Authentication fields
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")  # "user" or "moderator"
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)  # FIXED: Boolean instead of Integer

    # Relationships
    posts = relationship("Post", back_populates="author", foreign_keys="Post.author_id")
    comments = relationship("Comment", back_populates="author", foreign_keys="Comment.user_id")

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    author = relationship("User", back_populates="posts", foreign_keys=[author_id])

class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    is_abusive = Column(Integer, default=0, index=True)  # 0=clean, 1=abusive
    
    # Enhanced moderation fields
    status = Column(String, default="approved", index=True)  # "approved", "hidden", "pending_review"
    confidence_score = Column(Integer, default=0)
    flagged_words = Column(String)  # Comma-separated list
    
    # Auto-review fields
    auto_review_action = Column(String, index=True)  # "approve", "auto_approve", "keep_hidden", "human_review_needed"
    auto_review_reason = Column(String)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    moderated_at = Column(DateTime)
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    moderated_by = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    author = relationship("User", back_populates="comments", foreign_keys=[user_id])
    post = relationship("Post", back_populates="comments", foreign_keys=[post_id])
    moderator = relationship("User", foreign_keys=[moderated_by])
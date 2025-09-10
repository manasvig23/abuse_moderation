from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from database import SessionLocal, engine, Base
import models, schemas
from filter import is_abusive_with_auto_review
from auth import (
    hash_password, 
    authenticate_user, 
    create_access_token,
    get_current_user,
    get_current_moderator,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
# Create tables
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Abuse Moderation API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication Endpoints
@app.post("/api/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_user = models.User(
        username=user.username,
        email=user.email,
        password_hash=hash_password(user.password),
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/api/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """Login and get access token"""
    user = authenticate_user(db, user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

# User Endpoints
@app.get("/api/user/my-posts")
def get_my_posts(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """My Profile page - Shows user's own posts"""
    user_posts = db.query(models.Post).filter(
        models.Post.author_id == current_user.id
    ).order_by(models.Post.created_at.desc()).all()
    
    result = []
    for post in user_posts:
        # Show ALL comments for own posts (approved + pending)
        all_comments = [
            {
                "id": c.id,
                "text": c.text,
                "author_username": c.author.username,
                "created_at": c.created_at,
                "status": c.status
            }
            for c in post.comments
        ]
        
        result.append({
            "id": post.id,
            "content": post.content,
            "created_at": post.created_at,
            "comments": all_comments,
            "total_comments": len(all_comments)
        })
    
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username
        },
        "posts": result
    }

@app.get("/api/user/explore-feed")
def get_explore_feed(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Explore Feed page - Shows other users' posts"""
    other_posts = db.query(models.Post).filter(
        models.Post.author_id != current_user.id  # Exclude own posts
    ).order_by(models.Post.created_at.desc()).all()
    
    result = []
    for post in other_posts:
        # Show only approved comments for other users' posts
        approved_comments = [
            {
                "id": c.id,
                "text": c.text,
                "author_username": c.author.username,
                "created_at": c.created_at
            }
            for c in post.comments 
            if c.status == "approved"
        ]
        
        result.append({
            "id": post.id,
            "content": post.content,
            "author_username": post.author.username,
            "created_at": post.created_at,
            "comments": approved_comments,
            "total_comments": len(approved_comments)
        })
    
    return {"posts": result}

# Post Endpoints
@app.post("/api/posts/", response_model=schemas.PostResponse)
def create_post(post: schemas.PostCreate, 
               current_user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Create a new post"""
    db_post = models.Post(
        content=post.content,
        author_id=current_user.id
    )
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

@app.get("/api/posts/")
def get_all_posts(db: Session = Depends(get_db)):
    """Get all posts with approved comments only (public view)"""
    posts = db.query(models.Post).order_by(models.Post.created_at.desc()).all()
    
    result = []
    for post in posts:
        approved_comments = [
            {
                "id": c.id,
                "text": c.text,
                "author_username": c.author.username,
                "created_at": c.created_at
            }
            for c in post.comments 
            if c.status == "approved"
        ]
        
        result.append({
            "id": post.id,
            "content": post.content,
            "author_username": post.author.username,
            "created_at": post.created_at,
            "comments": approved_comments,
            "total_comments": len(approved_comments)
        })
    
    return {"posts": result}

@app.get("/api/posts/{post_id}")
def get_post_details(post_id: int, db: Session = Depends(get_db)):
    """Get specific post with approved comments only"""
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    approved_comments = [
        {
            "id": c.id,
            "text": c.text,
            "author_username": c.author.username,
            "created_at": c.created_at
        }
        for c in post.comments if c.status == "approved"
    ]

    return {
        "id": post.id,
        "content": post.content,
        "author_username": post.author.username,
        "created_at": post.created_at,
        "comments": approved_comments,
        "total_visible_comments": len(approved_comments)
    }

# Comment Endpoints
@app.post("/api/comments/")
def create_comment(comment: schemas.CommentCreate, 
                  current_user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Create comment with auto-review system"""
    
    post = db.query(models.Post).filter(models.Post.id == comment.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if len(comment.text.strip()) == 0:
        raise HTTPException(status_code=400, detail="Comment cannot be empty")
    if len(comment.text) > 1000:
        raise HTTPException(status_code=400, detail="Comment too long (max 1000 characters)")
    
    # Run auto-review analysis
    review_result = is_abusive_with_auto_review(comment.text)
    
    # Determine status based on auto-review
    if review_result["auto_action"] in ["approve", "auto_approve"]:
        comment_status = "approved"
        visible_in_feed = True
    else:  # keep_hidden or human_review_needed
        comment_status = "hidden" if review_result["auto_action"] == "keep_hidden" else "pending_review"
        visible_in_feed = False
    
    # Create comment
    db_comment = models.Comment(
        text=comment.text,
        is_abusive=review_result["is_abusive"],
        status=comment_status,
        confidence_score=int(review_result["confidence"] * 100),
        flagged_words=",".join(review_result["flagged_words"]) if review_result["flagged_words"] else None,
        auto_review_action=review_result["auto_action"],
        auto_review_reason=review_result["reason"],
        user_id=current_user.id,
        post_id=comment.post_id
    )
    
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    
    return {
        "message": "Comment posted successfully",
        "comment_id": db_comment.id,
        "visible_in_feed": visible_in_feed,
        "auto_processed": review_result["auto_action"] != "human_review_needed"
    }

# Moderator Endpoints
@app.get("/api/moderator/users")
def get_all_users_list(
    moderator: models.User = Depends(get_current_moderator),
    db: Session = Depends(get_db)
):
    """User List page - All Users List with details"""
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    
    users_data = []
    for user in users:
        total_posts = db.query(models.Post).filter(models.Post.author_id == user.id).count()
        total_comments = db.query(models.Comment).filter(models.Comment.user_id == user.id).count()
        flagged_comments = db.query(models.Comment).filter(
            models.Comment.user_id == user.id,
            models.Comment.is_abusive == 1
        ).count()
        
        users_data.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "created_at": user.created_at,
            "is_active": user.is_active,
            "total_posts": total_posts,
            "total_comments": total_comments,
            "flagged_comments": flagged_comments
        })
    
    return {"users": users_data}

@app.get("/api/moderator/all-posts")
def get_all_posts_moderation(
    user_id: Optional[int] = None,
    moderator: models.User = Depends(get_current_moderator),
    db: Session = Depends(get_db)
):
    """All Posts page - Select user from dropdown and see their posts"""
    query = db.query(models.Post)
    
    # Filter by user if selected from dropdown
    if user_id:
        query = query.filter(models.Post.author_id == user_id)
    
    posts = query.order_by(models.Post.created_at.desc()).all()
    
    result = []
    for post in posts:
        # Show ALL comments with their statuses for moderator
        all_comments = [
            {
                "id": c.id,
                "text": c.text,
                "author_username": c.author.username,
                "created_at": c.created_at,
                "status": c.status,  # approved, hidden, pending_review
                "is_abusive": c.is_abusive,
                "flagged_words": c.flagged_words,
                "confidence_score": c.confidence_score,
                "auto_review_action": c.auto_review_action,
                "auto_review_reason": c.auto_review_reason
            }
            for c in post.comments
        ]
        
        result.append({
            "id": post.id,
            "content": post.content,
            "author_username": post.author.username,
            "author_id": post.author_id,
            "created_at": post.created_at,
            "comments": all_comments,
            "total_comments": len(all_comments)
        })
    
    return {"posts": result}

@app.get("/api/moderator/posts-for-review")
def get_posts_for_review(
    moderator: models.User = Depends(get_current_moderator),
    db: Session = Depends(get_db)
):
    """Review Comments page - List all posts that have comments needing review"""
    posts_with_pending = db.query(models.Post).join(models.Comment).filter(
        models.Comment.auto_review_action == "human_review_needed"
    ).distinct().order_by(models.Post.created_at.desc()).all()
    
    result = []
    for post in posts_with_pending:
        # Count pending comments for this post
        pending_count = sum(1 for c in post.comments if c.auto_review_action == "human_review_needed")
        
        result.append({
            "id": post.id,
            "content": post.content,
            "author_username": post.author.username,
            "created_at": post.created_at,
            "pending_comments_count": pending_count
        })
    
    return {"posts": result}

@app.get("/api/moderator/posts/{post_id}/review")
def get_post_for_review(
    post_id: int,
    moderator: models.User = Depends(get_current_moderator),
    db: Session = Depends(get_db)
):
    """Review Comments - Show specific post with comments for approve/hide/delete"""
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Show ALL comments for this post
    all_comments = [
        {
            "id": c.id,
            "text": c.text,
            "author_username": c.author.username,
            "created_at": c.created_at,
            "status": c.status,
            "is_abusive": c.is_abusive,
            "flagged_words": c.flagged_words,
            "confidence_score": c.confidence_score,
            "auto_review_action": c.auto_review_action,
            "auto_review_reason": c.auto_review_reason
        }
        for c in post.comments
    ]
    
    return {
        "post": {
            "id": post.id,
            "content": post.content,
            "author_username": post.author.username,
            "created_at": post.created_at
        },
        "comments": all_comments
    }

@app.get("/api/moderator/flagged-comments")
def get_flagged_comments(
    user_id: Optional[int] = None,
    moderator: models.User = Depends(get_current_moderator),
    db: Session = Depends(get_db)
):
    """Flagged Comments page - Select user and see their posts with flagged comments"""
    query = db.query(models.Post).join(models.Comment).filter(
        models.Comment.is_abusive == 1
    )
    
    # Filter by user if selected
    if user_id:
        query = query.filter(models.Post.author_id == user_id)
    
    posts_with_flagged = query.distinct().order_by(models.Post.created_at.desc()).all()
    
    result = []
    for post in posts_with_flagged:
        # Show only flagged/hidden comments for this post
        flagged_comments = [
            {
                "id": c.id,
                "text": c.text,
                "author_username": c.author.username,
                "created_at": c.created_at,
                "status": c.status,
                "flagged_words": c.flagged_words,
                "confidence_score": c.confidence_score,
                "auto_review_action": c.auto_review_action,
                "auto_review_reason": c.auto_review_reason
            }
            for c in post.comments
            if c.is_abusive == 1
        ]
        
        result.append({
            "id": post.id,
            "content": post.content,
            "author_username": post.author.username,
            "created_at": post.created_at,
            "flagged_comments": flagged_comments,
            "flagged_count": len(flagged_comments)
        })
    
    return {"posts": result}

@app.get("/api/moderator/statistics")
def get_statistics(
    user_id: Optional[int] = None,
    moderator: models.User = Depends(get_current_moderator),
    db: Session = Depends(get_db)
):
    """Statistics page - Overall stats + user-specific stats with dropdown"""
    
    if user_id:
        # User-specific statistics
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        total_posts = db.query(models.Post).filter(models.Post.author_id == user_id).count()
        total_comments = db.query(models.Comment).filter(models.Comment.user_id == user_id).count()
        
        approved_comments = db.query(models.Comment).filter(
            models.Comment.user_id == user_id,
            models.Comment.status == "approved"
        ).count()
        
        hidden_comments = db.query(models.Comment).filter(
            models.Comment.user_id == user_id,
            models.Comment.status == "hidden"
        ).count()
        
        pending_comments = db.query(models.Comment).filter(
            models.Comment.user_id == user_id,
            models.Comment.auto_review_action == "human_review_needed"
        ).count()
        
        return {
            "type": "user_stats",
            "user": {
                "id": user.id,
                "username": user.username,
                "created_at": user.created_at
            },
            "stats": {
                "total_posts": total_posts,
                "total_comments": total_comments,
                "approved_comments": approved_comments,
                "hidden_comments": hidden_comments,
                "pending_comments": pending_comments
            }
        }
    
    else:
        # Overall system statistics
        total_users = db.query(models.User).count()
        total_posts = db.query(models.Post).count()
        total_comments = db.query(models.Comment).count()
        
        clean_comments = db.query(models.Comment).filter(
            models.Comment.status == "approved",
            models.Comment.is_abusive == 0
        ).count()
        
        flagged_comments = db.query(models.Comment).filter(
            models.Comment.is_abusive == 1
        ).count()
        
        needs_review = db.query(models.Comment).filter(
            models.Comment.auto_review_action == "human_review_needed"
        ).count()
        
        auto_hidden = db.query(models.Comment).filter(
            models.Comment.auto_review_action == "keep_hidden"
        ).count()
        
        auto_approved = db.query(models.Comment).filter(
            models.Comment.auto_review_action.in_(["approve", "auto_approve"])
        ).count()
        
        # AI efficiency
        ai_processed = auto_approved + auto_hidden
        ai_efficiency = round((ai_processed / total_comments) * 100, 1) if total_comments > 0 else 0
        
        return {
            "type": "overall_stats",
            "stats": {
                "total_users": total_users,
                "total_posts": total_posts,
                "total_comments": total_comments,
                "clean_comments": clean_comments,
                "flagged_comments": flagged_comments,
                "needs_review": needs_review,
                "auto_hidden": auto_hidden,
                "auto_approved": auto_approved,
                "ai_efficiency_percent": ai_efficiency
            }
        }

@app.put("/api/moderator/comments/{comment_id}/review")
def review_comment(comment_id: int,
                  action: schemas.ModerationAction,
                  moderator: models.User = Depends(get_current_moderator),
                  db: Session = Depends(get_db)):
    """Moderator reviews a comment - approve/hide/delete"""
    
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    if action.action == "approve":
        comment.status = "approved"
        comment.is_abusive = 0
        result_message = "Comment approved and made visible"
        
    elif action.action == "hide":
        comment.status = "hidden" 
        comment.is_abusive = 1
        result_message = "Comment hidden from public view"
        
    elif action.action == "delete":
        db.delete(comment)
        db.commit()
        return {"message": "Comment deleted permanently"}
    
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use: approve, hide, delete")
    
    # Update moderation info
    comment.moderated_by = moderator.id
    comment.moderated_at = datetime.utcnow()
    
    db.commit()
    return {"message": result_message, "comment_id": comment.id, "new_status": comment.status}

@app.get("/")
def root():
    return {"message": "Abuse Moderation API is running"}
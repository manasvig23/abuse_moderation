from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware  # Add this import
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

# Add CORS middleware - ADD THIS SECTION
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],  # Vue dev server URLs
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

# ---------------------------
# Authentication Endpoints
# ---------------------------
@app.post("/api/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if username exists
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email exists
    if db.query(models.User).filter(models.User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
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
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

# ---------------------------
# Post Endpoints
# ---------------------------
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
    """Get all posts with approved comments only"""
    posts = db.query(models.Post).order_by(models.Post.created_at.desc()).all()
    
    result = []
    for post in posts:
        # Only show approved comments
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
def get_post_with_comments(post_id: int, db: Session = Depends(get_db)):
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

# ---------------------------
# Comment Endpoints
# ---------------------------
@app.post("/api/comments/")
def create_comment(comment: schemas.CommentCreate, 
                  current_user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Create comment with auto-review system"""
    
    # Validate post exists
    post = db.query(models.Post).filter(models.Post.id == comment.post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Validate comment
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

# ---------------------------
# Moderator Endpoints
# ---------------------------
@app.get("/api/moderator/dashboard")
def get_moderation_dashboard(moderator: models.User = Depends(get_current_moderator),
                           db: Session = Depends(get_db)):
    """Get moderation dashboard"""
    
    # Get hidden/pending comments
    flagged_comments = db.query(models.Comment).filter(
        models.Comment.status.in_(["hidden", "pending_review"])
    ).order_by(models.Comment.created_at.desc()).all()
    
    # Statistics
    total_comments = db.query(models.Comment).count()
    auto_approved = db.query(models.Comment).filter(models.Comment.auto_review_action == "auto_approve").count()
    auto_hidden = db.query(models.Comment).filter(models.Comment.auto_review_action == "keep_hidden").count()
    
    comments_for_review = []
    for comment in flagged_comments:
        comments_for_review.append({
            "id": comment.id,
            "text": comment.text,
            "flagged_words": comment.flagged_words,
            "confidence_score": comment.confidence_score,
            "author_username": comment.author.username,
            "post_id": comment.post_id,
            "created_at": comment.created_at,
            "auto_review_action": comment.auto_review_action,
            "auto_review_reason": comment.auto_review_reason
        })
    
    return {
        "statistics": {
            "total_comments": total_comments,
            "auto_approved": auto_approved,
            "auto_hidden": auto_hidden,
            "pending_review": len(flagged_comments),
        },
        "pending_comments": comments_for_review
    }

@app.put("/api/moderator/comments/{comment_id}/review")
def review_comment(comment_id: int,
                  action: schemas.ModerationAction,
                  moderator: models.User = Depends(get_current_moderator),
                  db: Session = Depends(get_db)):
    """Moderator reviews a flagged comment"""
    
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    
    if action.action == "approve":
        comment.status = "approved"
        comment.is_abusive = 0
        result_message = "Comment approved and made visible"
        
    elif action.action == "confirm_hide":
        comment.status = "hidden" 
        comment.is_abusive = 1
        result_message = "Comment confirmed as abusive and kept hidden"
        
    elif action.action == "delete":
        db.delete(comment)
        db.commit()
        return {"message": "Comment deleted permanently"}
    
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    # Update moderation info
    comment.moderated_by = moderator.id
    comment.moderated_at = datetime.utcnow()
    
    db.commit()
    return {"message": result_message, "comment_id": comment.id, "new_status": comment.status}

@app.get("/")
def root():
    return {"message": "Abuse Moderation API is running"}
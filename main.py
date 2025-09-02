from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
import models, schemas
from filter import is_abusive

# Create tables if not exist
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------
# User Endpoints
# ---------------------------
@app.post("/users/")
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = models.User(username=user.username, email=user.email)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# ---------------------------
# Post Endpoints
# ---------------------------
@app.post("/posts/")
def create_post(post: schemas.PostCreate, db: Session = Depends(get_db)):
    db_post = models.Post(content=post.content)
    db.add(db_post)
    db.commit()
    db.refresh(db_post)
    return db_post

# ---------------------------
# Comment Endpoints
# ---------------------------
@app.post("/comments/")
def create_comment(comment: schemas.CommentCreate, db: Session = Depends(get_db)):
    abuse_flag = 1 if is_abusive(comment.text) else 0
    db_comment = models.Comment(
        text=comment.text,
        is_abusive=abuse_flag,
        user_id=comment.user_id,
        post_id=comment.post_id
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return {"comment": db_comment.text, "is_abusive": db_comment.is_abusive}

# ---------------------------
# GET Endpoint: Fetch posts with comments (hide abusive ones)
# ---------------------------
@app.get("/posts/{post_id}")
def get_post_with_comments(post_id: int, db: Session = Depends(get_db)):
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        return {"error": "Post not found"}

    comments = []
    for c in post.comments:
        if c.is_abusive == 1:
            comments.append({"comment": "[Hidden due to abusive content]"})
        else:
            comments.append({"comment": c.text, "user_id": c.user_id})

    return {
        "post_id": post.id,
        "content": post.content,
        "comments": comments
    }

# ---------------------------
# Moderator Endpoints
# ---------------------------
@app.get("/moderator/comments/")
def get_all_comments(db: Session = Depends(get_db)):
    comments = db.query(models.Comment).all()
    results = []
    for c in comments:
        results.append({
            "id": c.id,
            "text": c.text,
            "is_abusive": c.is_abusive,
            "user_id": c.user_id,
            "post_id": c.post_id
        })
    return {"all_comments": results}


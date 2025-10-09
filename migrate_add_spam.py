from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:root123@localhost:5432/abuse_moderation"
)

engine = create_engine(DATABASE_URL)

def migrate():
    """Add spam detection columns to comments table"""
    with engine.connect() as conn:
        try:
            print("Starting migration...")
            
            # Add is_spam column
            conn.execute(text("""
                ALTER TABLE comments 
                ADD COLUMN IF NOT EXISTS is_spam INTEGER DEFAULT 0
            """))
            print("✓ Added is_spam column")
            
            # Add index on is_spam
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_comments_is_spam 
                ON comments(is_spam)
            """))
            print("✓ Added index on is_spam")
            
            # Add spam_reasons column
            conn.execute(text("""
                ALTER TABLE comments 
                ADD COLUMN IF NOT EXISTS spam_reasons VARCHAR
            """))
            print("✓ Added spam_reasons column")
            
            # Add spam_confidence column
            conn.execute(text("""
                ALTER TABLE comments 
                ADD COLUMN IF NOT EXISTS spam_confidence INTEGER DEFAULT 0
            """))
            print("✓ Added spam_confidence column")
            
            conn.commit()
            print("\nMigration completed successfully!")
            print("Spam detection fields added to database.")
            
        except Exception as e:
            print(f"\nMigration failed: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()
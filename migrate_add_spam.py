from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:root123@localhost:5432/abuse_moderation"
)

engine = create_engine(DATABASE_URL)

def migrate():
    """Add last_login column to users table"""
    with engine.connect() as conn:
        try:
            print("Starting migration to add last_login...")
            
            # Add last_login column
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS last_login TIMESTAMP
            """))
            print("✓ Added last_login column")
            
            # Add index on last_login for performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_users_last_login 
                ON users(last_login)
            """))
            print("✓ Added index on last_login")
            
            conn.commit()
            print("\nMigration completed successfully!")
            print("last_login field added to users table.")
            
        except Exception as e:
            print(f"\nMigration failed: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()
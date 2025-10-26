from sqlalchemy import create_engine, text
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:root123@localhost:5432/abuse_moderation"
)

engine = create_engine(DATABASE_URL)

def migrate():
    """Add admin role and suspended_by field to users table"""
    with engine.connect() as conn:
        try:
            print("Starting migration to add admin features...")
            
            # Add suspended_by column to track who suspended the user
            print("Adding suspended_by column...")
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS suspended_by INTEGER 
                REFERENCES users(id)
            """))
            print("✓ Added suspended_by column")
            
            # Update existing admin user to have admin role
            print("Updating admin role...")
            conn.execute(text("""
                UPDATE users 
                SET role = 'admin' 
                WHERE username = 'admin' AND role = 'moderator'
            """))
            print("✓ Updated admin role")
            
            # Create index on suspended_by for performance
            print("Creating index on suspended_by...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_users_suspended_by 
                ON users(suspended_by)
            """))
            print("✓ Created index on suspended_by")
            
            conn.commit()
            print("\n✅ Migration completed successfully!")
            print("Admin features are now available.")
            print("\nNOTE: Default admin credentials:")
            print("  Username: admin")
            print("  Password: admin123")
            print("  Role: admin (super moderator)")
            
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            conn.rollback()

if __name__ == "__main__":
    migrate()
from app import app, db
from models import AdminUser, Equipment, Service
import os

# Ensure instance directory exists
instance_dir = os.path.join(os.path.dirname(__file__), 'instance')
os.makedirs(instance_dir, exist_ok=True)

def create_database():
    """Create all database tables."""
    with app.app_context():
        # Drop all tables and recreate them
        db.drop_all()
        db.create_all()
        
        print("✓ Database created successfully!")
        print("✓ Tables created:")

if __name__ == "__main__":
    create_database()

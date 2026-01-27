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
        print("  - AdminUser (id, email, password_hash, address, registration_date)")
        print("  - Equipment (id, admin_user_id, code, make, model, mileage, service_date)")
        print("  - Service (id, equipment_id, date, performed_by, mileage, next_service)")

if __name__ == "__main__":
    create_database()

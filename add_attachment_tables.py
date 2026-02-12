from app import app, db
from models import ServiceAttachment, RepairAttachment


def create_attachment_tables():
    """Create attachment tables without dropping existing data."""
    with app.app_context():
        db.create_all()
        print("Attachment tables ensured.")


if __name__ == "__main__":
    create_attachment_tables()

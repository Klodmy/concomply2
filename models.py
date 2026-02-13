from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, ForeignKey, Date, Time
from datetime import datetime, date, time
from db import db

class AdminUser(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    address: Mapped[str] = mapped_column(nullable=True)
    role: Mapped[str] = mapped_column(nullable=False, default="admin")
    registration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

class Equipment(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("admin_user.id"), nullable=False)
    type: Mapped[str] = mapped_column(nullable=False)
    vin_number: Mapped[str] = mapped_column(unique=True, nullable=False)
    code: Mapped[str] = mapped_column(nullable=False)
    make: Mapped[str] = mapped_column(nullable=False)
    model: Mapped[str] = mapped_column(nullable=False)
    qr_token: Mapped[str] = mapped_column(unique=True, nullable=True)
    mileage: Mapped[int] = mapped_column(nullable=True)
    service_required: Mapped[str] = mapped_column(nullable=True)
    last_service_date: Mapped[date] = mapped_column(Date, nullable=True)

class Service(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    performed_by: Mapped[str] = mapped_column(nullable=False)
    mileage: Mapped[int] = mapped_column(nullable=True)
    next_service: Mapped[date] = mapped_column(Date, nullable=True)
    service_cost: Mapped[float] = mapped_column(nullable=True)
    notes: Mapped[str] = mapped_column(nullable=True)

class Service_records(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("service.id"), nullable=False)
    category: Mapped[str] = mapped_column(nullable=False)
    issue_found: Mapped[str] = mapped_column(nullable=True)

class Repair(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    performed_by: Mapped[str] = mapped_column(nullable=False)
    mileage: Mapped[int] = mapped_column(nullable=True)
    repair_cost: Mapped[float] = mapped_column(nullable=True)
    notes: Mapped[str] = mapped_column(nullable=True)

class Repair_records(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    repair_id: Mapped[int] = mapped_column(ForeignKey("repair.id"), nullable=False)
    category: Mapped[str] = mapped_column(nullable=False)
    detail: Mapped[str] = mapped_column(nullable=True)
    cost: Mapped[float] = mapped_column(nullable=True)
    comments: Mapped[str] = mapped_column(nullable=True)

class ServiceCostItem(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("service.id"), nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)

class RepairCostItem(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    repair_id: Mapped[int] = mapped_column(ForeignKey("repair.id"), nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)

class ServiceAttachment(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("service.id"), nullable=False)
    original_name: Mapped[str] = mapped_column(nullable=False)
    stored_name: Mapped[str] = mapped_column(nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

class RepairAttachment(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    repair_id: Mapped[int] = mapped_column(ForeignKey("repair.id"), nullable=False)
    original_name: Mapped[str] = mapped_column(nullable=False)
    stored_name: Mapped[str] = mapped_column(nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

class EquipmentCheckIn(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id"), nullable=False)
    mileage: Mapped[int] = mapped_column(nullable=True)
    issues: Mapped[str] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

class AuditLog(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("admin_user.id"), nullable=True)
    action: Mapped[str] = mapped_column(nullable=False)
    entity: Mapped[str] = mapped_column(nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=True)
    details: Mapped[str] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

class BidTrackerEntry(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True, nullable=False)
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("admin_user.id"), nullable=False)
    line_number: Mapped[int] = mapped_column(nullable=True)
    owner: Mapped[str] = mapped_column(nullable=True)
    project_number: Mapped[str] = mapped_column(nullable=True)
    project_name: Mapped[str] = mapped_column(nullable=True)
    location: Mapped[str] = mapped_column(nullable=True)
    city: Mapped[str] = mapped_column(nullable=True)
    closing_date: Mapped[date] = mapped_column(Date, nullable=True)
    closing_time: Mapped[time] = mapped_column(Time, nullable=True)
    role: Mapped[str] = mapped_column(nullable=True)
    asphalt_tonnage: Mapped[float] = mapped_column(nullable=True)
    bid_type: Mapped[str] = mapped_column(nullable=True)
    estimator_responsible: Mapped[str] = mapped_column(nullable=True)
    submission_status: Mapped[str] = mapped_column(nullable=True)
    notes_comments: Mapped[str] = mapped_column(nullable=True)
    follow_up_notes: Mapped[str] = mapped_column(nullable=True)
    gc_awarded: Mapped[str] = mapped_column(nullable=True)
    amount_award: Mapped[float] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)





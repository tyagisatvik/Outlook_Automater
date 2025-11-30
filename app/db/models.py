"""SQLAlchemy Database Models"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, JSON, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User model for storing user information and OAuth tokens"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    microsoft_user_id = Column(String(255), unique=True, nullable=False)

    # OAuth tokens (encrypted)
    access_token_encrypted = Column(Text, nullable=False)
    refresh_token_encrypted = Column(Text)
    token_expires_at = Column(DateTime)

    # User preferences (JSONB for flexibility)
    preferences = Column(JSON, default={})

    # Expertise tracking for delegation
    expertise_areas = Column(ARRAY(String), default=[])

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)

    # Webhook subscription info
    webhook_subscription_id = Column(String(255))
    webhook_expires_at = Column(DateTime)

    # Relationships
    emails = relationship("Email", back_populates="user", cascade="all, delete-orphan")
    action_items = relationship("ActionItem", back_populates="user", cascade="all, delete-orphan")


class Email(Base):
    """Email model for storing processed emails and AI analysis"""
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Microsoft Graph fields
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    conversation_id = Column(String(255), index=True)
    subject = Column(Text)
    sender = Column(JSON)  # {name, email}
    recipients = Column(JSON)  # [{"name": ..., "email": ...}]

    # Email content
    body_text = Column(Text)
    body_html = Column(Text)

    # Email metadata
    received_at = Column(DateTime, nullable=False, index=True)
    is_read = Column(Boolean, default=False)
    has_attachments = Column(Boolean, default=False)
    importance = Column(String(50))  # low, normal, high

    # AI-generated fields
    summary = Column(Text)
    key_points = Column(JSON)  # ["point1", "point2", ...]
    suggested_actions = Column(JSON)  # [{"action": ..., "priority": ...}]
    sentiment = Column(String(50))  # positive, neutral, negative
    urgency_score = Column(Float)  # 0.0 to 1.0
    category = Column(String(100))  # auto-categorized

    # AI processing metadata
    ai_model_used = Column(String(100))
    processing_time_seconds = Column(Float)
    processed_at = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="emails")
    action_items = relationship("ActionItem", back_populates="email", cascade="all, delete-orphan")


class ActionItem(Base):
    """Action items extracted from emails"""
    __tablename__ = "action_items"

    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Action details
    title = Column(String(500), nullable=False)
    description = Column(Text)
    action_type = Column(String(50))  # reply, delegate, schedule, review
    priority = Column(String(50))  # low, medium, high, urgent

    # Assignment
    assigned_to_id = Column(Integer, ForeignKey("users.id"))
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])

    # Status tracking
    status = Column(String(50), default="pending")  # pending, in_progress, completed, cancelled
    due_date = Column(DateTime)
    completed_at = Column(DateTime)

    # AI recommendation metadata
    confidence_score = Column(Float)  # 0.0 to 1.0
    recommendation_reason = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    email = relationship("Email", back_populates="action_items")
    user = relationship("User", foreign_keys=[user_id], back_populates="action_items")


class AICache(Base):
    """Cache for AI responses to reduce costs and improve performance"""
    __tablename__ = "ai_cache"

    id = Column(Integer, primary_key=True, index=True)

    # Cache key (hash of input)
    cache_key = Column(String(64), unique=True, nullable=False, index=True)

    # Cache type (summary, actions, reply, etc.)
    cache_type = Column(String(50), nullable=False, index=True)

    # Cached response
    response_data = Column(JSON, nullable=False)

    # Metadata
    model_used = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    hit_count = Column(Integer, default=0)

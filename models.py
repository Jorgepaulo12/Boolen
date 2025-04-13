from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, DateTime, Float, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import random
import string

Base = declarative_base()

def generate_course_code():
    """Gera um código único de 6 dígitos para o curso"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def generate_enrollment_code():
    """Gera um código único de 8 dígitos para a matrícula"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    username = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))
    profile_picture = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    courses_downloaded = relationship("CourseDownload", back_populates="user")
    courses_created = relationship("Course", back_populates="instructor")
    wallet = relationship("Wallet", back_populates="user", uselist=False)

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="wallet")
    transactions = relationship("WalletTransaction", back_populates="wallet")

class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"))
    amount = Column(Float)
    transaction_type = Column(String(50))  # deposit, purchase, etc.
    payment_ref = Column(String(255), nullable=True)
    status = Column(String(50))  # pending, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    wallet = relationship("Wallet", back_populates="transactions")

class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String(6), unique=True, index=True, nullable=False)
    title = Column(String(255), index=True)
    description = Column(Text)
    price = Column(Float)
    duration_minutes = Column(Integer)
    cover_image = Column(String(255))  # caminho para a imagem de capa
    file_path = Column(String(255))
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="draft")  # draft, published, archived
    instructor = relationship("User", back_populates="courses_created")
    downloads = relationship("CourseDownload", back_populates="course")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.course_code:
            self.course_code = generate_course_code()

class CourseDownload(Base):
    __tablename__ = "course_downloads"

    id = Column(Integer, primary_key=True, index=True)
    enrollment_code = Column(String(8), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    transaction_id = Column(Integer, ForeignKey("wallet_transactions.id"))
    downloaded_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default="active")  # active, completed, cancelled
    progress = Column(Float, default=0.0)  # Progresso do curso em porcentagem
    last_accessed = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="courses_downloaded")
    course = relationship("Course", back_populates="downloads")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.enrollment_code:
            self.enrollment_code = generate_enrollment_code()

    __table_args__ = (
        UniqueConstraint('user_id', 'course_id', name='uq_user_course'),
    )

class CourseLike(Base):
    __tablename__ = "course_likes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="course_likes")
    course = relationship("Course", backref="likes")

    __table_args__ = (
        UniqueConstraint('user_id', 'course_id', name='uq_user_course_like'),
    )
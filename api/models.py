from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Index , Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from enum import Enum as PyEnum
Base = declarative_base()

class TimestampMixin:
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

class RoleType(PyEnum):
    ADMIN = 'admin'
    INSTRUCTOR = 'instructor'
    STUDENT = 'student'


class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    role_name = Column(SQLAlchemyEnum(RoleType), unique=True, nullable=False)
    users = relationship("User", back_populates="role")
    
    def __repr__(self):
        return f"<Role(id={self.id}, name={self.role_name})>"

class User(Base, TimestampMixin):
    __tablename__ = 'users'
    __table_args__ = (Index('ix_user_email', 'email'),)
    id = Column(Integer, primary_key=True)
    user_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    role = relationship("Role", back_populates="users")
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan", lazy='joined')
    courses = relationship("Course", back_populates="instructor")
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.user_name}, email={self.email})>"

class UserProfile(Base, TimestampMixin):
    __tablename__ = 'user_profiles'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    bio = Column(Text)
    profile_picture = Column(Text)
    additional_info = Column(Text)
    user = relationship("User", back_populates="profile")
    
    def __repr__(self):
        return f"<UserProfile(user_id={self.user_id}, name={self.first_name} {self.last_name})>"

class Course(Base, TimestampMixin):
    __tablename__ = 'courses'
    __table_args__ = (Index('ix_course_instructor_id', 'course_instructor_id'),)
    id = Column(Integer, primary_key=True)
    title = Column(String, unique=True, nullable=False)
    description = Column(Text, nullable=True)
    course_instructor_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    instructor = relationship("User", back_populates="courses")
    modules = relationship("Module", back_populates="course", cascade="all, delete-orphan", lazy='selectin')
    
    def __repr__(self):
        return f"<Course(id={self.id}, title={self.title})>"

class Module(Base, TimestampMixin):
    __tablename__ = 'modules'
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    course = relationship("Course", back_populates="modules")
    
    def __repr__(self):
        return f"<Module(id={self.id}, title={self.title})>"

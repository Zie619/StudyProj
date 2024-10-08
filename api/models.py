# models.py

from sqlalchemy import Column, Integer, String,Text, ForeignKey,DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime , timezone

Base = declarative_base()

# Define Role model
class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    role_name = Column(String, unique=True, nullable=False)
    
    # Relationship with User
    users = relationship("User", back_populates="role")
    
    def __repr__(self):
        return f"<Role (id={self.id}, name={self.role_name}>"
    
# Define UserProfile model
class UserProfile(Base):
    __tablename__ = 'user_profiles'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    bio = Column(String)  # Optional bio or description
    profile_picture = Column(String)  # Path to profile picture
    additional_info = Column(String)  # Any other relevant info, like student/teacher specific data
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    # Relationship with User
    user = relationship("User", back_populates="profile")
    
    def __repr__(self):
        return f"<User(id={self.user_id}, first_name={self.first_name}, last_name={self.last_name})>"
    
# Define User model
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    user_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role_id = Column(Integer, ForeignKey('roles.id'), nullable=False)

    # Relationship with Role
    role = relationship("Role", back_populates="users")
    courses = relationship("Course", back_populates="instructor")
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    def __repr__(self):
        return f"<Username(id={self.id}, user_name={self.user_name}, email={self.email}, role_id={self.role_id})>"

# Define Courses model
class Course(Base):
    __tablename__ = 'courses'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    course_instructor_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Relationship to link to the instructor (User)
    instructor = relationship("User", back_populates="courses")

    # Relationship to link modules to the course
    modules = relationship("Module", back_populates="course", cascade="all, delete-orphan")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    def __repr__(self):
        return f"<Course(id={self.id}, title={self.title}, course_instructor_id={self.course_instructor_id})>"


class Module(Base):
    __tablename__ = 'modules'

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=True)  # Detailed content or description of the module

    # Relationship back to the course
    course = relationship("Course", back_populates="modules")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    def __repr__(self):
        return f"<Module(id={self.id}, title={self.title}, course_id={self.course_id})>"

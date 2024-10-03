# models.py

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# Define Role model
class Role(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    role_name = Column(String, unique=True, nullable=False)
    
    # Relationship with User
    users = relationship("User", back_populates="role")

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

    # Relationship with User
    user = relationship("User", back_populates="profile")

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

    profile = relationship("UserProfile", back_populates="user", uselist=False)

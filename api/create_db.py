from sqlalchemy import Column, Integer, String, ForeignKey, create_engine
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.inspection import inspect
from dotenv import load_dotenv
import os

# Import models and RoleType
try:
    from .models import Base, Role, User, UserProfile, Course, Module, RoleType, Enroll  # Relative import
except ImportError:
    from models import Base, Role, User, UserProfile, Course, Module, RoleType, Enroll  # Direct import for terminal

# Load the .env file
load_dotenv()

# Function to establish the database
def create_db():
    # Connect to the database (replace with your desired database URL)
    engine = create_engine(os.getenv("SQLALCHEMY_DATABASE_URI"), echo=False)
    
    # Check if tables already exist
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if not set(Base.metadata.tables.keys()).issubset(set(tables)):
        # Create all tables if they don't exist
        Base.metadata.create_all(engine)
        print("Tables created.")
    else:
        print("Tables already exist. Skipping creation.")
    
    # Create a new session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check if roles already exist before adding them
    existing_roles = {role.role_name for role in session.query(Role).all()}
    default_roles = {RoleType.ADMIN, RoleType.INSTRUCTOR, RoleType.STUDENT}

    roles_to_add = [Role(role_name=role) for role in default_roles if role not in existing_roles]

    if roles_to_add:
        session.add_all(roles_to_add)
        session.commit()
        print(f"Added missing roles: {', '.join([role.role_name.value for role in roles_to_add])}")
    else:
        print("All default roles already exist.")

if __name__ == "__main__":
    create_db()

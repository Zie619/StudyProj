from sqlalchemy import Column, Integer, String, ForeignKey, create_engine, text
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.inspection import inspect
from sqlalchemy.dialects.postgresql import ENUM
from dotenv import load_dotenv
import os

# Import models and RoleType
try:
    from .models import Base, Role, User, UserProfile, Course, Module, RoleType, Enroll  # Relative import
except ImportError:
    from models import Base, Role, User, UserProfile, Course, Module, RoleType, Enroll  # Direct import for terminal

# Load the .env file
load_dotenv()

# Define the ENUM type separately to prevent automatic creation
role_type_enum = ENUM('ADMIN', 'INSTRUCTOR', 'STUDENT', name='roletype', create_type=False)

# Function to establish the database
def create_db():
    # Connect to the database (replace with your desired database URL)
    engine = create_engine(os.getenv("SQLALCHEMY_DATABASE_URI"), echo=False)
    
    # Create a connection for checking existing ENUM types or other database-specific objects.
    with engine.connect() as connection:
        # Check if the ENUM type 'roletype' exists and create it if it doesn't
        result = connection.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'roletype');")
        )
        exists = result.scalar()
        
        if not exists:
            # Create the ENUM type if it doesn't exist
            role_type_enum.create(engine, checkfirst=True)
            print("ENUM 'roletype' created.")
        else:
            print("ENUM 'roletype' already exists. Skipping creation.")

    # Use create_all to create all tables that are defined in the metadata
    Base.metadata.create_all(engine, checkfirst=True)
    print("Tables created where necessary.")

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

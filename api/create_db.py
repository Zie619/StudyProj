from sqlalchemy import Column, Integer, String, ForeignKey, create_engine
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv
import os
from api.models import Base, Role, User, UserProfile  # Import models

# Load the .env file
load_dotenv()


# Function to establish the database
def create_db():
    # Connect to an SQLite database (or replace with your desired database URL)
    engine = create_engine(os.getenv("SQLALCHEMY_DATABASE_URI"), echo=True)
    
    # Create all tables
    Base.metadata.create_all(engine)

    # Create a new session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Add default roles (Admin, Instructor, Student)
    admin_role = Role(role_name="Admin")
    instructor_role = Role(role_name="Instructor")
    student_role = Role(role_name="Student")
    
    session.add_all([admin_role, instructor_role, student_role])
    session.commit()
    print("Database created and default roles added!")

if __name__ == "__main__":
    create_db()

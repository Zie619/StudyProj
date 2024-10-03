# README

## Project: Online Learning Platform with Video Streaming and Progress Tracking

### Overview
This project is an online learning platform backend API that focuses on secure user management, video streaming, course progress tracking, and role-based access control (RBAC). The platform integrates key features like JWT authentication, Redis caching, and a modular architecture, allowing scalability and flexibility as the system grows.

This project is for me to learn and improve my backend workaround to find a job as a developer.
If you find this project useful you may use it.

### Features
- **User Authentication**: JWT-based authentication with role-based access control (Admin, Instructor, Student).
- **Role Management**: Users can have different roles with specific permissions.
- **Video Streaming**: Secure video access using signed URLs.
- **Progress Tracking**: Track user progress in courses and quizzes.
- **Redis Caching**: Used for JWT token revocation and session management.
- **Course Management**: CRUD operations for courses, modules, and quizzes.
- **Token Revocation**: Redis is used to manage JWT token revocation for secure logout functionality.

### Current Setup
- **Tech Stack**: 
  - Backend: Python (with Flask)
  - Database: SQLAlchemy for relational database management (PostgreSQL)
  - Caching: Redis
  - Authentication: JWT tokens
  - Video Storage: Cloud-based (AWS S3) -- not yet created

### Folder Structure
- `api.py`: Manages API endpoints for user authentication, course management, and role management.
inside the folder you can find:
- `create_db.py`: Initializes the database, setting up tables such as `User`, `Role`, and user profiles.
- `models.py`: Defines the database models including `User`, `Role`, and `Profile`.
- `api.py` to start the server and test endpoints.

### Future Enhancements
- **OAuth Support**: Integration of OAuth for external logins via providers like Google or Facebook.
- **Real-time Notifications**: Implement WebSockets or Socket.IO for real-time notifications such as course updates or quiz results.
- **Certificate Generation**: Automated generation and distribution of course completion certificates, stored securely in cloud storage (e.g., AWS S3).
- **Quiz System**: Create a dynamic quiz system where instructors can build quizzes, and students can submit answers and receive results.
- **Advanced Progress Tracking**: Enhance progress tracking with detailed analytics, including video watch time and quiz performance.
- **Messaging Queue Integration**: Use RabbitMQ or Kafka for asynchronous tasks such as sending notifications, processing certificates, and handling long-running jobs.
- **Microservices Architecture**: Modularize the platform into distinct microservices (authentication, course management, etc.) to improve scalability and maintainability. 
- **Cloud Infrastructure**: Dockerize the services and deploy using Kubernetes for container orchestration and auto-scaling.


### How to Run
first setup posgresql db or any other db for your chosing locally or on your server.
initiat redis locally or on your server.

1. Set up your environment and install dependencies (pip install -r /path/to/requirements.txt).
2. Configure the database using environment variables.( Create an .env file with those params):
SQLALCHEMY_DATABASE_URI=postgresql://user:pass@localhost:5432/your_db_name
ADMIN_INVITE_CODE=your_code_here
JWT_SECRET_KEY=your_code_here
3. Run `create_db.py` to set up initial roles and database schema.
4. Launch `api.py` to start the server and test endpoints.

---

This is a simple, initial overview of the platform, and will be updated as the project evolves.
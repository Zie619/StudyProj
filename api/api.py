from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required , get_jwt , decode_token , get_jwt_identity
from sqlalchemy import create_engine, DateTime, Column
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
try:
    from .models import Base, Role, User, UserProfile, Course, Module, RoleType, Enroll  # Relative import
except ImportError:
    from models import Base, Role, User, UserProfile, Course, Module, RoleType, Enroll  # Direct import for terminal

from datetime import timedelta , datetime , timezone
import bcrypt
import os
import redis
import hashlib


######################################################## INITIALIZATION #######################################################################
# Load environment variables from .env file
load_dotenv()

# Initialize Redis
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

# Initialize Flask app
app = Flask(__name__)

# PostgreSQL database configuration (loaded from .env file)
ADMIN_INVITE_CODE = os.getenv("ADMIN_INVITE_CODE", "secret_code") 

app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY")
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=60)

# Initialize JWT manager
jwt = JWTManager(app)

# Create SQLAlchemy engine and session
engine = create_engine(os.getenv("SQLALCHEMY_DATABASE_URI"), echo=True)
Session = sessionmaker(bind=engine)
session = Session()

# Create database tables if they don't exist
Base.metadata.create_all(engine)


@jwt.token_in_blocklist_loader
def check_if_token_in_blocklist(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    user_name = jwt_payload['sub']['user_name']  # Extract user_name from the JWT payload

    # Check if the jti is in the Redis set for this user
    return redis_client.sismember(f"revoked_tokens:{user_name}", jti)

@jwt.revoked_token_loader
def revoked_token_response(jwt_header, jwt_payload):
    return jsonify({"message": "Your token has been revoked. Please login again."}), 401

@jwt.expired_token_loader
def expired_token_response(jwt_header, jwt_payload):
    return jsonify({"message": "Your session has expired. Please log in again."}), 401


def generate_device_fingerprint():
    # Get the user's IP address from the request headers
    user_ip = request.remote_addr

    # Get the User-Agent from the request headers (this contains browser and OS info)
    user_agent = request.headers.get('User-Agent')

    # Combine IP and User-Agent to create a unique "fingerprint" for the device
    fingerprint_data = f"{user_ip}:{user_agent}"

    # Hash the fingerprint data to create a unique identifier
    fingerprint_hash = hashlib.sha256(fingerprint_data.encode()).hexdigest()

    return fingerprint_hash


def revoke_token_for_fingerprint(user_name, fingerprint):
    old_token_jti = redis_client.get(f"active_token:{user_name}:{fingerprint}")
    if old_token_jti:
        # Add the old token jti to the user's set of revoked tokens
        redis_client.sadd(f"revoked_tokens:{user_name}", old_token_jti)
        # Optionally, set a TTL on the set (or individual entries) to clean it up after token expiration
        redis_client.expire(f"revoked_tokens:{user_name}", timedelta(hours=1))

        # Remove the old active token reference
        redis_client.delete(f"active_token:{user_name}:{fingerprint}")


###############################################################################################################################################
########################################################### AUTHENTICATION ####################################################################
# Route to register a new user
@app.route('/auth/register', methods=['POST'])
def register():
    data = request.get_json()

    required_fields = {'user_name', 'email', 'password', 'role', 'first_name', 'last_name'}
    optional_fields = {'bio', 'profile_picture', 'additional_info', 'invite_code'}
    all_valid_fields = required_fields.union(optional_fields)

    # Check for unexpected fields in the incoming data
    for key in data.keys():
        if key not in all_valid_fields:
            return jsonify({"message": f"Unexpected field: {key}"}), 400

    # Check if all required fields are provided
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"message": f"{field} is required!"}), 400

    # Check if the user already exists
    if session.query(User).filter_by(user_name=data['user_name']).first() or session.query(User).filter_by(email=data['email']).first():
        return jsonify({"message": "User already exists!"}), 400

    # Validate and convert the role string to the RoleType enum
    try:
        role_type = RoleType(data['role'].lower())
    except ValueError:
        return jsonify({"message": "Invalid role provided. Choose from 'admin', 'instructor', or 'student'."}), 400
    role = session.query(Role).filter_by(role_name=role_type).first()
    
    # Check if the current user is trying to register as an admin
    if role_type == RoleType.ADMIN:
        if 'invite_code' not in data or data['invite_code'] != ADMIN_INVITE_CODE:
            return jsonify({"message": "Invalid or missing admin invite code!"}), 403

    # Hash the password using bcrypt
    hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
    
    # Start a transaction to ensure atomic operations
    try:
        # Create a new user
        new_user = User(
            user_name=data['user_name'].strip(),
            email=data['email'].strip(),
            password_hash=hashed_password.decode('utf-8'),
            role_id=role.id
        )

        # Add the new user to the session
        session.add(new_user)
        session.commit()  # This will generate new_user.id

        # Now create the profile and link it to the user
        new_profile = UserProfile(
            user_id=new_user.id,  # Link to the created user
            first_name=data['first_name'].strip(),
            last_name=data['last_name'].strip(),
            bio=data.get('bio', '').strip(),  # Optional field, use default empty string
            profile_picture=data.get('profile_picture', ''),  # Optional
            additional_info=data.get('additional_info', '')  # Optional
        )

        # Add the new profile to the session
        session.add(new_profile)
        session.commit()

        return jsonify({"message": "User and profile created successfully!"}), 201

    except SQLAlchemyError as e:
        session.rollback()  # Rollback the transaction on error
        return jsonify({"message": "Error occurred while creating user or profile", "error": str(e)}), 500

# Route to login the user
@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()

    # Find the user by name
    user = session.query(User).filter_by(user_name=data['user_name']).first()

    # Check if the user exists and the password matches
    if not user or not bcrypt.checkpw(data['password'].encode('utf-8'), user.password_hash.encode('utf-8')):
        return jsonify({"message": "Invalid credentials"}), 401

    # Generate the device fingerprint based on IP and User-Agent
    device_fingerprint = generate_device_fingerprint()

    # Revoke the previous token for this user on this specific device (if any)
    revoke_token_for_fingerprint(user.user_name, device_fingerprint)

    # Create a new access token
    access_token = create_access_token(identity={'user_name': user.user_name, 'role': user.role.role_name.value})
    decoded_token = decode_token(access_token)
    jti = decoded_token['jti']  # Extract the JTI from the decoded token

    # Store the new JTI in Redis as the active token for this device
    redis_client.set(f"active_token:{user.user_name}:{device_fingerprint}", jti)

    return jsonify(access_token=access_token), 200

# Protected route that requires a valid JWT token


@app.route('/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    # Get the current token's jti (unique identifier)
    jti = get_jwt()['jti']
    identity = get_jwt_identity()
    user_name = identity.get("user_name")

    # Add the token's jti to the user's revoked set
    redis_client.sadd(f"revoked_tokens:{user_name}", jti)

    # Generate the device fingerprint and remove the active token reference
    device_fingerprint = generate_device_fingerprint()
    redis_client.delete(f"active_token:{user_name}:{device_fingerprint}")

    return jsonify(message="Successfully logged out"), 200

@app.route('/auth/role', methods=['GET'])
@jwt_required()
def role():
    jwt_data = get_jwt()  # Get the JWT token payload
    user_role_name = jwt_data['sub']['role']  # Access the 'role' from the 'identity' (stored in 'sub')

    # Query to get all roles from the database
    roles = session.query(Role).all()
    # List of role names
    role_names = [role.role_name.value for role in roles]
    # Query to find the full user role object (based on the name from JWT)
    user_role = session.query(Role).filter_by(role_name=RoleType(user_role_name)).first()

    # Construct the response
    response = {
        "message": f"You have access to the protected route with role: {user_role.role_name.value}",
        "roles_list": role_names,
        "user_role": {"id": user_role.id, "name": user_role.role_name.value}
    }
    # Return the response as JSON
    return jsonify(response)


@app.route('/auth/profile', methods=['GET'])
@jwt_required()
def profile():
    jwt_data = get_jwt()  # Get the JWT token payload
    user_name = jwt_data['sub']['user_name']  # Access the 'user_name' from the 'identity' (stored in 'sub')
    
    # Query to get user profile and user data using a join
    user_data_table = (
        session.query(UserProfile, User)
        .join(User, UserProfile.user_id == User.id)
        .filter(User.user_name == user_name)
        .first()
    )

    if not user_data_table:
        return jsonify({"message": "User profile not found"}), 404

    user_profile, user = user_data_table  # Unpack the tuple into UserProfile and User
    response = {
        "message": "You have access to your user profile information.",
        "user_profile": {
            "user_id": user.id,
            "user_name": user_name,
            "user_role": user.role.role_name.value, 
            "email": user.email,
            "bio": user_profile.bio,
            "first_name": user_profile.first_name,
            "last_name": user_profile.last_name
        }
    }

    # Return the response as JSON
    return jsonify(response), 200

###############################################################################################################################################
############################################################## USERS ##########################################################################

@app.route('/users', methods=['GET'])
@jwt_required()  # Ensure the user is authenticated
def get_users():
    # Check if the current user is an Admin
    current_user_role = get_jwt_identity()['role']
    if current_user_role.lower() != 'admin':
        return jsonify({"message": "You do not have access to this resource"}), 403
    
    # Get the 'limit' query parameter from the request (default to 10 if not provided)
    limit = request.args.get('limit', default=10, type=int)
    
    # Get users from the database with the specified limit
    users = session.query(User).limit(limit).all()
    
    # Convert users to a list of dictionaries
    user_list = [{"id": user.id, "role": user.role_id, "name": user.user_name, "email": user.email} for user in users]
    
    return jsonify(user_list)


@app.route('/users/<int:id>', methods=['GET'])
@jwt_required()
def get_user_profile(id):
    # Query to get all roles from the database
    user_data_table = session.query(UserProfile, User).join(User, UserProfile.user_id == User.id).filter_by(id=id).first()

    if user_data_table:
        user_profile, user = user_data_table  # Unpack the tuple into UserProfile and User
        return jsonify({
            "user_id":user_profile.user_id, 
            "user_name":user.user_name, 
            "email":user.email,
            "bio":user_profile.bio,
            "first_name":user_profile.first_name,
            "last_name":user_profile.last_name,
            "user_role": user.role.role_name.value,
        })
    else:
        return jsonify({"message": "User not found"}), 404


@app.route('/users/<int:id>/role', methods=['PUT'])
@jwt_required()
def update_user_role(id):
    user_name = get_jwt_identity()['user_name']
    current_user_role = get_jwt_identity()['role']
    user = session.query(User).filter_by(id=id).first()
    data = request.get_json()
    role_check = session.query(Role).filter_by(role_name=RoleType(data.get('role').lower())).first()
    if not role_check:
        return jsonify({"message": "Role does not exist!"}), 400
    
    new_role = data.get('role') 
    if user:

        if user.user_name != user_name and current_user_role.lower() != 'admin':
            return jsonify({"message": "You do not have permission to change roles for other users"}), 403
        

        if user.user_name == user_name and new_role.lower() == "admin" and current_user_role.lower() != 'admin':
            if 'invite_code' not in data or data['invite_code'] != ADMIN_INVITE_CODE:
                return jsonify({"message": "You do not have permission to change your role to admin"}), 403
            
        user.role_id = session.query(Role).filter_by(role_name=RoleType(data.get('role').lower())).first().id  # Assume the role is stored as a simple field in User table
        session.commit()
        if user.user_name == user_name:
            logout()
            return jsonify({"message": "Your role updated successfully - Please login again"})
        return jsonify({"message": "The user role updated successfully"})
    else:
        return jsonify({"message": "User not found"}), 404



@app.route('/users/<int:id>', methods=['PUT'])
@jwt_required()
def update_user_profile(id):
    user_profile = session.query(UserProfile).filter_by(user_id=id).first()
    jwt_data = get_jwt()
    user_name = jwt_data['sub']['user_name']
    user_role = jwt_data['sub']['role']
    user = session.query(User).filter_by(user_name=user_name).first()
    if user.id != user_profile.user_id and user_role.lower() != 'admin':
        return jsonify({"message": "You do not have permission to change roles"}), 403
    if not user_profile:
        return jsonify({"message": "User profile not found"}), 404

    data = request.get_json()

    # Check 'first_name' if provided and ensure it's not empty
    if 'first_name' in data:
        if data['first_name'].strip() == "":
            return jsonify({"message": "First name cannot be empty"}), 400
        user_profile.first_name = data['first_name'].strip()

    # Check 'last_name' if provided and ensure it's not empty
    if 'last_name' in data:
        if data['last_name'].strip() == "":
            return jsonify({"message": "Last name cannot be empty"}), 400
        user_profile.last_name = data['last_name'].strip()

    # Update 'bio' if provided; allow it to be empty if needed
    if 'bio' in data:
        user_profile.bio = data['bio'].strip()

    session.commit()
    return jsonify({"message": "Profile updated successfully"}), 200



@app.route('/users/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_user(id):
    current_user_role = get_jwt_identity()['role']
    if current_user_role.lower() != 'admin':
        return jsonify({"message": "You do not have permission to delete users"}), 403

    user = session.query(User).filter_by(id=id).first()
    if user:
        session.delete(user)
        session.commit()
        return jsonify({"message": "User deleted successfully"}), 200
    else:
        return jsonify({"message": "User not found"}), 404

###############################################################################################################################################
############################################################## COURSES ########################################################################

@app.route('/courses', methods=['POST'])
@jwt_required()
def create_course():
    current_user = get_jwt_identity()
    user_role = current_user['role']
    user_id = session.query(User).filter_by(user_name=current_user['user_name']).first().id
    # Ensure only instructors can create courses
    if user_role != 'instructor' and user_role != 'admin':
        return jsonify({"message": "Only instructors can create courses."}), 403
    data = request.get_json()
    title = data.get('title').strip()
    description = data.get('description', '')
    if not title:
        return jsonify({"message": "Title is required."}), 400
    # Check if the course already exists
    if session.query(Course).filter_by(title=title).first():
        return jsonify({"message": "Title alread exists for a different course, use a different name!"}), 400
    new_course = Course(
        title=title,
        description=description,
        course_instructor_id=user_id
    )
    session.add(new_course)
    session.commit()
    return jsonify({"message": "Course created successfully!", "course_id": new_course.id}), 201

@app.route('/courses', methods=['GET'])
def list_courses():
    # Get the 'limit' query parameter from the request (default to 10 if not provided)
    limit = request.args.get('limit', default=10, type=int)
    courses = session.query(Course).limit(limit).all()
    course_list = [{"id": course.id, "title": course.title, "description": course.description} for course in courses]
    return jsonify({"courses": course_list}), 200

@app.route('/courses/<int:id>', methods=['GET'])
@jwt_required()
def get_course_details(id):
    course = session.query(Course).filter_by(id=id).first()
    if not course:
        return jsonify({"message": "Course not found."}), 404
    modules = [{"id": module.id, "title": module.title, "content": module.content} for module in course.modules]
    response = {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "modules": modules
    }
    return jsonify(response), 200

@app.route('/courses/<int:id>', methods=['PUT'])
@jwt_required()
def update_course(id):
    current_user = get_jwt_identity()
    user_role = current_user['role']
    # Get the course to update
    course = session.query(Course).filter_by(id=id).first()
    if not course:
        return jsonify({"message": "Course not found."}), 404
    # Ensure only the instructor who created the course or an admin can update it
    if course.instructor.user_name != current_user['user_name'] and user_role != 'admin':
        return jsonify({"message": "You do not have permission to update this course."}), 403
    data = request.get_json()
    title = data.get('title').strip()
    if 'title' in data:
        if data['title'].strip() == "":
            return jsonify({"message": "Title can not be empty"}), 400
        current_title = session.query(Course).filter_by(title=data['title']).first()
        if current_title and current_title.id != id:
            return jsonify({"message": "Title alread exists in a different Course, use a different name!"}), 400
        course.title = title
    else:
        course.title = course.title
    course.description = data.get('description', course.description)
    session.commit()
    return jsonify({"message": "Course updated successfully."}), 200

@app.route('/courses/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_course(id):
    current_user = get_jwt_identity()
    user_role = current_user['role']
    course = session.query(Course).filter_by(id=id).first()
    if not course:
        return jsonify({"message": "Course not found."}), 404
    # Ensure only the instructor who created the course or an admin can delete it
    if course.instructor.user_name != current_user['user_name'] and user_role != 'admin':
        return jsonify({"message": "You do not have permission to delete this course."}), 403
    session.delete(course)
    session.commit()
    return jsonify({"message": "Course deleted successfully."}), 200

###############################################################################################################################################
############################################################## MODULE #########################################################################

@app.route('/courses/<int:id>/modules', methods=['POST'])
@jwt_required()
def add_module_to_course(id):
    current_user = get_jwt_identity()
    user_role = current_user['role']
    if user_role != 'instructor' and user_role != 'admin':
        return jsonify({"message": "Only instructors can add modules."}), 403
    course = session.query(Course).filter_by(id=id).first()
    if not course:
        return jsonify({"message": "Course not found."}), 404
    if course.instructor.user_name != current_user['user_name'] and user_role != 'admin':
        return jsonify({"message": "You are not the instructor of this course."}), 403
    data = request.get_json()
    title = data.get('title').strip()
    content = data.get('content', '')
    if not title:
        return jsonify({"message": "Module title is required."}), 400
    if session.query(Module).filter_by(title=data['title'], course_id=id).first():
        return jsonify({"message": "Title alread exists for a different module, use a different name!"}), 400
    if data['title'] == '':
        return jsonify({"message": "Title cannot be empty!"}), 400
    new_module = Module(
        course_id=course.id,
        title=title,
        content=content
    )
    session.add(new_module)
    session.commit()
    return jsonify({"message": "Module added successfully!", "module_id": new_module.id}), 201

@app.route('/courses/<int:id>/modules', methods=['GET'])
@jwt_required()
def get_modules(id):
    limit = request.args.get('limit', default=10, type=int)
    course = session.query(Course).filter_by(id=id).first()
    if not course:
        return jsonify({"message": "Course not found."}), 404
    # Retrieve the module and ensure it belongs to the specified course
    if not course.modules:
        return jsonify({"message": "Module not found in the specified course."}), 404
    module_data = [{"id": module.id, "title": module.title, "content": module.content} for module in course.modules[:limit]]
    return jsonify({"modules": module_data}), 200

@app.route('/courses/<int:id>/modules/<int:moduleId>', methods=['GET'])
@jwt_required()
def get_module(id, moduleId):
    # Ensure the course exists
    module = session.query(Module).filter_by(id=moduleId, course_id=id).first()
    if not module:
        return jsonify({"message": "Module not found. make sure module id and course id exist"}), 404
    
    response = {
        "id": module.id,
        "title": module.title,
        "content": module.content,
        "course_id": module.course_id,
    }
    # Return the response with a 200 status code
    return jsonify(response), 200

@app.route('/courses/<int:id>/modules/<int:moduleId>', methods=['PUT'])
@jwt_required()
def update_module(id, moduleId):
    current_user = get_jwt_identity()
    user_role = current_user['role']
    module = session.query(Module).filter_by(id=moduleId, course_id=id).first()
    if not module:
        return jsonify({"message": "Module not found."}), 404
    if module.course.instructor.user_name != current_user['user_name'] and user_role != 'admin':
        return jsonify({"message": "You do not have permission to delete this module."}), 403
    data = request.get_json()
    title = data.get('title').strip()
    if 'title' in data:
        if data['title'].strip() == "":
            return jsonify({"message": "Title can not be empty"}), 400
        current_title = session.query(Module).filter_by(title=data['title'], course_id=id).first()
        if current_title and current_title.id != moduleId:
            return jsonify({"message": "Title alread exists in a different Module, use a different name!"}), 400
        module.title = title
    else:
        module.title = module.title
    module.content = data.get('content', module.content)
    session.commit()
    return jsonify({"message": "Module updated successfully."}), 200


@app.route('/courses/<int:id>/modules/<int:moduleId>', methods=['DELETE'])
@jwt_required()
def delete_module_from_course(id, moduleId):
    current_user = get_jwt_identity()
    user_role = current_user['role']
    module = session.query(Module).filter_by(id=moduleId, course_id=id).first()
    if not module:
        return jsonify({"message": "Module not found."}), 404
    course = session.query(Course).filter_by(id=id).first()
    # Ensure only the instructor of the course or an admin can delete the module
    if course.instructor.user_name != current_user['user_name'] and user_role != 'admin':
        return jsonify({"message": "You do not have permission to delete this module."}), 403
    session.delete(module)
    session.commit()
    return jsonify({"message": "Module deleted successfully."}), 200

###############################################################################################################################################
############################################################## ENROLL #########################################################################


@app.route('courses/<int:id>/enroll', methods=['POST'])
@jwt_required
def enroll_to_course(id):
    current_user = get_jwt_identity()
    user_name = current_user['user_name']
    user_role = current_user['role']
    user_id = session.query(User).filter_by(user_name=user_name).first().id
    if user_role != 'student':
        return jsonify({"message": "Only student can enroll."}), 403
    course = session.query(Course).filter_by(id=id).first()
    if not course:
        return jsonify({"message": "Course not found."}), 404
    
    new_enroll = Module(
        course_id=course.id,
        user_id=user_id
    )
    session.add(new_enroll)
    session.commit()
    return jsonify({"message": "Enrolled to course successfuly!", "course id": id, "user": user_name}), 201


# Start the Flask application
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

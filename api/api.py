from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required , get_jwt , decode_token , get_jwt_identity
from sqlalchemy import create_engine, DateTime, Column
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from dotenv import load_dotenv
try:
    from .models import Base, Role, User, UserProfile, Course, Module  # Relative import
except ImportError:
    from models import Base, Role, User, UserProfile, Course, Module  # Direct import for terminal

from datetime import timedelta , datetime , timezone
import bcrypt
import os
import redis
import hashlib

# Load environment variables from .env file
load_dotenv()

# Initialize Redis
redis_client = redis.StrictRedis(host='localhost', port=6379, db=0, decode_responses=True)

# Initialize Flask app
app = Flask(__name__)

# PostgreSQL database configuration (loaded from .env file)
ADMIN_INVITE_CODE = os.getenv("ADMIN_INVITE_CODE", "secret_code") 

app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY")
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

# Initialize JWT manager
jwt = JWTManager(app)

# Create SQLAlchemy engine and session
engine = create_engine(os.getenv("SQLALCHEMY_DATABASE_URI"), echo=True)
Session = sessionmaker(bind=engine)
session = Session()

# Create database tables if they don't exist
Base.metadata.create_all(engine)

# Route to register a new user
@app.route('/auth/register', methods=['POST'])

def register():
    data = request.get_json()

    # Define the valid fields we expect in the JSON
    required_fields = {'user_name', 'email', 'password', 'role', 'first_name', 'last_name'}
    optional_fields = {'bio', 'profile_picture', 'additional_info' , 'invite_code'}
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

    # Check if the current user is an admin
    if data['role'].lower() == 'admin':
        if 'invite_code' not in data or data['invite_code'] != ADMIN_INVITE_CODE:
            return jsonify({"message": "Invalid or missing admin invite code!"}), 403

    # Hash the password using bcrypt
    hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())

    # Find the role by name (Admin, Instructor, Student)
    role = session.query(Role).filter_by(role_name=data['role']).first()
    if not role:
        return jsonify({"message": "Role does not exist!"}), 400

    # Start a transaction to ensure atomic operations
    try:
        # Create a new user
        new_user = User(
            user_name=data['user_name'],
            email=data['email'],
            password_hash=hashed_password.decode('utf-8'),
            role_id=role.id
        )

        # Add the new user to the session
        session.add(new_user)
        session.commit()  # This will generate new_user.id

        # Now create the profile and link it to the user
        new_profile = UserProfile(
            user_id=new_user.id,  # Link to the created user
            first_name=data['first_name'],
            last_name=data['last_name'],
            bio=data.get('bio', ''),  # Optional field, use default empty string
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


@jwt.token_in_blocklist_loader
def check_if_token_in_blocklist(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    user_name = jwt_payload['sub']['user_name']  # Extract user_name from the JWT payload

    # Check if the jti is in the Redis set for this user
    return redis_client.sismember(f"revoked_tokens:{user_name}", jti)


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
    access_token = create_access_token(identity={'user_name': user.user_name, 'role': user.role.role_name})
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
    role_names = [role.role_name for role in roles]

    # Query to find the full user role object (based on the name from JWT)
    user_role = session.query(Role).filter_by(role_name=user_role_name).first()

    # Construct the response
    response = {
        "message": f"You have access to the protected route with role: {user_role.role_name}",
        "roles_list": role_names,
        "user_role": {"id": user_role.id, "name": user_role.role_name}
    }
    # Return the response as JSON
    return jsonify(response)


@app.route('/auth/profile', methods=['GET'])
@jwt_required()
def profile():
    jwt_data = get_jwt()  # Get the JWT token payload
    user_name = jwt_data['sub']['user_name']  # Access the 'user_name' from the 'identity' (stored in 'sub')
    user_role = jwt_data['sub']['role']
    
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
            "user_role": user.role.role_name, 
            "email": user.email,
            "bio": user_profile.bio,
            "first_name": user_profile.first_name,
            "last_name": user_profile.last_name
        }
    }

    # Return the response as JSON
    return jsonify(response), 200


@app.route('/users', methods=['GET'])
@jwt_required()  # Ensure the user is authenticated
def get_users():
    # Check if the current user is an Admin
    current_user_role = get_jwt_identity()['role']
    if current_user_role != 'Admin':
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
            "user_role": user.role.role_name,
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
    role_check = session.query(Role).filter_by(role_name=data.get('role')).first()
    if not role_check:
        return jsonify({"message": "Role does not exist!"}), 400
    
    new_role = data.get('role') 
    if user:

        if user.user_name != user_name and current_user_role.lower() != 'admin':
            return jsonify({"message": "You do not have permission to change roles for other users"}), 403
        

        if user.user_name == user_name and new_role.lower() == "admin" and current_user_role.lower() != 'admin':
            if 'invite_code' not in data or data['invite_code'] != ADMIN_INVITE_CODE:
                return jsonify({"message": "You do not have permission to change your role to admin"}), 403
            
        user.role_id = session.query(Role).filter_by(role_name=new_role).first().id  # Assume the role is stored as a simple field in User table
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
    if user.id != user_profile.user_id and user_role != 'Admin':
        return jsonify({"message": "You do not have permission to change roles"}), 403
    if not user_profile:
        return jsonify({"message": "User profile not found"}), 404

    data = request.get_json()

    # Check 'first_name' if provided and ensure it's not empty
    if 'first_name' in data:
        if data['first_name'].strip() == "":
            return jsonify({"message": "First name cannot be empty"}), 400
        user_profile.first_name = data['first_name']

    # Check 'last_name' if provided and ensure it's not empty
    if 'last_name' in data:
        if data['last_name'].strip() == "":
            return jsonify({"message": "Last name cannot be empty"}), 400
        user_profile.last_name = data['last_name']

    # Update 'bio' if provided; allow it to be empty if needed
    if 'bio' in data:
        user_profile.bio = data['bio']

    session.commit()
    return jsonify({"message": "Profile updated successfully"}), 200



@app.route('/users/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_user(id):
    current_user_role = get_jwt_identity()['role']
    if current_user_role != 'Admin':
        return jsonify({"message": "You do not have permission to delete users"}), 403

    user = session.query(User).filter_by(id=id).first()
    if user:
        session.delete(user)
        session.commit()
        return jsonify({"message": "User deleted successfully"}), 200
    else:
        return jsonify({"message": "User not found"}), 404




# Start the Flask application
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

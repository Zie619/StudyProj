from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
import datetime
from dotenv import load_dotenv
import os

# Load the .env file
load_dotenv()


# Initialize Flask app
app = Flask(__name__)

# PostgreSQL database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY")  # Change this to a more secure key

# Initialize extensions
db = SQLAlchemy(app)
jwt = JWTManager(app)

# Define User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

# Create database tables
with app.app_context():
    db.create_all()

# User registration route
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    new_user = User(username=data['username'], password=data['password'])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User registered successfully!"}), 201

# User login route (JWT generation)
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()

    if not user or user.password != data['password']:
        return jsonify({"message": "Invalid credentials"}), 401

    access_token = create_access_token(identity={'username': user.username}, expires_delta=datetime.timedelta(days=1))
    return jsonify(access_token=access_token), 200

# Protected route that requires a valid JWT to access
@app.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    return jsonify(message="You have access to the protected route!")

# Start Flask application
if __name__ == '__main__':
    app.run(debug=True)

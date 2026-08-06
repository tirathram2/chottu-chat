import os
import re
import uuid
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
    send_from_directory,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_socketio import (
    SocketIO,
    emit,
    join_room,
    leave_room,
    send,
)
import eventlet

# Patch threading for Flask-SocketIO
eventlet.monkey_patch()

# =========================
# Configuration
# =========================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['AVATAR_FOLDER'] = 'static/avatars'
app.config['STATUS_FOLDER'] = 'static/status'
app.config['VOICE_FOLDER'] = 'static/voice'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Allowed extensions for uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav', 'ogg', 'mp4', 'mov', 'avi'}

# =========================
# Initialize extensions
# =========================
db = SQLAlchemy(app)
login_manager = LoginManager(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# =========================
# Database Models
# =========================

# Users Table
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    avatar = db.Column(db.String(256), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# Messages Table
class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Null for global
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), nullable=False, default='text')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Friends Table
class Friend(db.Model):
    __tablename__ = 'friends'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    friend_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

# Groups Table
class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

# Group Members
class GroupMember(db.Model):
    __tablename__ = 'group_members'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

# Status Table
class Status(db.Model):
    __tablename__ = 'status'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status_text = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Notifications Table
class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Reactions Table
class Reaction(db.Model):
    __tablename__ = 'reactions'
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reaction_type = db.Column(db.String(50), nullable=False)

# =========================
# User Loader
# =========================
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# =========================
# Helper Functions
# =========================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_email(email):
    email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(email_regex, email) is not None

def get_user_by_username_or_email(username_or_email):
    return User.query.filter(
        (User.username == username_or_email) | (User.email == username_or_email)
    ).first()

# =========================
# Create database tables
# =========================
with app.app_context():
    db.create_all()

# =========================
# Routes
# =========================

# Home Page
@app.route('/')
@login_required
def index():
    return render_template('index.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('username')
        password = request.form.get('password')
        user = get_user_by_username_or_email(username_or_email)
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

# Signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validate form
        errors = []

        if not username or not email or not password or not confirm_password:
            errors.append('Please fill out all fields.')

        if not validate_email(email):
            errors.append('Invalid email address.')

        if User.query.filter_by(username=username).first():
            errors.append('Username already exists.')

        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')

        if password != confirm_password:
            errors.append('Passwords do not match.')

        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('signup'))

        # Create user
        new_user = User(
            username=username,
            email=email,
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created. Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Chat Page
@app.route('/chat')
@login_required
def chat():
    return render_template('index.html')  # Assuming index.html is the chat interface

# Profile Page
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Update profile info
        username = request.form.get('username')
        email = request.form.get('email')
        status_text = request.form.get('status')
        avatar_file = request.files.get('avatar')

        errors = []

        if not username or not email:
            errors.append('Username and email are required.')

        if not validate_email(email):
            errors.append('Invalid email address.')

        # Check for duplicate username
        user_with_username = User.query.filter_by(username=username).first()
        if user_with_username and user_with_username.id != current_user.id:
            errors.append('Username already taken.')

        # Check for duplicate email
        user_with_email = User.query.filter_by(email=email).first()
        if user_with_email and user_with_email.id != current_user.id:
            errors.append('Email already registered.')

        if avatar_file:
            if not allowed_file(avatar_file.filename):
                errors.append('Invalid avatar file type.')
            else:
                filename = secure_filename(avatar_file.filename)
                ext = filename.rsplit('.', 1)[1].lower()
                filename = f"{current_user.id}_{uuid.uuid4().hex}.{ext}"
                avatar_path = os.path.join(app.config['AVATAR_FOLDER'], filename)
                avatar_file.save(avatar_path)
                current_user.avatar = avatar_path

        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('profile'))

        # Update user info
        current_user.username = username
        current_user.email = email
        if status_text:
            # Save status
            new_status = Status(user_id=current_user.id, status_text=status_text)
            db.session.add(new_status)
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', user=current_user)

# API: Get current user info
@app.route('/api/me')
@login_required
def api_me():
    user_data = {
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'avatar': current_user.avatar,
        'status': current_user.status,
        'last_seen': current_user.last_seen.isoformat() if current_user.last_seen else None,
    }
    return jsonify(user_data)

# API: Get global messages
@app.route('/api/messages/global')
@login_required
def api_messages_global():
    messages = Message.query.filter_by(receiver_id=None).order_by(Message.timestamp.asc()).limit(50).all()
    messages_list = []
    for msg in messages:
        sender = User.query.get(msg.sender_id)
        messages_list.append({
            'sender_id': sender.id,
            'sender_name': sender.username,
            'content': msg.content,
            'message_type': msg.message_type,
            'timestamp': msg.timestamp.isoformat(),
        })
    return jsonify(messages_list)

# =========================
# Socket.IO Events
# =========================

# Keep track of online users
online_users = {}

@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        user_id = current_user.id
        online_users[user_id] = request.sid
        # Broadcast online status
        emit('user_online', {'user_id': user_id, 'username': current_user.username}, broadcast=True)
        # Update last seen
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        user_id = current_user.id
        online_users.pop(user_id, None)
        # Broadcast offline status
        emit('user_offline', {'user_id': user_id, 'username': current_user.username}, broadcast=True)

@socketio.on('send_message')
def handle_send_message(data):
    # data: { 'receiver_id': int or None, 'content': str, 'message_type': str }
    if not current_user.is_authenticated:
        return
    receiver_id = data.get('receiver_id')
    content = data.get('content', '').strip()
    message_type = data.get('message_type', 'text')

    if not content:
        return

    # Save message
    msg = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        content=content,
        message_type=message_type,
        timestamp=datetime.utcnow(),
    )
    db.session.add(msg)
    db.session.commit()

    message_data = {
        'sender_id': current_user.id,
        'sender_name': current_user.username,
        'content': content,
        'message_type': message_type,
        'timestamp': msg.timestamp.isoformat(),
    }

    # Send to receiver or broadcast
    if receiver_id:
        # Private message
        receiver_sid = online_users.get(receiver_id)
        if receiver_sid:
            emit('new_message', message_data, room=receiver_sid)
        # Also emit back to sender
        emit('new_message', message_data, room=request.sid)
    else:
        # Global message
        emit('new_message', message_data, broadcast=True)

@socketio.on('typing')
def handle_typing(data):
    # data: { 'receiver_id': int or None }
    if not current_user.is_authenticated:
        return
    receiver_id = data.get('receiver_id')
    emit('typing', {'user_id': current_user.id, 'username': current_user.username}, broadcast=True, include_self=False)

# =========================
# File Upload API
# =========================
@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    file = request.files.get('file')
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file'}), 400
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower()
    filename = f"{current_user.id}_{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(save_path)
    return jsonify({'filename': filename, 'url': url_for('static', filename=f'uploads/{filename}')})

# =========================
# API: List Users
# =========================
@app.route('/api/users')
@login_required
def api_users():
    users = User.query.filter(User.id != current_user.id).all()
    users_list = []
    for user in users:
        users_list.append({
            'id': user.id,
            'username': user.username,
            'avatar': user.avatar,
            'status': user.status,
        })
    return jsonify(users_list)

# =========================
# API: Search Users
# =========================
@app.route('/api/search')
@login_required
def api_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    users = User.query.filter(User.username.ilike(f'%{query}%'), User.id != current_user.id).all()
    result = []
    for user in users:
        result.append({
            'id': user.id,
            'username': user.username,
            'avatar': user.avatar,
        })
    return jsonify(result)

# =========================
# Run the app
# =========================
if __name__ == '__main__':
    # For production, use Gunicorn or similar WSGI server
    socketio.run(app, host='0.0.0.0', port=5000)

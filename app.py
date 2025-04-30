from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
from dotenv import load_dotenv
from functools import wraps
import pytz
from sqlalchemy import event
import json

# Load environment variables
load_dotenv()

# Set timezone to IST
IST = pytz.timezone('Asia/Kolkata')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost:3306/event_management'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File Upload Configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads/events'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Create upload directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize SQLAlchemy
db = SQLAlchemy(app)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('You need to be an admin to access this page.', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper function to get current time in IST
def get_current_time():
    """Return current time in IST"""
    return datetime.now(IST)

# Helper function to convert naive datetime to IST
def make_timezone_aware(dt):
    """Convert naive datetime to timezone-aware datetime in IST"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return IST.localize(dt)
    return dt.astimezone(IST)

# Helper function to convert datetime string to timezone-aware datetime
def parse_datetime(date_str, format='%Y-%m-%dT%H:%M'):
    """Parse datetime string and return timezone-aware datetime in IST"""
    try:
        local_date = datetime.strptime(date_str, format)
        return IST.localize(local_date)
    except ValueError as e:
        raise ValueError(f"Invalid date format: {e}")

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='attendee')  # admin, organizer, or attendee
    events_organized = db.relationship('Event', backref='organizer', lazy=True)
    registrations = db.relationship('Registration', backref='attendee', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_organizer(self):
        return self.role == 'organizer'

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False, default=0.0)
    photo = db.Column(db.String(255))  # Store the photo filename
    organizer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    registrations = db.relationship('Registration', backref='event', lazy=True)

    @property
    def ist_date(self):
        """Return the event date in IST timezone"""
        return make_timezone_aware(self.date)

    def is_upcoming(self):
        """Check if the event is upcoming"""
        now = get_current_time()
        event_date = self.ist_date
        return event_date >= now if event_date and now else False

    def __init__(self, **kwargs):
        """Initialize event with timezone-aware date"""
        if 'date' in kwargs and kwargs['date']:
            kwargs['date'] = make_timezone_aware(kwargs['date'])
        super(Event, self).__init__(**kwargs)

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    registration_date = db.Column(db.DateTime, default=get_current_time)

    @property
    def ist_registration_date(self):
        """Return the registration date in IST timezone"""
        return make_timezone_aware(self.registration_date)

    def __init__(self, **kwargs):
        """Initialize registration with timezone-aware date"""
        if 'registration_date' not in kwargs:
            kwargs['registration_date'] = get_current_time()
        super(Registration, self).__init__(**kwargs)

# SQLAlchemy event listeners to ensure timezone awareness
@event.listens_for(Event, 'before_insert')
@event.listens_for(Event, 'before_update')
def ensure_event_date_timezone(mapper, connection, target):
    """Ensure event date is stored in UTC"""
    if target.date:
        aware_date = make_timezone_aware(target.date)
        target.date = aware_date.astimezone(pytz.UTC).replace(tzinfo=None)

@event.listens_for(Registration, 'before_insert')
@event.listens_for(Registration, 'before_update')
def ensure_registration_date_timezone(mapper, connection, target):
    """Ensure registration date is stored in UTC"""
    if target.registration_date:
        aware_date = make_timezone_aware(target.registration_date)
        target.registration_date = aware_date.astimezone(pytz.UTC).replace(tzinfo=None)

@event.listens_for(Event, 'load')
def receive_event_load(target, context):
    """Ensure loaded dates are timezone-aware"""
    if target.date and target.date.tzinfo is None:
        target.date = pytz.UTC.localize(target.date)

@event.listens_for(Registration, 'load')
def receive_registration_load(target, context):
    """Ensure loaded dates are timezone-aware"""
    if target.registration_date and target.registration_date.tzinfo is None:
        target.registration_date = pytz.UTC.localize(target.registration_date)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.is_admin():
            return redirect(url_for('admin_dashboard'))
        elif current_user.is_organizer():
            return redirect(url_for('organizer_dashboard'))
        else:
            return redirect(url_for('attendee_dashboard'))
    
    events = Event.query.filter(
        Event.is_active == True
    ).order_by(Event.date).all()
    
    # Filter upcoming events in Python after ensuring timezone awareness
    upcoming_events = [event for event in events if event.is_upcoming()]
    return render_template('index.html', events=upcoming_events)

@app.route('/events')
def events():
    """Display all events"""
    events = Event.query.filter(
        Event.is_active == True
    ).order_by(Event.date).all()
    upcoming_events = [event for event in events if event.is_upcoming()]
    past_events = [event for event in events if not event.is_upcoming()]
    return render_template('events.html', upcoming_events=upcoming_events, past_events=past_events)

@app.route('/profile')
@login_required
def profile():
    """User profile page"""
    return render_template('profile.html', user=current_user)

@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        
        # Check if username is taken by another user
        if username != current_user.username:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('Username already exists', 'danger')
                return redirect(url_for('edit_profile'))
        
        # Check if email is taken by another user
        if email != current_user.email:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('Email already exists', 'danger')
                return redirect(url_for('edit_profile'))
        
        current_user.username = username
        current_user.email = email
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html', user=current_user)

@app.route('/profile/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(current_password):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            flash('New passwords do not match', 'danger')
            return redirect(url_for('change_password'))
        
        current_user.set_password(new_password)
        db.session.commit()
        flash('Password changed successfully', 'success')
        return redirect(url_for('profile'))
    
    return render_template('change_password.html')

@app.route('/organizer/dashboard')
@login_required
def organizer_dashboard():
    now = get_current_time()
    organized_events = Event.query.filter_by(organizer_id=current_user.id).all()
    active_events = [event for event in organized_events if event.is_upcoming()]
    total_registrations = sum(len(event.registrations) for event in organized_events)
    # Chart data: Registrations per event (for this organizer)
    org_event_titles = [event.title for event in organized_events]
    org_registrations_count = [len(event.registrations) for event in organized_events]
    return render_template('organizer_dashboard.html',
                         organized_events=organized_events,
                         active_events=active_events,
                         total_registrations=total_registrations,
                         now=now,
                         org_event_titles=json.dumps(org_event_titles),
                         org_registrations_count=json.dumps(org_registrations_count))

@app.route('/attendee/dashboard')
@login_required
def attendee_dashboard():
    now = get_current_time()
    
    # Get events user is registered for
    registered_events = Event.query.join(Registration).filter(Registration.user_id == current_user.id).all()
    
    # Split into upcoming and past events
    upcoming_events = [event for event in registered_events if event.is_upcoming()]
    past_events = [event for event in registered_events if not event.is_upcoming()]
    
    # Get available events (future events user hasn't registered for)
    all_events = Event.query.filter(
        Event.organizer_id != current_user.id,
        Event.is_active == True
    ).all()
    
    registered_event_ids = {event.id for event in registered_events}
    available_events = [
        event for event in all_events 
        if event.id not in registered_event_ids and event.is_upcoming()
    ]
    
    return render_template('attendee_dashboard.html',
                         registered_events=registered_events,
                         upcoming_events=upcoming_events,
                         past_events=past_events,
                         available_events=available_events)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'attendee')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email, role=role)
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        date_str = request.form.get('date')
        location = request.form.get('location')
        capacity = request.form.get('capacity')
        price = request.form.get('price', 0.0)

        # Handle photo upload
        photo_filename = None
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo and allowed_file(photo.filename):
                filename = secure_filename(photo.filename)
                # Add timestamp to filename to make it unique
                photo_filename = f"{datetime.now(IST).strftime('%Y%m%d_%H%M%S')}_{filename}"
                photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))

        try:
            # Parse and localize the date
            ist_date = parse_datetime(date_str)
            
            event = Event(
                title=title,
                description=description,
                date=ist_date,
                location=location,
                capacity=int(capacity),
                price=float(price),
                photo=photo_filename,
                organizer_id=current_user.id
            )
            
            db.session.add(event)
            db.session.commit()
            flash('Event created successfully', 'success')
            return redirect(url_for('index'))
        except ValueError as e:
            flash(f'Error creating event: {str(e)}', 'danger')
            return redirect(url_for('create_event'))

    return render_template('create_event.html')

@app.route('/event/<int:event_id>')
def event_details(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('event_details.html', event=event)

@app.route('/register_event/<int:event_id>', methods=['POST'])
@login_required
def register_event(event_id):
    event = Event.query.get_or_404(event_id)
    if len(event.registrations) >= event.capacity:
        flash('Event is full')
        return redirect(url_for('event_details', event_id=event_id))

    if Registration.query.filter_by(user_id=current_user.id, event_id=event_id).first():
        flash('You are already registered for this event')
        return redirect(url_for('event_details', event_id=event_id))

    registration = Registration(user_id=current_user.id, event_id=event_id)
    db.session.add(registration)
    db.session.commit()
    flash('Successfully registered for the event')
    return redirect(url_for('event_details', event_id=event_id))

@app.route('/my_events')
@login_required
def my_events():
    now = get_current_time()
    organized_events = Event.query.filter_by(organizer_id=current_user.id).all()
    registered_events = Event.query.join(Registration).filter(Registration.user_id == current_user.id).all()
    return render_template('my_events.html', 
                         organized_events=organized_events, 
                         registered_events=registered_events, 
                         now=now)

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    now = get_current_time()
    users = User.query.all()
    events = Event.query.all()
    organizers = User.query.filter_by(role='organizer').all()
    total_users = len(users)
    total_events = len(events)
    active_events = len([e for e in events if e.is_upcoming()])
    total_registrations = Registration.query.count()
    # Chart data: Registrations per event
    event_titles = [event.title for event in events]
    registrations_count = [len(event.registrations) for event in events]
    # Chart data: User roles
    role_labels = ['Admin', 'Organizer', 'Attendee']
    role_counts = [
        len([u for u in users if u.role == 'admin']),
        len([u for u in users if u.role == 'organizer']),
        len([u for u in users if u.role == 'attendee'])
    ]
    return render_template('admin_dashboard.html',
                         users=users,
                         events=events,
                         organizers=organizers,
                         total_users=total_users,
                         total_events=total_events,
                         active_events=active_events,
                         total_registrations=total_registrations,
                         now=now,
                         event_titles=json.dumps(event_titles),
                         registrations_count=json.dumps(registrations_count),
                         role_labels=json.dumps(role_labels),
                         role_counts=json.dumps(role_counts))

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.role = request.form.get('role')
        
        if request.form.get('password'):
            user.set_password(request.form.get('password'))
        
        db.session.commit()
        flash('User updated successfully', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin_edit_user.html', user=user)

@app.route('/admin/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return '', 204

@app.route('/admin/events/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        event.title = request.form.get('title')
        event.description = request.form.get('description')
        date_str = request.form.get('date')
        try:
            # Parse and localize the date
            ist_date = parse_datetime(date_str)
            event.date = ist_date
            event.location = request.form.get('venue')
            event.organizer_id = request.form.get('organizer_id')
            event.is_active = bool(request.form.get('is_active'))
            
            db.session.commit()
            flash('Event updated successfully', 'success')
            return redirect(url_for('admin_dashboard'))
        except ValueError as e:
            flash(f'Error updating event: {str(e)}', 'danger')
            return redirect(url_for('admin_edit_event', event_id=event_id))
    
    organizers = User.query.filter_by(role='organizer').all()
    return render_template('admin_edit_event.html', event=event, organizers=organizers)

@app.route('/admin/events/<int:event_id>', methods=['DELETE'])
@login_required
@admin_required
def admin_delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    return '', 204

@app.route('/admin/add_event', methods=['POST'])
@login_required
@admin_required
def admin_add_event():
    title = request.form.get('title')
    description = request.form.get('description')
    date_str = request.form.get('date')
    try:
        # Parse and localize the date
        ist_date = parse_datetime(date_str)
        location = request.form.get('venue')
        organizer_id = request.form.get('organizer_id')
        is_active = bool(request.form.get('is_active'))
        
        event = Event(
            title=title,
            description=description,
            date=ist_date,
            location=location,
            organizer_id=organizer_id,
            is_active=is_active,
            capacity=100  # Default capacity
        )
        
        db.session.add(event)
        db.session.commit()
        flash('Event added successfully', 'success')
    except ValueError as e:
        flash(f'Error adding event: {str(e)}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/event/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    event = Event.query.get_or_404(event_id)
    
    # Check if user is the organizer
    if event.organizer_id != current_user.id and not current_user.is_admin():
        flash('You do not have permission to edit this event.', 'danger')
        return redirect(url_for('event_details', event_id=event_id))
    
    if request.method == 'POST':
        event.title = request.form.get('title')
        event.description = request.form.get('description')
        date_str = request.form.get('date')
        try:
            # Parse and localize the date
            ist_date = parse_datetime(date_str)
            event.date = ist_date
            event.location = request.form.get('location')
            event.capacity = int(request.form.get('capacity'))
            event.price = float(request.form.get('price', 0.0))
            
            # Handle photo upload if provided
            if 'photo' in request.files:
                photo = request.files['photo']
                if photo and allowed_file(photo.filename):
                    # Delete old photo if exists
                    if event.photo:
                        old_photo_path = os.path.join(app.config['UPLOAD_FOLDER'], event.photo)
                        if os.path.exists(old_photo_path):
                            os.remove(old_photo_path)
                    
                    filename = secure_filename(photo.filename)
                    photo_filename = f"{datetime.now(IST).strftime('%Y%m%d_%H%M%S')}_{filename}"
                    photo.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_filename))
                    event.photo = photo_filename
            
            db.session.commit()
            flash('Event updated successfully', 'success')
            return redirect(url_for('event_details', event_id=event_id))
        except ValueError as e:
            flash(f'Error updating event: {str(e)}', 'danger')
            return redirect(url_for('edit_event', event_id=event_id))
    
    return render_template('edit_event.html', event=event)

@app.route('/admin/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_user():
    """Add a new user from admin dashboard"""
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role', 'attendee')
        
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('admin_add_user'))
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('admin_add_user'))
        
        try:
            user = User(username=username, email=email, role=role)
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            flash('User added successfully', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding user: {str(e)}', 'danger')
            return redirect(url_for('admin_add_user'))
    
    return render_template('admin_add_user.html')

@app.template_filter('to_ist')
def to_ist(utc_dt):
    if utc_dt is None:
        return ""
    if utc_dt.tzinfo is None:
        utc_dt = pytz.UTC.localize(utc_dt)
    return utc_dt.astimezone(IST)

@app.template_filter('strftime')
def _jinja2_filter_datetime(date, fmt=None):
    if fmt is None:
        fmt = '%Y-%m-%d %H:%M:%S'
    return date.strftime(fmt)

if __name__ == '__main__':
    with app.app_context():
        print("Checking database tables...")
        try:
            # Create tables only if they don't exist
            db.create_all()
            print("Database tables ready")
        except Exception as e:
            print(f"Error setting up database: {e}")
    app.run(debug=True, port=5005) 
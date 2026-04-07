import os
from flask import Flask, render_template, request, redirect, url_for, flash, current_app
import re

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from dotenv import load_dotenv

from extensions import db, login_manager, mail, oauth

from models import User, Item

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret')

# Handle Render's postgres:// vs postgresql://
db_uri = os.getenv('DATABASE_URL', 'sqlite:///database.db')
if db_uri.startswith('postgres://'):
    db_uri = db_uri.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# Mail configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = 'login'
mail.init_app(app)
oauth.init_app(app)

# Google OAuth setup
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url=os.getenv('GOOGLE_DISCOVERY_URL'),
    client_kwargs={
        'scope': 'openid email profile'
    }
)


with app.app_context():
    db.create_all()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def check_for_match(new_item):
    # Find active items of the opposite type
    opposite_type = 'found' if new_item.type == 'lost' else 'lost'
    # Use ilike for case-insensitive matching and allow for similar locations
    matches = Item.query.filter_by(type=opposite_type, status='open').all()
    
    match_found = False
    for match in matches:
        # Match if category is same AND location is same (case insensitive)
        if match.category == new_item.category and match.location.lower() == new_item.location.lower():
            match_found = True
            # Update status and link both items
            match.status = 'matched'
            new_item.status = 'matched'
            match.matched_with_id = new_item.id
            new_item.matched_with_id = match.id
            db.session.commit()


            try:
                # Notify the owner of the other item
                other_user = User.query.get(match.user_id)
                if app.config.get('MAIL_USERNAME') and 'your_email' not in app.config.get('MAIL_USERNAME'):
                    msg = Message(
                        f"Potential Match for your {match.type} item: {match.title}",
                        recipients=[other_user.email, current_user.email]
                    )
                    msg.body = f'''Hello,

A potential match has been found!
Item 1 ({match.type}): {match.title}
Item 2 ({new_item.type}): {new_item.title}

Please log in to the portal to view details and coordinate.
'''
                    mail.send(msg)
                    flash(f'A match was found for "{new_item.title}"! Notifications sent via email.')
                else:
                    flash(f'A match was found for "{new_item.title}"! (Email settings not configured yet)')
            except Exception as e:
                print(f"Failed to send email: {e}")
                flash(f'A match was found for "{new_item.title}", but email notification failed.')
    return match_found


@app.route('/')
def index():
    recent_lost = Item.query.filter_by(type='lost', status='open').order_by(Item.created_at.desc()).limit(4).all()
    recent_found = Item.query.filter_by(type='found', status='open').order_by(Item.created_at.desc()).limit(4).all()
    return render_template('index.html', recent_lost=recent_lost, recent_found=recent_found)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Enforce @kpriet.ac.in email format
        email_pattern = r'^[a-zA-Z0-9.]+@kpriet\.ac\.in$'
        if not re.match(email_pattern, email):
            flash('Please use your official college email (e.g. 21cs001@kpriet.ac.in)')
            return redirect(url_for('register'))
            
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email address already exists')
            return redirect(url_for('register'))
            
        new_user = User(name=name, email=email, password_hash=generate_password_hash(password, method='pbkdf2:sha256'))
        db.session.add(new_user)
        db.session.commit()
        
        login_user(new_user)
        return redirect(url_for('dashboard'))

    return render_template('auth.html', is_login=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash('Please check your login details and try again.')
            return redirect(url_for('login'))
            
        login_user(user)
        return redirect(url_for('dashboard'))

    return render_template('auth.html', is_login=True)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/login/google')
def google_login():
    redirect_uri = url_for('google_authorize', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def google_authorize():
    token = oauth.google.authorize_access_token()
    user_info = token.get('userinfo')
    
    if not user_info:
        flash('Failed to fetch user info from Google.')
        return redirect(url_for('login'))
        
    email = user_info.get('email')
    
    # Enforce @kpriet.ac.in domain
    if not email.endswith('@kpriet.ac.in'):
        flash('Access restricted to @kpriet.ac.in accounts only.')
        return redirect(url_for('login'))
        
    # Check if user exists
    user = User.query.filter_by(email=email).first()
    
    if not user:
        # Create new user for first-time Google login
        user = User(
            name=user_info.get('name', email.split('@')[0]),
            email=email,
            google_id=user_info.get('sub')
        )
        db.session.add(user)
        db.session.commit()
    elif not user.google_id:
        # Link Google ID to existing account if not already linked
        user.google_id = user_info.get('sub')
        db.session.commit()
        
    login_user(user)
    flash(f'Successfully logged in as {user.name}')
    return redirect(url_for('dashboard'))


@app.route('/report/<item_type>', methods=['GET', 'POST'])
@login_required
def report_item(item_type):
    from datetime import datetime
    if item_type not in ['lost', 'found']:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        description = request.form.get('description')
        date_str = request.form.get('date')
        location = request.form.get('location')
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            date_obj = datetime.utcnow().date()
            
        filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                
                # Append timestamp to prevent collisions
                import time
                filename = f"{int(time.time())}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                
        new_item = Item(
            title=title, category=category, description=description,
            date=date_obj, location=location, image_filename=filename,
            type=item_type, user_id=current_user.id
        )
        db.session.add(new_item)
        db.session.commit()
        
        check_for_match(new_item)
        
        flash('Item reported successfully!')
        return redirect(url_for('items', type=item_type))
        
    return render_template('report.html', item_type=item_type)

@app.route('/items')
def items():
    q_type = request.args.get('type')
    q_search = request.args.get('search', '')
    q_category = request.args.get('category')
    q_location = request.args.get('location')
    
    query = Item.query.filter_by(status='open')
    
    if q_type in ['lost', 'found']:
        query = query.filter_by(type=q_type)
        
    if q_search:
        query = query.filter(Item.title.ilike(f'%{q_search}%') | Item.description.ilike(f'%{q_search}%'))
        
    if q_category:
        query = query.filter_by(category=q_category)
        
    if q_location:
        query = query.filter_by(location=q_location)
        
    result_items = query.order_by(Item.created_at.desc()).all()
    
    return render_template('items.html', items=result_items, list_type=q_type)

@app.route('/item/<int:id>')
def item_detail(id):
    item = Item.query.get_or_404(id)
    return render_template('item_detail.html', item=item)

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('You do not have permission to view this page.')
        return redirect(url_for('index'))
    items = Item.query.all()
    return render_template('admin.html', items=items)

@app.route('/admin/delete/<int:id>')
@login_required
def delete_item(id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    item = Item.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    flash('Item deleted.')
    return redirect(url_for('admin'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_items = Item.query.filter_by(user_id=current_user.id).order_by(Item.created_at.desc()).all()
    stats = {
        'total': len(user_items),
        'lost': len([i for i in user_items if i.type == 'lost']),
        'found': len([i for i in user_items if i.type == 'found']),
        'resolved': len([i for i in user_items if i.status == 'resolved']),
        'matched': len([i for i in user_items if i.status == 'matched'])
    }

    return render_template('dashboard.html', items=user_items, stats=stats)

@app.route('/item/resolve/<int:id>')
@login_required
def resolve_item(id):
    item = Item.query.get_or_404(id)
    if item.user_id != current_user.id and not current_user.is_admin:
        flash('You do not have permission to modify this item.')
        return redirect(url_for('dashboard'))
    
    item.status = 'resolved'
    db.session.commit()
    flash(f'Item "{item.title}" marked as resolved!')
    return redirect(url_for('dashboard'))


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)

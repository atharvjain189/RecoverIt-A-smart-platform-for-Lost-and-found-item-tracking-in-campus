from flask import Flask,render_template,request,redirect,url_for,flash,session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from uuid import uuid4
from difflib import SequenceMatcher
import re
import os

app =  Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key-before-deployment')


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lostfound.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 2*1024*1024

db = SQLAlchemy(app)
ALLOWED_EXTENSIONS = {'png','jpg','jpeg','gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS


class User(db.Model):
    id = db.Column(db.Integer,primary_key = True)
    name = db.Column(db.String(100),nullable = False)
    email = db.Column(db.String(100), unique=True,nullable=False)
    password = db.Column(db.String(200),nullable=False)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime,default =datetime.utcnow)


class Item(db.Model):
    id = db.Column(db.Integer,primary_key=True)
    title = db.Column(db.String(100),nullable=False)
    category = db.Column(db.String(50),nullable=False)
    location = db.Column(db.String(100),nullable=False)
    description = db.Column(db.Text,nullable=False)
    item_type = db.Column(db.String(10),nullable=False)
    date = db.Column(db.String(20),nullable=False)
    image = db.Column(db.String(200))
    status = db.Column(db.String(30),default="Open")
    admin_note = db.Column(db.Text)
    user_id = db.Column(db.Integer,db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime,default=datetime.utcnow)
    user = db.relationship('User', backref='items')


class Claim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    claimant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    item = db.relationship('Item', backref='claims')
    claimant = db.relationship('User', backref='claims')



class MatchNotice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lost_item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    found_item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(30), default='Pending')
    owner_name = db.Column(db.String(100))
    owner_phone = db.Column(db.String(30))
    owner_address = db.Column(db.Text)
    owner_email = db.Column(db.String(120))
    owner_dob = db.Column(db.String(20))
    admin_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lost_item = db.relationship('Item', foreign_keys=[lost_item_id])
    found_item = db.relationship('Item', foreign_keys=[found_item_id])


def _text_similarity(first, second):
    """Return a 0..1 similarity score for two short text values."""
    first = re.sub(r"[^a-z0-9 ]", " ", (first or "").lower()).strip()
    second = re.sub(r"[^a-z0-9 ]", " ", (second or "").lower()).strip()
    if not first or not second:
        return 0.0
    sequence_score = SequenceMatcher(None, first, second).ratio()
    first_words, second_words = set(first.split()), set(second.split())
    overlap_score = len(first_words & second_words) / max(1, len(first_words | second_words))
    return max(sequence_score, overlap_score)


def similarity_score(first_item, second_item):
    """Weighted matching score (0-100) between opposite Lost/Found reports."""
    if first_item.item_type == second_item.item_type:
        return 0
    category_score = 1.0 if (first_item.category or '').strip().lower() == (second_item.category or '').strip().lower() else 0.0
    title_score = _text_similarity(first_item.title, second_item.title)
    location_score = _text_similarity(first_item.location, second_item.location)
    description_score = _text_similarity(first_item.description, second_item.description)
    # Category 25%, title 35%, location 20%, description 20%.
    score = (category_score * 25) + (title_score * 35) + (location_score * 20) + (description_score * 20)
    return round(score)


def find_matches(item, limit=5):
    candidates = Item.query.filter(Item.item_type != item.item_type, Item.status == 'Open', Item.id != item.id).all()
    scored = [(candidate, similarity_score(item, candidate)) for candidate in candidates]
    return sorted((pair for pair in scored if pair[1] > 0), key=lambda pair: pair[1], reverse=True)[:limit]


# routes

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/register',methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if not all([name, email, password, confirm]):
            flash('Please fill in all required fields.', 'danger')
            return redirect(url_for('register'))

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(url_for('register'))

        if password != confirm:
            flash('Passwords do not match. Please try again.', 'danger')
            return redirect(url_for('register'))

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("Email already registered!","danger")
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)
        new_user = User(name=name,email=email,password=hashed)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! Please login.","success")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login',methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password,password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash("Login successful!","success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password!","danger")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!","success")
    return redirect(url_for('home'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    # Users only see their own reports and public Lost reports; Found reports are admin-only.
    own_items = Item.query.filter_by(user_id=session['user_id']).all()
    public_lost = Item.query.filter_by(item_type='Lost', status='Open').order_by(Item.created_at.desc()).all()
    items = list({item.id: item for item in own_items + public_lost}.values())
    notices = MatchNotice.query.join(Item, MatchNotice.lost_item_id == Item.id).filter(
        Item.user_id == session['user_id'], MatchNotice.status.in_(['Pending', 'Approved', 'Follow-up required'])
    ).order_by(MatchNotice.created_at.desc()).all()
    return render_template('dashboard.html', items=items, user_name=session.get('user_name'),
                           potential_matches=[], notices=notices)


@app.route('/report-lost',methods=['GET','POST'])
def report_lost():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST' :
        title = request.form.get('title')
        category = request.form.get('category')
        location = request.form.get('location')
        date = request.form.get('date')
        description = request.form.get('description')


        image_file = request.files.get('image')
        filename = None

        if image_file and allowed_file(image_file.filename):
            safe_name = secure_filename(image_file.filename)
            filename = f'{uuid4().hex}_{safe_name}'
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        new_item = Item(
            title = title,
            category = category,
            location = location,
            date = date,
            description = description,
            item_type = "Lost",
            image = filename,
            user_id = session['user_id']
        )
        db.session.add(new_item)
        db.session.commit()

        flash("Lost item reported successfully! The admin will review possible matches.", "success")
        return redirect(url_for('dashboard'))
    return render_template('report-lost.html',user_name= session.get('user_name'))



@app.route('/report-found',methods = ['GET','POST'])
def report_found():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        location = request.form.get('location')
        date = request.form.get('date')
        description = request.form.get('description')

        image_file = request.files.get('image')
        filename = None

        if image_file and allowed_file(image_file.filename):
            safe_name = secure_filename(image_file.filename)
            filename = f'{uuid4().hex}_{safe_name}'
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))


        new_item = Item(
            title = title,
            category = category,
            location = location,
            date = date,
            description = description,
            item_type = "Found",
            image = filename,
            user_id = session['user_id']
        )

        db.session.add(new_item)
        db.session.commit()

        flash("Found item submitted. It is visible only to the admin for verification.", "success")
        return redirect(url_for('dashboard'))
    return render_template('report-found.html',user_name = session.get('user_name'))


@app.route('/search')
def search():
    keyword = request.args.get('keyword', '')
    category = request.args.get('category', '')
    query = Item.query.filter_by(status="Open", item_type="Lost")
    if keyword:
        query = query.filter((Item.title.ilike(f'%{keyword}%')) | (Item.description.ilike(f'%{keyword}%')))
    if category:
        query = query.filter_by(category=category)
    items = query.order_by(Item.created_at.desc()).all()
    return render_template('search.html', items=items, user_name=session.get('user_name'))


# ---------- ITEM DETAILS ----------
@app.route('/item/<int:item_id>')
def item_details(item_id):
    item = Item.query.get_or_404(item_id)
    if item.item_type == 'Found' and not session.get('is_admin'):
        if session.get('user_id') != item.user_id:
            flash('Found reports are private and can only be viewed by the admin.', 'danger')
            return redirect(url_for('dashboard') if session.get('user_id') else url_for('login'))
    return render_template('item-details.html', item=item, user_name=session.get('user_name'))


# ---------- CLAIM ----------
@app.route('/claim/<int:item_id>', methods=['GET', 'POST'])
def claim(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    item = Item.query.get_or_404(item_id)

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        contact = (request.form.get('contact') or '').strip()
        message = (request.form.get('message') or '').strip()
        if not name or not contact or not message:
            flash('Please complete all claim fields.', 'danger')
            return redirect(url_for('claim', item_id=item.id))
        if item.user_id == session['user_id']:
            flash('You cannot submit a claim on your own listing.', 'danger')
            return redirect(url_for('item_details', item_id=item.id))
        claim_request = Claim(item_id=item.id, claimant_id=session['user_id'], name=name, contact=contact, message=message)
        db.session.add(claim_request)
        db.session.commit()
        flash('Claim request sent successfully!', 'success')
        return redirect(url_for('item_details', item_id=item.id))

    return render_template('claim.html', item=item, user_name=session.get('user_name'))


# ---------- PROFILE ----------
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        phone = (request.form.get('phone') or '').strip()
        if not name or not email:
            flash('Name and email are required.', 'danger')
            return redirect(url_for('profile'))
        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if existing:
            flash('That email is already used by another account.', 'danger')
            return redirect(url_for('profile'))
        user.name, user.email, user.phone = name, email, phone
        db.session.commit()

        session['user_name'] = user.name
        flash("Profile updated successfully!", "success")
        return redirect(url_for('profile'))

    lost_count = Item.query.filter_by(user_id=user.id, item_type="Lost").count()
    found_count = Item.query.filter_by(user_id=user.id, item_type="Found").count()

    return render_template('profile.html', user=user, lost_count=lost_count, found_count=found_count)



# ---------- ADMIN PORTAL ----------
def admin_required():
    return bool(session.get('is_admin'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        if username == os.environ.get('ADMIN_USERNAME', 'admin') and password == os.environ.get('ADMIN_PASSWORD', 'password'):
            session.clear()
            session['is_admin'] = True
            session['user_name'] = 'Admin'
            return redirect(url_for('admin_dashboard'))
        flash('Invalid admin username or password.', 'danger')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/admin')
@app.route('/admin/dashboard')
def admin_dashboard():
    if not admin_required():
        return redirect(url_for('admin_login'))
    items = Item.query.order_by(Item.created_at.desc()).all()
    notices = MatchNotice.query.order_by(MatchNotice.created_at.desc()).all()
    matches = []
    lost_items = Item.query.filter_by(item_type='Lost').all()
    found_items = Item.query.filter_by(item_type='Found').all()
    for lost in lost_items:
        for found in found_items:
            if lost.status not in ('Handed Over', 'Closed') and found.status not in ('Handed Over', 'Closed'):
                score = similarity_score(lost, found)
                matches.append((lost, found, score))
    matches.sort(key=lambda row: row[2], reverse=True)
    return render_template('admin_dashboard.html', items=items, notices=notices, matches=matches)

@app.route('/admin/notify/<int:lost_id>/<int:found_id>', methods=['POST'])
def admin_notify(lost_id, found_id):
    if not admin_required():
        return redirect(url_for('admin_login'))
    lost = Item.query.get_or_404(lost_id)
    found = Item.query.get_or_404(found_id)
    if lost.item_type != 'Lost' or found.item_type != 'Found':
        flash('Only Lost-to-Found matches can be notified.', 'danger')
        return redirect(url_for('admin_dashboard'))
    notice = MatchNotice.query.filter_by(lost_item_id=lost.id, found_item_id=found.id).first()
    if not notice:
        notice = MatchNotice(lost_item_id=lost.id, found_item_id=found.id, score=similarity_score(lost, found))
        db.session.add(notice)
    else:
        notice.score = similarity_score(lost, found)
        notice.status = 'Pending'
    db.session.commit()
    flash('Match notification is now available in the Lost item owner dashboard.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/match/<int:notice_id>', methods=['GET', 'POST'])
def match_notice(notice_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    notice = MatchNotice.query.get_or_404(notice_id)
    if notice.lost_item.user_id != session['user_id'] and not session.get('is_admin'):
        flash('You are not allowed to view this match.', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'dismiss':
            notice.status = 'Dismissed'
            db.session.commit()
            flash('Match dismissed.', 'info')
            return redirect(url_for('dashboard'))
        if action == 'approve':
            required = ['owner_name', 'owner_phone', 'owner_address', 'owner_email']
            values = {key: (request.form.get(key) or '').strip() for key in required}
            if not all(values.values()):
                flash('Please fill in name, phone, address and email.', 'danger')
            else:
                notice.owner_name = values['owner_name']
                notice.owner_phone = values['owner_phone']
                notice.owner_address = values['owner_address']
                notice.owner_email = values['owner_email']
                notice.owner_dob = (request.form.get('owner_dob') or '').strip()
                notice.status = 'Approved'
                db.session.commit()
                flash('Details sent to admin for verification.', 'success')
                return redirect(url_for('dashboard'))
    return render_template('match_notice.html', notice=notice)

@app.route('/admin/match/<int:notice_id>/status', methods=['POST'])
def admin_match_status(notice_id):
    if not admin_required():
        return redirect(url_for('admin_login'))
    notice = MatchNotice.query.get_or_404(notice_id)
    status = request.form.get('status')
    if status in ('Follow-up required', 'Verified', 'Handed Over', 'Dismissed'):
        notice.status = status
        notice.admin_note = (request.form.get('admin_note') or '').strip()
        if status == 'Handed Over':
            notice.lost_item.status = 'Handed Over'
            notice.found_item.status = 'Handed Over'
        db.session.commit()
        flash('Match status updated.', 'success')
    return redirect(url_for('admin_dashboard'))

# ==================== RUN ====================

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
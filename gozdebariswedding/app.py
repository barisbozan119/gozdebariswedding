from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import pillow_heif
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secretkey123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)


class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300))
    description = db.Column(db.String(300))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    approved = db.Column(db.Boolean, default=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('gallery'))
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(username=username).first():
            return "Kullanıcı zaten mevcut!"
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect(url_for('gallery'))
        return "Hatalı kullanıcı adı veya şifre!"
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        file = request.files['photo']
        description = request.form['description']
        if file:
            filename = secure_filename(file.filename)

            # Timestamp ekle
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{timestamp}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            # HEIC dosyasını otomatik JPEG'e çevir
            if ext.lower() == ".heic":
                heif_file = pillow_heif.read_heif(file)
                image = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data)
                filename = f"{name}_{timestamp}.jpg"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image.save(filepath, format="JPEG")
            else:
                file.save(filepath)

            photo = Photo(filename=filename, description=description, user_id=current_user.id, approved=False)
            db.session.add(photo)
            db.session.commit()
            return redirect(url_for('gallery'))
    return render_template('upload.html')


@app.route('/gallery')
@login_required
def gallery():
    photos = Photo.query.filter_by(user_id=current_user.id, approved=True).all()
    return render_template('gallery.html', photos=photos)


@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        return "Erişim reddedildi!"
    all_photos = Photo.query.all()
    return render_template('admin.html', photos=all_photos)


@app.route('/approve/<int:photo_id>')
@login_required
def approve(photo_id):
    if not current_user.is_admin:
        return "Erişim reddedildi!"
    photo = Photo.query.get(photo_id)
    if photo:
        photo.approved = True
        db.session.commit()
    return redirect(url_for('admin'))


@app.route('/reject/<int:photo_id>')
@login_required
def reject(photo_id):
    if not current_user.is_admin:
        return "Erişim reddedildi!"
    photo = Photo.query.get(photo_id)
    if photo:
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], photo.filename))
        db.session.delete(photo)
        db.session.commit()
    return redirect(url_for('admin'))


with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', password=generate_password_hash('admin123'), is_admin=True)
        db.session.add(admin_user)
        db.session.commit()

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
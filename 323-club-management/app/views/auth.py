from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import db, login_manager
from app.models import User, Club
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')  # student 或 club_leader
        real_name = request.form.get('real_name')
        class_name = request.form.get('class_name')  # 针对学生
        club_name = request.form.get('club_name')    # 针对社长
        email = request.form.get('email')
        phone = request.form.get('phone')
        
        # 检查用户名是否已存在
        if User.query.filter_by(username=username).first():
            flash("用户名已存在")
            return redirect(url_for('auth.register'))
            
        # 检查社团名称是否已存在
        if role == 'club_leader' and club_name:
            if Club.query.filter_by(name=club_name).first() or User.query.filter_by(club_name=club_name, role='club_leader').first():
                flash("社团名称已存在")
                return redirect(url_for('auth.register'))
        
        # 创建新用户
        user = User(
            username=username,
            password=generate_password_hash(password),
            role=role,
            real_name=real_name,
            class_name=class_name if role == 'student' else None,
            club_name=club_name if role == 'club_leader' else None,
            is_approved=False if role == 'club_leader' else True,
            email=email,
            phone=phone
        )
        
        db.session.add(user)
        db.session.commit()
        
        if role == 'club_leader':
            flash("注册成功！社长账号需要管理员审核后才能发布活动，请等待审核。")
        else:
            flash("注册成功，请登录")
        return redirect(url_for('auth.login'))
        
    return render_template('register.html')

@auth_bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('main.index'))
        else:
            flash("用户名或密码错误")
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
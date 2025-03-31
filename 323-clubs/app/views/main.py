from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import current_user, login_required
from app import db
from app.models import Activity, Club, Comment, Registration, User
from datetime import datetime, timedelta
import calendar as cal_module
import pytz
from werkzeug.security import generate_password_hash, check_password_hash

main_bp = Blueprint('main', __name__)

def get_beijing_time():
    """获取北京时间"""
    beijing_tz = pytz.timezone('Asia/Shanghai')
    return datetime.now(beijing_tz)

def make_aware(dt):
    """将naive datetime转换为aware datetime"""
    beijing_tz = pytz.timezone('Asia/Shanghai')
    if dt.tzinfo is None:
        return beijing_tz.localize(dt)
    return dt

@main_bp.route('/')
def index():
    # 获取北京时间
    now = get_beijing_time()
    
    # 获取最新的已审核活动，并按时间分类
    all_activities = Activity.query.filter_by(approved=True).order_by(Activity.event_date.desc()).all()
    
    # 分类活动
    past_activities = []
    future_activities = []
    
    for activity in all_activities:
        # 确保event_date是时区感知的
        event_date = make_aware(activity.event_date)
        if event_date < now:
            past_activities.append(activity)
        else:
            future_activities.append(activity)
    
    # 限制显示数量
    past_activities = past_activities[:3]
    future_activities = future_activities[:3]
    
    # 获取所有社团
    clubs = Club.query.all()
    
    return render_template('index.html', 
                         past_activities=past_activities,
                         future_activities=future_activities,
                         clubs=clubs,
                         current_time=now)

@main_bp.route('/activity/<int:activity_id>')
def view_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    
    # 增加点击量
    activity.click_count += 1
    db.session.commit()
    
    # 获取评论
    comments = Comment.query.filter_by(activity_id=activity.id, approved=True).order_by(Comment.created_at.desc()).all()
    
    # 检查当前用户是否已报名
    is_enrolled = False
    if current_user.is_authenticated:
        registration = Registration.query.filter_by(
            student_id=current_user.id, 
            activity_id=activity.id
        ).first()
        is_enrolled = registration is not None
    
    return render_template('activity_detail.html', 
                           activity=activity, 
                           comments=comments, 
                           is_enrolled=is_enrolled)

@main_bp.route('/calendar')
def activity_calendar():
    # 获取北京时间
    now = get_beijing_time()
    
    # 获取当前年月
    year = request.args.get('year', type=int, default=now.year)
    month = request.args.get('month', type=int, default=now.month)
    
    # 验证年月
    if not (1 <= month <= 12):
        month = now.month
    
    # 获取当月第一天和最后一天
    first_day = datetime(year, month, 1, tzinfo=now.tzinfo)
    if month == 12:
        last_day = datetime(year + 1, 1, 1, tzinfo=now.tzinfo) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1, tzinfo=now.tzinfo) - timedelta(days=1)
    
    # 获取日历信息
    cal = cal_module.monthcalendar(year, month)
    month_name = datetime(year, month, 1).strftime("%Y年%m月")
    
    # 获取当月已审核的活动
    activities = Activity.query.filter(
        Activity.event_date >= first_day,
        Activity.event_date <= last_day + timedelta(days=1),
        Activity.approved == True
    ).order_by(Activity.event_date).all()
    
    # 按日期对活动进行分组，并标记是否为过去活动
    activity_by_day = {}
    for activity in activities:
        # 确保event_date是时区感知的
        event_date = make_aware(activity.event_date)
        day = event_date.day
        if day not in activity_by_day:
            activity_by_day[day] = []
        activity_by_day[day].append({
            'activity': activity,
            'is_past': event_date < now
        })
    
    # 准备上一月和下一月的链接
    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year = year - 1
        
    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year = year + 1
    
    return render_template('calendar.html',
                          cal=cal,
                          month_name=month_name,
                          activity_by_day=activity_by_day,
                          year=year,
                          month=month,
                          prev_year=prev_year,
                          prev_month=prev_month,
                          next_year=next_year,
                          next_month=next_month,
                          today=now)

@main_bp.route('/profile')
@login_required
def profile():
    # 获取北京时间
    now = get_beijing_time()
    
    # 获取用户已报名的活动
    enrolled_activities = Registration.query.filter_by(student_id=current_user.id).all()
    
    # 处理活动日期时间，确保是时区感知的
    for registration in enrolled_activities:
        registration.activity.event_date = make_aware(registration.activity.event_date)
    
    # 获取用户所属的社团
    user_clubs = []
    if current_user.is_club_leader:
        club = Club.query.filter_by(leader_id=current_user.id).first()
        if club:
            user_clubs.append({
                'club': club,
                'role': '社长'
            })
    elif current_user.is_club_teacher:
        clubs = Club.query.filter_by(teacher_id=current_user.id).all()
        for club in clubs:
            user_clubs.append({
                'club': club,
                'role': '指导老师'
            })
    
    return render_template('profile.html',
                         enrolled_activities=enrolled_activities,
                         user_clubs=user_clubs,
                         current_time=now)

@main_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        # 获取表单数据
        username = request.form.get('username')
        real_name = request.form.get('real_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # 验证用户名是否已被使用
        if username != current_user.username:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('用户名已被使用', 'danger')
                return redirect(url_for('main.edit_profile'))
        
        # 验证当前密码
        if new_password:
            if not current_password or not check_password_hash(current_user.password, current_password):
                flash('当前密码错误', 'danger')
                return redirect(url_for('main.edit_profile'))
            
            if new_password != confirm_password:
                flash('两次输入的密码不一致', 'danger')
                return redirect(url_for('main.edit_profile'))
            
            current_user.password = generate_password_hash(new_password)
        
        # 更新用户信息
        current_user.username = username
        current_user.real_name = real_name
        current_user.email = email
        current_user.phone = phone
        
        try:
            db.session.commit()
            flash('个人资料更新成功', 'success')
            return redirect(url_for('main.profile'))
        except Exception as e:
            db.session.rollback()
            flash('更新失败，请稍后重试', 'danger')
            return redirect(url_for('main.edit_profile'))
    
    return render_template('edit_profile.html') 
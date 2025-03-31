from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, make_response
from flask_login import current_user, login_required
from app import db
from app.models import Club, Activity, User, ClubMember, Registration
from datetime import datetime
from functools import wraps
import csv
from io import StringIO

club_bp = Blueprint('club', __name__, url_prefix='/club')

# 社长权限装饰器
def require_club_leader(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_club_leader or not current_user.is_approved:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@club_bp.route('/<int:club_id>')
def club_home(club_id):
    club = Club.query.get_or_404(club_id)
    activities = Activity.query.filter_by(club_id=club.id, approved=True).order_by(Activity.published_at.desc()).all()
    return render_template('club/club_home.html', club=club, activities=activities)

@club_bp.route('/my_club')
@login_required
@require_club_leader
def my_club():
    # 获取当前社长的社团
    club = Club.query.filter_by(leader_id=current_user.id).first()
    
    if not club:
        flash('您还没有管理的社团')
        return redirect(url_for('main.index'))
    
    activities = Activity.query.filter_by(club_id=club.id).order_by(Activity.published_at.desc()).all()
    return render_template('club/my_club.html', club=club, activities=activities)

@club_bp.route('/edit_club_profile', methods=['GET', 'POST'])
@login_required
@require_club_leader
def edit_club_profile():
    # 获取当前社长的社团
    club = Club.query.filter_by(leader_id=current_user.id).first()
    
    if not club:
        flash('您还没有管理的社团')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        club.description = request.form.get('description')
        club.type = request.form.get('type')
        club.president_contact = request.form.get('president_contact')
        
        db.session.commit()
        flash('社团信息更新成功')
        return redirect(url_for('club.my_club'))
    
    # 社团类型列表
    club_types = ['科技类', '公益类', '学术类', '活动类', '文化类', '体育类', '艺术类']
    
    return render_template('club/edit_profile.html', club=club, club_types=club_types)

@club_bp.route('/new_activity', methods=['GET', 'POST'])
@login_required
@require_club_leader
def new_activity():
    # 获取当前社长的社团
    club = Club.query.filter_by(leader_id=current_user.id).first()
    
    if not club:
        flash('您需要先创建或加入一个社团')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        event_date_str = request.form.get('event_date')
        location = request.form.get('location')
        max_participants = request.form.get('max_participants', type=int, default=0)
        
        if not all([title, description, event_date_str, location]):
            flash('所有必填字段都必须填写')
            return render_template('club/new_activity.html')
        
        try:
            event_date = datetime.strptime(event_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('日期格式无效')
            return render_template('club/new_activity.html')
        
        activity = Activity(
            title=title,
            description=description,
            event_date=event_date,
            location=location,
            max_participants=max_participants,
            club_id=club.id,
            publisher_id=current_user.id,
            creator_id=current_user.id
        )
        
        db.session.add(activity)
        db.session.commit()
        flash('活动创建成功，等待审核')
        return redirect(url_for('club.my_club'))
    
    return render_template('club/new_activity.html')

@club_bp.route('/edit_activity/<int:activity_id>', methods=['GET', 'POST'])
@login_required
@require_club_leader
def edit_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    club = Club.query.filter_by(leader_id=current_user.id).first()
    
    # 安全检查：确保是自己社团的活动
    if not club or activity.club_id != club.id:
        flash('您没有权限编辑此活动')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        activity.title = request.form.get('title')
        activity.description = request.form.get('description')
        event_date_str = request.form.get('event_date')
        activity.location = request.form.get('location')
        activity.max_participants = request.form.get('max_participants', type=int, default=0)
        
        if not all([activity.title, activity.description, event_date_str, activity.location]):
            flash('所有必填字段都必须填写')
            return render_template('club/edit_activity.html', activity=activity)
        
        try:
            activity.event_date = datetime.strptime(event_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('日期格式无效')
            return render_template('club/edit_activity.html', activity=activity)
        
        # 如果已审核的活动被修改，需要重新审核
        if activity.approved:
            activity.approved = False
            flash('活动已更新，但需要重新审核')
        else:
            flash('活动已更新，等待审核')
            
        db.session.commit()
        return redirect(url_for('club.my_club'))
    
    return render_template('club/edit_activity.html', activity=activity)

@club_bp.route('/delete_activity/<int:activity_id>', methods=['POST'])
@login_required
@require_club_leader
def delete_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    club = Club.query.filter_by(leader_id=current_user.id).first()
    
    # 安全检查：确保是自己社团的活动
    if not club or activity.club_id != club.id:
        flash('您没有权限删除此活动')
        return redirect(url_for('main.index'))
    
    # 删除活动
    db.session.delete(activity)
    db.session.commit()
    
    flash('活动已删除')
    return redirect(url_for('club.my_club'))

def get_leader_club(user_id):
    """获取指定用户ID的社长所管理的社团"""
    return Club.query.filter_by(leader_id=user_id).first()

def get_current_leader_club():
    """获取当前登录用户（社长）所管理的社团"""
    if not current_user.is_authenticated or not current_user.is_club_leader:
        return None
    return get_leader_club(current_user.id)

@club_bp.route('/activity/<int:activity_id>/participants')
@login_required
def view_participants(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    
    # 检查权限：只有活动所属社团的社长、指导老师、管理员和超级管理员可以查看
    is_allowed = (current_user.is_super_admin or 
                  current_user.is_admin or 
                  (current_user.is_club_leader and activity.club.leader_id == current_user.id) or
                  (current_user.is_club_teacher and activity.club.teacher_id == current_user.id))
                  
    if not is_allowed:
        flash('您没有权限查看该活动的参与者名单')
        return redirect(url_for('main.view_activity', activity_id=activity_id))
    
    # 获取所有报名该活动的记录
    registrations = Registration.query.filter_by(activity_id=activity_id).all()
    
    return render_template('activity_participants.html', 
                           activity=activity, 
                           registrations=registrations)

@club_bp.route('/registration/<int:registration_id>/mark/<status>', methods=['POST'])
@login_required
def mark_participant(registration_id, status):
    registration = Registration.query.get_or_404(registration_id)
    activity = Activity.query.get_or_404(registration.activity_id)
    
    # 检查权限
    is_allowed = (current_user.is_super_admin or 
                  current_user.is_admin or 
                  (current_user.is_club_leader and activity.club.leader_id == current_user.id) or
                  (current_user.is_club_teacher and activity.club.teacher_id == current_user.id))
                  
    if not is_allowed:
        flash('您没有权限修改参与者状态')
        return redirect(url_for('main.view_activity', activity_id=activity.id))
    
    # 更新状态
    if status in ['registered', 'attended', 'absent']:
        registration.status = status
        if status == 'attended':
            registration.checked_in_at = datetime.utcnow()
        db.session.commit()
        flash('参与者状态已更新')
    else:
        flash('无效的状态值')
    
    return redirect(url_for('club.view_participants', activity_id=activity.id))

@club_bp.route('/activity/<int:activity_id>/export')
@login_required
def export_participants(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    
    # 检查权限
    is_allowed = (current_user.is_super_admin or 
                  current_user.is_admin or 
                  (current_user.is_club_leader and activity.club.leader_id == current_user.id) or
                  (current_user.is_club_teacher and activity.club.teacher_id == current_user.id))
                  
    if not is_allowed:
        flash('您没有权限导出参与者名单')
        return redirect(url_for('main.view_activity', activity_id=activity.id))
    
    # 获取所有报名该活动的记录
    registrations = Registration.query.filter_by(activity_id=activity_id).all()
    
    # 创建CSV文件
    si = StringIO()
    csv_writer = csv.writer(si)
    
    # 写入CSV标题行
    csv_writer.writerow(['姓名', '班级', '联系方式', '状态', '报名时间', '签到时间'])
    
    # 写入参与者数据
    for reg in registrations:
        # 组装联系方式
        contact = reg.student.phone or reg.student.email or '未提供'
        
        # 准备状态
        status = '已报名'
        if reg.status == 'attended':
            status = '已参加'
        elif reg.status == 'absent':
            status = '未参加'
        
        # 准备签到时间
        checked_in_time = '未签到'
        if reg.checked_in_at:
            checked_in_time = reg.checked_in_at.strftime('%Y-%m-%d %H:%M')
        
        # 写入数据行
        csv_writer.writerow([
            reg.student.real_name,
            reg.student.class_name or '未记录',
            contact,
            status,
            reg.registered_at.strftime('%Y-%m-%d %H:%M'),
            checked_in_time
        ])
    
    # 生成文件名
    output = make_response(si.getvalue())
    filename = f"{activity.title}_参与者名单_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-Disposition"] = f"attachment; filename={filename}"
    output.headers["Content-type"] = "text/csv; charset=utf-8-sig"  # 包含BOM以支持中文Excel
    
    flash('名单导出成功')
    return output
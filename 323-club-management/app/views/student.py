from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required
from app import db
from app.models import Activity, Registration, Comment
from datetime import datetime

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/activity/<int:activity_id>')
def activity_detail(activity_id):
    # 重定向到主蓝图中的活动详情页面
    return redirect(url_for('main.view_activity', activity_id=activity_id))

@student_bp.route('/activity/<int:activity_id>/enroll', methods=['POST'])
@login_required
def enroll(activity_id):
    # 检查当前用户联系方式是否完整
    if not current_user.email or not current_user.phone:
        flash("请先补充您的联系方式")
        return redirect(url_for('main.view_activity', activity_id=activity_id))
    
    # 检查用户是否已经报名
    existing_reg = Registration.query.filter_by(
        student_id=current_user.id,
        activity_id=activity_id
    ).first()
    
    if existing_reg:
        flash("您已经报名过这个活动了")
        return redirect(url_for('main.view_activity', activity_id=activity_id))
    
    # 创建报名记录
    activity = Activity.query.get_or_404(activity_id)
    
    # 检查活动是否已批准
    if not activity.approved:
        flash("该活动尚未通过审核，无法报名")
        return redirect(url_for('main.view_activity', activity_id=activity_id))
    
    # 检查人数是否已满
    if activity.max_participants > 0 and activity.enroll_count >= activity.max_participants:
        flash("很抱歉，活动报名人数已满")
        return redirect(url_for('main.view_activity', activity_id=activity_id))
    
    registration = Registration(student_id=current_user.id, activity_id=activity_id)
    activity.enroll_count += 1
    db.session.add(registration)
    db.session.commit()
    flash("报名成功")
    return redirect(url_for('main.view_activity', activity_id=activity_id))

@student_bp.route('/activity/<int:activity_id>/comment', methods=['POST'])
@login_required
def add_comment(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    
    # 检查活动是否已批准
    if not activity.approved:
        flash("该活动尚未通过审核，无法评论")
        return redirect(url_for('main.view_activity', activity_id=activity_id))
    
    content = request.form.get('content', '').strip()
    
    if not content:
        flash("评论内容不能为空")
        return redirect(url_for('main.view_activity', activity_id=activity_id))
    
    comment = Comment(
        content=content,
        user_id=current_user.id,
        activity_id=activity_id,
        created_at=datetime.utcnow(),
        approved=False  # 默认需要审核
    )
    
    db.session.add(comment)
    db.session.commit()
    
    flash("评论已提交，等待审核")
    return redirect(url_for('main.view_activity', activity_id=activity_id))

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user, login_required
from app import db
from app.models import Post, Comment, Activity, Club, User, ClubMember, Registration
from app.models import ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_CLUB_LEADER, ROLE_CLUB_TEACHER, ROLE_UNION, ROLE_STUDENT
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# 装饰器：需要超级管理员权限
def require_super_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_super_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# 装饰器：需要管理员权限
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.can_manage_users:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# 装饰器：需要审核权限
def require_review_permission(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.can_review_activity:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/manage_users')
@login_required
@require_admin
def manage_users():
    # 获取筛选角色（如果有）
    role_filter = request.args.get('role')
    search_query = request.args.get('search', '').strip()
    
    # 如果是普通管理员，超级管理员不应该出现在列表中
    query = User.query
    if current_user.role != ROLE_SUPER_ADMIN:
        query = query.filter(User.role != ROLE_SUPER_ADMIN)
    
    # 应用角色筛选（如果有）
    if role_filter:
        query = query.filter(User.role == role_filter)
    
    # 应用搜索条件（如果有）
    if search_query:
        search_filter = (
            User.username.ilike(f'%{search_query}%') |
            User.real_name.ilike(f'%{search_query}%') |
            User.email.ilike(f'%{search_query}%') |
            User.phone.ilike(f'%{search_query}%')
        )
        query = query.filter(search_filter)
    
    users = query.all()
    
    # 获取所有社长，用于指导老师绑定
    club_leaders = User.query.filter_by(role=ROLE_CLUB_LEADER).all()
    
    # 标记是否显示角色变更表单
    show_role_form = (current_user.role == ROLE_SUPER_ADMIN or 
                     (current_user.role == ROLE_ADMIN and role_filter != ROLE_SUPER_ADMIN))
    
    return render_template('admin/manage_users.html', users=users, 
                          club_leaders=club_leaders, 
                          show_role_form=show_role_form)

@admin_bp.route('/update_user_role/<int:user_id>', methods=['POST'])
@login_required
@require_admin
def update_user_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    
    # 验证角色类型
    valid_roles = [ROLE_STUDENT, ROLE_CLUB_LEADER, ROLE_CLUB_TEACHER, ROLE_UNION]
    
    # 只有超级管理员可以设置或取消超级管理员权限
    if current_user.is_super_admin:
        valid_roles.append(ROLE_SUPER_ADMIN)
        valid_roles.append(ROLE_ADMIN)
    else:
        # 普通管理员不能修改其他管理员的角色
        if user.is_admin or user.is_super_admin:
            flash('您没有权限修改其他管理员的角色')
            return redirect(url_for('admin.manage_users'))
        
        # 普通管理员可以设置普通管理员权限，但不能设置超级管理员权限
        valid_roles.append(ROLE_ADMIN)
    
    if new_role not in valid_roles:
        flash('无效的角色类型')
        return redirect(url_for('admin.manage_users'))
    
    # 不能修改自己的角色（防止降低自己的权限导致无法操作）
    if user.id == current_user.id:
        flash('不能修改自己的角色')
        return redirect(url_for('admin.manage_users'))
    
    # 更新用户角色
    user.role = new_role
    
    # 如果是指导老师角色，需要处理与社长的关联
    if new_role == ROLE_CLUB_TEACHER:
        leader_id = request.form.get('leader_id')
        if leader_id:
            user.leader_id = leader_id
    else:
        # 如果不是指导老师，清除关联
        user.leader_id = None
    
    db.session.commit()
    flash(f'用户 {user.username} 的角色已更新为 {new_role}')
    
    # 如果有角色筛选，保持相同的筛选条件返回
    if 'role' in request.args:
        return redirect(url_for('admin.manage_users', role=request.args.get('role')))
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@require_admin
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # 安全检查：不允许删除自己
    if user.id == current_user.id:
        flash('不能删除当前登录的用户账号')
        return redirect(url_for('admin.manage_users'))
    
    # 安全检查：普通管理员不能删除超级管理员
    if current_user.role != ROLE_SUPER_ADMIN and user.role == ROLE_SUPER_ADMIN:
        flash('您没有权限删除超级管理员账号')
        return redirect(url_for('admin.manage_users'))
    
    username = user.username
    
    try:
        # 删除关联数据
        
        # 1. 删除用户创建的社团
        clubs = Club.query.filter_by(creator_id=user.id).all()
        for club in clubs:
            # 删除社团相关活动
            activities = Activity.query.filter_by(club_id=club.id).all()
            for activity in activities:
                # 删除活动相关评论
                Comment.query.filter_by(activity_id=activity.id).delete()
                db.session.delete(activity)
            
            # 删除社团成员关系
            ClubMember.query.filter_by(club_id=club.id).delete()
            
            db.session.delete(club)
        
        # 2. 删除用户发布的活动
        activities = Activity.query.filter_by(creator_id=user.id).all()
        for activity in activities:
            # 删除活动相关评论
            Comment.query.filter_by(activity_id=activity.id).delete()
            db.session.delete(activity)
        
        # 3. 删除用户的评论
        Comment.query.filter_by(user_id=user.id).delete()
        
        # 4. 删除用户
        db.session.delete(user)
        db.session.commit()
        
        flash(f'用户 {username} 已成功删除')
    except Exception as e:
        db.session.rollback()
        flash(f'删除用户失败: {str(e)}')
    
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/manage_clubs')
@login_required
@require_admin
def manage_clubs():
    clubs = Club.query.all()
    return render_template('admin/manage_clubs.html', clubs=clubs)

@admin_bp.route('/edit_club/<int:club_id>', methods=['GET', 'POST'])
@login_required
@require_super_admin
def edit_club(club_id):
    club = Club.query.get_or_404(club_id)
    
    if request.method == 'POST':
        club.name = request.form.get('name')
        club.description = request.form.get('description')
        club.type = request.form.get('type')
        club.president_contact = request.form.get('president_contact')
        
        # 更新社长和指导老师关联
        leader_id = request.form.get('leader_id', type=int)
        teacher_id = request.form.get('teacher_id', type=int)
        
        if leader_id:
            leader = User.query.get(leader_id)
            if leader and leader.role == ROLE_CLUB_LEADER:
                club.leader_id = leader_id
        
        if teacher_id:
            teacher = User.query.get(teacher_id)
            if teacher and teacher.role == ROLE_CLUB_TEACHER:
                club.teacher_id = teacher_id
        
        db.session.commit()
        flash(f'社团 {club.name} 信息已更新')
        return redirect(url_for('admin.manage_clubs'))
    
    # 获取所有社长和指导老师
    leaders = User.query.filter_by(role=ROLE_CLUB_LEADER).all()
    teachers = User.query.filter_by(role=ROLE_CLUB_TEACHER).all()
    
    # 社团类型列表
    club_types = ['科技类', '公益类', '学术类', '活动类', '文化类', '体育类', '艺术类']
    
    return render_template('admin/edit_club.html', 
                          club=club, 
                          leaders=leaders, 
                          teachers=teachers,
                          club_types=club_types)

@admin_bp.route('/create_club', methods=['POST'])
@login_required
@require_admin
def create_club():
    name = request.form.get('name')
    description = request.form.get('description')
    club_type = request.form.get('type', '科技类')  # 默认为科技类
    
    if not name or not description:
        flash('社团名称和描述不能为空')
        return redirect(url_for('admin.manage_clubs'))
    
    # 检查社团名称是否已存在
    if Club.query.filter_by(name=name).first():
        flash('社团名称已存在')
        return redirect(url_for('admin.manage_clubs'))
    
    # 创建新社团
    club = Club(
        name=name,
        description=description,
        creator_id=current_user.id,
        type=club_type
    )
    
    db.session.add(club)
    db.session.commit()
    
    flash(f'社团 {name} 创建成功')
    return redirect(url_for('admin.manage_clubs'))

@admin_bp.route('/delete_club/<int:club_id>', methods=['POST'])
@login_required
@require_admin
def delete_club(club_id):
    club = Club.query.get_or_404(club_id)
    
    # 获取社团名称用于显示
    club_name = club.name
    
    try:
        # 删除社团关联数据
        
        # 1. 删除社团活动及评论
        activities = Activity.query.filter_by(club_id=club.id).all()
        for activity in activities:
            Comment.query.filter_by(activity_id=activity.id).delete()
            db.session.delete(activity)
        
        # 2. 删除社团成员关系
        ClubMember.query.filter_by(club_id=club.id).delete()
        
        # 3. 删除社团
        db.session.delete(club)
        db.session.commit()
        
        flash(f'社团 {club_name} 已成功删除')
    except Exception as e:
        db.session.rollback()
        flash(f'删除社团失败: {str(e)}')
    
    return redirect(url_for('admin.manage_clubs'))

@admin_bp.route('/manage_activities')
@login_required
@require_admin
def manage_activities():
    activities = Activity.query.all()
    return render_template('admin/manage_activities.html', activities=activities)

@admin_bp.route('/delete_activity/<int:activity_id>', methods=['POST'])
@login_required
@require_admin
def delete_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    
    # 获取活动标题用于显示
    activity_title = activity.title
    
    try:
        # 删除活动评论
        Comment.query.filter_by(activity_id=activity.id).delete()
        
        # 删除活动注册记录
        Registration.query.filter_by(activity_id=activity.id).delete()
        
        # 删除活动
        db.session.delete(activity)
        db.session.commit()
        
        flash(f'活动 {activity_title} 已成功删除')
    except Exception as e:
        db.session.rollback()
        flash(f'删除活动失败: {str(e)}')
    
    return redirect(url_for('admin.manage_activities'))

@admin_bp.route('/review_posts')
@login_required
@require_review_permission
def review_posts():
    # 超级管理员和管理员可以看到所有活动
    if current_user.is_super_admin or current_user.is_admin:
        activities = Activity.query.filter_by(approved=False).all()
    
    # 社联成员可以看到所有未审核的活动
    elif current_user.is_union:
        activities = Activity.query.filter_by(approved=False).all()
    
    # 指导老师只能查看关联社长发布的活动
    elif current_user.is_club_teacher:
        leader = User.query.get(current_user.leader_id)
        if not leader:
            activities = []
        else:
            led_club = Club.query.filter_by(leader_id=leader.id).first()
            if led_club:
                activities = Activity.query.filter_by(club_id=led_club.id, approved=False).all()
            else:
                activities = []
    else:
        activities = []
    
    return render_template('admin/review_posts.html', activities=activities)

@admin_bp.route('/approve_activity/<int:activity_id>', methods=['POST'])
@login_required
@require_review_permission
def approve_activity(activity_id):
    activity = Activity.query.get_or_404(activity_id)
    
    # 检查权限
    if current_user.is_club_teacher:
        # 指导老师只能审核关联社长的活动
        if not current_user.leader_id:
            flash('您没有关联的社长，无法审核活动')
            return redirect(url_for('admin.review_posts'))
        
        leader = User.query.get(current_user.leader_id)
        led_club = Club.query.filter_by(leader_id=leader.id).first()
        
        if not led_club or activity.club_id != led_club.id:
            flash('您没有权限审核此活动')
            return redirect(url_for('admin.review_posts'))
    
    activity.approved = True
    db.session.commit()
    
    flash(f'活动 {activity.title} 已批准')
    return redirect(url_for('admin.review_posts'))

@admin_bp.route('/review_comments')
@login_required
@require_admin
def review_comments():
    comments = Comment.query.filter_by(approved=False).all()
    return render_template('admin/review_comments.html', comments=comments)

@admin_bp.route('/approve_comment/<int:comment_id>', methods=['POST'])
@login_required
@require_admin
def approve_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    comment.approved = True
    db.session.commit()
    
    flash('评论已批准')
    return redirect(url_for('admin.review_comments'))

@admin_bp.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
@require_admin
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    
    flash('评论已删除')
    return redirect(url_for('admin.review_comments'))

@admin_bp.route('/pending_leaders')
@login_required
@require_admin
def pending_leaders():
    # 获取所有待审核的社长申请
    pending_leaders = User.query.filter_by(role='club_leader', is_approved=False).all()
    return render_template('admin/pending_leaders.html', pending_leaders=pending_leaders)

@admin_bp.route('/approve_leader/<int:user_id>', methods=['POST'])
@login_required
@require_admin
def approve_leader(user_id):
    user = User.query.get_or_404(user_id)
    
    # 验证用户角色
    if user.role != ROLE_CLUB_LEADER:
        flash(f'只能审核社长申请')
        return redirect(url_for('admin.pending_leaders'))
    
    # 验证社团名称
    if not user.club_name:
        flash(f'用户未提供社团名称')
        return redirect(url_for('admin.pending_leaders'))
    
    # 检查社团名称是否已存在
    if Club.query.filter_by(name=user.club_name).first():
        flash(f'社团名称 {user.club_name} 已存在')
        return redirect(url_for('admin.pending_leaders'))
    
    # 批准社长申请
    user.is_approved = True
    
    # 创建新社团
    club = Club(
        name=user.club_name,
        description=f"{user.club_name}是由{user.real_name}创建的社团",
        leader_id=user.id,
        creator_id=current_user.id,
        type='科技类'  # 默认类型，社长可以在后续编辑
    )
    
    db.session.add(club)
    db.session.commit()
    
    flash(f'已批准 {user.real_name} 的社长申请，并创建社团 {user.club_name}')
    return redirect(url_for('admin.pending_leaders'))

@admin_bp.route('/reject_leader/<int:user_id>', methods=['POST'])
@login_required
@require_admin
def reject_leader(user_id):
    leader = User.query.get_or_404(user_id)
    
    # 确保是社长账号
    if leader.role != 'club_leader':
        flash('该用户不是社长账号')
        return redirect(url_for('admin.pending_leaders'))
    
    # 将角色改为学生
    leader.role = 'student'
    leader.club_name = None
    
    db.session.commit()
    
    flash(f'已拒绝 {leader.real_name} 的社长申请并将其角色改为学生')
    return redirect(url_for('admin.pending_leaders'))
from app import db
from flask_login import UserMixin
from datetime import datetime

# 用户角色常量
ROLE_SUPER_ADMIN = 'super_admin'  # 超级管理员
ROLE_ADMIN = 'admin'  # 普通管理员
ROLE_CLUB_LEADER = 'club_leader'  # 社长
ROLE_CLUB_TEACHER = 'club_teacher'  # 社团指导老师
ROLE_UNION = 'union'  # 社联
ROLE_STUDENT = 'student'  # 学生

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    password = db.Column(db.String(128))
    role = db.Column(db.String(20))  # super_admin, admin, club_leader, club_teacher, union, student
    real_name = db.Column(db.String(64))
    class_name = db.Column(db.String(64))  # 针对学生
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    # 指导老师关联的社长ID
    leader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # 社长申请状态
    is_approved = db.Column(db.Boolean, default=False)
    # 社长申请的社团名称
    club_name = db.Column(db.String(64), nullable=True)
    # 创建时间
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 反向引用：该社长关联的所有指导老师
    teachers = db.relationship('User', backref=db.backref('leader', remote_side=[id]), foreign_keys=[leader_id])

    def __repr__(self):
        return f"<User {self.username}>"
    
    @property
    def is_super_admin(self):
        return self.role == ROLE_SUPER_ADMIN
    
    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN
    
    @property
    def is_club_leader(self):
        return self.role == ROLE_CLUB_LEADER
    
    @property
    def is_club_teacher(self):
        return self.role == ROLE_CLUB_TEACHER
    
    @property
    def is_union(self):
        return self.role == ROLE_UNION
    
    @property
    def is_student(self):
        return self.role == ROLE_STUDENT
    
    @property
    def can_manage_users(self):
        return self.is_super_admin or self.is_admin
    
    @property
    def can_create_club(self):
        return self.is_super_admin or self.is_admin
    
    @property
    def can_delete_club(self):
        return self.is_super_admin or self.is_admin
    
    @property
    def can_publish_activity(self):
        return (self.is_super_admin or self.is_admin or 
                (self.is_club_leader and self.is_approved))
    
    @property
    def can_delete_activity(self):
        return self.is_super_admin or self.is_admin or (self.is_club_leader and self.is_approved)
    
    @property
    def can_review_activity(self):
        return self.is_super_admin or self.is_admin or self.is_union or self.is_club_teacher

class Club(db.Model):
    __tablename__ = "clubs"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    description = db.Column(db.Text)
    president_contact = db.Column(db.String(64))
    type = db.Column(db.String(64))   # 社团类型：科技类、公益类、学术类、活动类、文化类、体育类、艺术类
    score = db.Column(db.Float, default=0)   # 社团分数
    # 关联社长用户ID
    leader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # 关联社团指导老师ID
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # 创建者ID
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # 创建时间
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 一对多关系
    activities = db.relationship('Activity', backref='club', lazy='dynamic')
    # 一对一关系
    leader = db.relationship('User', foreign_keys=[leader_id], backref='led_club')
    teacher = db.relationship('User', foreign_keys=[teacher_id], backref='guided_club')
    creator = db.relationship('User', foreign_keys=[creator_id], backref='created_clubs')

    def __repr__(self):
        return f"<Club {self.name}>"

class Activity(db.Model):
    __tablename__ = "activities"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128))
    description = db.Column(db.Text)
    event_date = db.Column(db.DateTime)
    location = db.Column(db.String(128))
    published_at = db.Column(db.DateTime, default=datetime.utcnow)
    click_count = db.Column(db.Integer, default=0)
    enroll_count = db.Column(db.Integer, default=0)
    max_participants = db.Column(db.Integer, default=0)  # 0表示不限制人数
    feedback_score = db.Column(db.Float, default=0)  # 学生反馈综合评分
    approved = db.Column(db.Boolean, default=False)  # 活动帖审核状态
    
    # 关联发布者ID
    publisher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    # 关联社团ID
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'))
    # 创建者ID
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # 关系
    publisher = db.relationship('User', foreign_keys=[publisher_id], backref='published_activities')
    creator = db.relationship('User', foreign_keys=[creator_id], backref='created_activities')
    comments = db.relationship('Comment', backref='activity', lazy='dynamic')
    participants = db.relationship('Registration', backref='activity', lazy='dynamic')

    def __repr__(self):
        return f"<Activity {self.title}>"

class Registration(db.Model):
    __tablename__ = "registrations"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'))
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 添加参与状态
    status = db.Column(db.String(20), default='registered')  # registered, attended, absent
    # 添加签到时间
    checked_in_at = db.Column(db.DateTime, nullable=True)
    
    # 添加与用户的关系
    student = db.relationship('User', backref=db.backref('registrations', lazy='dynamic'))
    
    def __repr__(self):
        return f"<Registration {self.id}>"

class Post(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)     # 可同时支持 html 格式
    media_url = db.Column(db.String(256))  # 图片或视频存储地址
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved = db.Column(db.Boolean, default=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))

class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved = db.Column(db.Boolean, default=False)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    activity_id = db.Column(db.Integer, db.ForeignKey('activities.id'))
    
    # 添加与用户的关系
    user = db.relationship('User', backref=db.backref('comments', lazy='dynamic'))
    
    def __repr__(self):
        return f"<Comment {self.id}>"

class ClubMember(db.Model):
    __tablename__ = "club_members"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'))
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='memberships')
    club = db.relationship('Club', backref='members')

    def __repr__(self):
        return f"<ClubMember user_id={self.user_id} club_id={self.club_id}>"
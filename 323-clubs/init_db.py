from app import create_app, db
from app.models import User, Club, Activity
from app.models import ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_CLUB_LEADER, ROLE_CLUB_TEACHER, ROLE_UNION, ROLE_STUDENT
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # 创建所有表
    db.create_all()
    
    # 检查是否有管理员用户，如果没有则创建
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            password=generate_password_hash('password'),
            role=ROLE_ADMIN,
            real_name='管理员',
            email='admin@example.com'
        )
        db.session.add(admin)
    
    # 添加特定超级管理员账号terryduan
    terry = User.query.filter_by(username='terryduan').first()
    if terry:
        # 如果已存在，更新为超级管理员角色
        terry.role = ROLE_SUPER_ADMIN
    else:
        # 否则创建新的超级管理员账号
        terry = User(
            username='terryduan',
            password=generate_password_hash('dzy20090328'),
            role=ROLE_SUPER_ADMIN,
            real_name='Terry Duan',
            email='terryduan@example.com'
        )
        db.session.add(terry)
        
    # 创建测试社团
    test_club = Club.query.filter_by(name='测试社团').first()
    if not test_club:
        test_club = Club(
            name='测试社团',
            description='这是一个用于测试的社团',
            president_contact='12345678901',
            scale='小型社团'
        )
        db.session.add(test_club)
    
    # 提交更改
    db.session.commit()
    
    print("数据库初始化完成！") 
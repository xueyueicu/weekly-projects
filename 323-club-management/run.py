from app import create_app, db

app = create_app()

# 导入模型，确保迁移能识别所有模型
from app.models import User, Club, Activity, Registration, Comment, Post, ClubMember

@app.shell_context_processor
def make_shell_context():
    return dict(app=app, db=db, User=User, Club=Club, Activity=Activity, 
                Registration=Registration, Comment=Comment, Post=Post, ClubMember=ClubMember)

if __name__ == '__main__':
    app.run(debug=True)
import os
from flask import Flask

from .models import db
from . import config

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_CONNECTION_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ['FLASK_SECRET']
    db.init_app(app)
    
    with app.app_context():
        from . import routes
        db.create_all()
    
    return app
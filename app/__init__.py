import os
from flask import Flask
import os.path
import sys
sys.path.append(os.path.dirname(__file__))

from models import db
import config

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_CONNECTION_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ['FLASK_SECRET']
    app.app_context().push()
    db.init_app(app)
    db.create_all()
    return app
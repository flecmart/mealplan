from flask import Flask
import flask_sqlalchemy

from .models import db
from . import config

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_CONNECTION_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'super secret key' # TODO
    app.app_context().push()
    db.init_app(app)
    db.create_all()
    return app
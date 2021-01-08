<<<<<<< HEAD
import os
=======
>>>>>>> 0f3918eda4471fc2c9ce026d2cc8b3a1b5570329
from flask import Flask

from .models import db
from . import config

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_CONNECTION_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
<<<<<<< HEAD
    app.config['SECRET_KEY'] = os.environ['FLASK_SECRET']
=======
    app.config['SECRET_KEY'] = 'super secret key' # TODO
>>>>>>> 0f3918eda4471fc2c9ce026d2cc8b3a1b5570329
    app.app_context().push()
    db.init_app(app)
    db.create_all()
    return app
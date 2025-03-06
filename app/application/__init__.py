import os
from flask import Flask
from flask_migrate import Migrate

from application.models import db
from application import config

migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = config.DATABASE_CONNECTION_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.environ['FLASK_SECRET']
    db.init_app(app)
    migrate.init_app(app, db)
    
    with app.app_context():
        from application import routes
        #db.create_all() # Migrate will handle table creation.
    
    return app
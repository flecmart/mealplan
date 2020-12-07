import json

from flask import request

from . import create_app
from .models import db, Cats

app = create_app()

@app.route('/', methods=['GET'])
def fetch():
    cats = Cats.query.all()
    all_cats = []
    for cat in cats:
        new_cat = {
            "id": cat.id,
            "name": cat.name,
            "price": cat.price,
            "breed": cat.breed
        }

        all_cats.append(new_cat)
    return json.dumps(all_cats), 200


# todo create routes for data examples
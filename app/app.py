import json

from flask import request, flash

from . import create_app
from . import database
from .models import db, Recipe, PlannedMeal

app = create_app()
IMG_FOLDER = '../img'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

@app.route('/', methods=['GET'])
def show_data():
    recipes = database.query_all(Recipe)
    recipe_json = []
    for recipe in recipes:
        new_recipe = {
            "id": recipe.id,
            "name": recipe.name,
            "ingredients": recipe.ingredients,
            "instructions": recipe.instructions,
            "time": recipe.time,
            "image_path": recipe.image_path
        }
        recipe_json.append(new_recipe)
    return json.dumps(recipe_json), 200
    
@app.route('/add_recipe', methods=['POST'])
def save_recipe():
    name = request.form['name']
    time = request.form['time']
    ingredients = request.form['ingredients']
    instructions = request.form['instructions']
    image_path = '' # TODO: define default image
    # TODO: request image_path
    # e.g. upload img files: https://stackoverflow.com/questions/44926465/upload-image-in-flask
    # it should also be able to add images to recipes later on, edit recipes in general

    if time == '': 
        time = 30 # default in min

    if image_path == '':
        image_path = 'default'

    if len(name) == 0 or len(ingredients) == 0 or len(instructions) == 0:
        flash('Please fill in Name, Ingredients, and Instructions.', 'negative')

    same_recipe = Recipe.query.filter_by(name=name, instructions=instructions, cookbook_id=c_book.id).first()
    if same_recipe:
        flash(f'The recipe {name} already exists.', 'negative')

    database.add_instance(Recipe(name, str(ingredients), instructions, str(time), str(image_path)))
    flash(f'Recipe {name} saved.', 'positive')
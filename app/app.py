import json

from flask import request, flash, render_template

from . import create_app
from . import database
from . import helper_functs
from .models import db, Recipe, Event

from .debugger import initialize_flask_server_debugger_if_needed
initialize_flask_server_debugger_if_needed()

app = create_app()
IMG_FOLDER = '../img'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

@app.route("/")
def index():
    return render_template('full-calendar.html', recipes=database.query_all(Recipe))

@app.route('/data')
def return_data():
    events = database.query_all(Event)
    all_events = []
    for event in events:
        recipe = Recipe.query.filter_by(id=event.id).first()
        all_events.append({"title":recipe.name, "start":event.date, "id":recipe.id})
    
    return json.dumps(all_events, default=str)

@app.route('/test', methods=['GET'])
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

@app.route('/full-calendar', methods=['POST', 'GET'])
def cal_display():
    if request.method == 'GET':
        return render_template('full-calendar.html', recipes=database.query_all(Recipe))

    else: # 'POST'
        # displays calendar with updated changes
        recipes = database.query_all(Recipe)
        if recipes == []:
            flash("Add some recipes to your cookbook.", 'negative')
            return render_template('full-calendar.html', recipes=recipes)

        date = request.form['date']
        recipe_id = request.form['name']

        database.add_instance(Event, fk_recipe=recipe_id, date=date)

        return render_template('full-calendar.html', recipes=recipes)
    
@app.route('/recipe-added', methods=['POST'])
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

    ingredients = ';'.join(ingredients.splitlines())

    same_recipe = Recipe.query.filter_by(name=name).first()
    if same_recipe:
        flash(f'The recipe {name} already exists.', 'negative')

    database.add_instance(Recipe, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time), image_path=str(image_path))
    flash(f'Recipe {name} saved.', 'positive')

    return render_template('full-calendar.html', recipes=database.query_all(Recipe))

@app.route("/remove-recipe", methods=['POST'])
def delete_recipe():
    recipe_id = request.form["id"]

    # removes events with that recipe
    events_to_go = Event.query.filter_by(fk_recipe=recipe_id).all()
    for event in events_to_go:
        Event.query.filter_by(id=event.id).delete()

    # removes recipe from db
    Recipe.query.filter_by(id=recipe_id).delete()
    db.session.commit()

    return render_template('recipe-index.html', recipes=database.query_all(Recipe))

@app.route("/modal-recipe", methods=['POST'])
def display_modal_recipe():
    recipe_date = request.form["recipe_date"]
    event = Event.query.filter_by(date=recipe_date).first()
    recipe = Recipe.query.filter_by(id=event.fk_recipe).first()

    return render_template('recipe.html', recipe=recipe, instructions=recipe.get_instructions(), recipe_date=recipe_date, ingredients=recipe.get_ingredients_list())


@app.route("/recipe/<recipe_id>")
def display_recipe(recipe_id):
    recipe = Recipe.query.filter_by(id=recipe_id).first()
    button_flag = True
    
    return render_template('recipe.html', recipe=recipe, instructions=recipe.get_instructions(), button_flag=button_flag, ingredients=recipe.get_ingredients_list())

@app.route("/recipe-index")
def display_index():
    return render_template('recipe-index.html', recipes=database.query_all(Recipe))
  
@app.route('/remove-meal', methods=['POST'])
def delete_meal_event():
    event_date = request.form['dinner_to_remove']
    
    Event.query.filter_by(date=event_date).delete()
    db.session.commit()

    return render_template('full-calendar.html', recipes=database.query_all(Recipe))

@app.route("/ingredients")
def display_ingredients():
    """
    Diplays a list of ingredients for recipes of all events for the current week
    """
    events = Event.query.filter(Event.date >= helper_functs.get_start_of_week())

    ingredient_lists = []
    for event in events:
        recipe = Recipe.query.filter_by(id=event.id).first()
        ingredient_lists.append(recipe.get_ingredients_list())
    
    # TODO: fix nltk download here
    return render_template('ingredients.html', ingredients_dict=helper_functs.make_shopping_list(ingredient_lists), start=helper_functs.get_today_string(), end=helper_functs.get_week_from_string())
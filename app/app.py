from .debugger import initialize_flask_server_debugger_if_needed
initialize_flask_server_debugger_if_needed()

import os
import json

from datetime import datetime
from io import BytesIO
from urllib.request import urlopen
from flask import request, flash, render_template
from recipe_scrapers import scrape_me
from todoist.api import TodoistAPI
from . import create_app
from . import database
from . import helper_functs
from .models import db, Recipe, Event

def get_todoist_project_id(name):
    for project in api.state['projects']:
        if project['name'] == name:
            return project['id']
    return None

api = TodoistAPI(os.environ['TODOIST_TOKEN'])
api.sync()
shopping_list = get_todoist_project_id('Einkaufsliste')

app = create_app()
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    return render_template('full-calendar.html', recipes=database.query_all(Recipe))

@app.route('/test', methods=['GET'])
def show_data():
    #api.items.add('TestFromPython', project_id=shopping_list)
    #api.commit()
    recipes = database.query_all(Recipe)
    recipe_json = []
    for recipe in recipes:
        new_recipe = {
            "id": recipe.id,
            "name": recipe.name,
            "ingredients": recipe.ingredients,
            "instructions": recipe.instructions,
            "time": recipe.time,
            "image": recipe.image
        }
        recipe_json.append(new_recipe)
    return json.dumps(recipe_json), 200

@app.route('/data')
def return_data():
    events = database.query_all(Event)
    all_events = []
    for event in events:
        recipe = Recipe.query.filter_by(id=event.fk_recipe).first()
        if recipe.image:
            all_events.append({"title":recipe.name, "start":event.date, "id":recipe.id, "imageurl":f"/recipe/{recipe.id}/img"})
        else:
            all_events.append({"title":recipe.name, "start":event.date, "id":recipe.id, "imageurl":"/static/images/default.png"})
    
    return json.dumps(all_events, default=str)

@app.route('/full-calendar', methods=['POST', 'GET'])
def cal_display():
    if request.method == 'GET':
        return render_template('full-calendar.html', recipes=database.query_all(Recipe))

    else: # 'POST'
        # displays calendar with updated changes
        recipes = database.query_all(Recipe)
        if recipes == []:
            flash("Bitte füge dem Kochbuch Rezepte hinzu.", 'negative')
            return render_template('full-calendar.html', recipes=recipes)

        date = request.form['date']
        recipe_id = request.form['name']

        database.add_instance(Event, fk_recipe=recipe_id, date=date)

        return render_template('full-calendar.html', recipes=recipes)

@app.route('/add-recipe', methods=['POST'])
def add_recipe():
    name = request.form['name']
    time = request.form['time']
    ingredients = request.form['ingredients']
    instructions = request.form['instructions']
    image = request.files['image']

    if time == '': 
        time = 30 # default in min
 
    if len(name) == 0 or len(ingredients) == 0 or len(instructions) == 0:
        flash('Bitte mindestens Namen, Zutaten und Zubereitung ausfüllen.', 'negative')
        return render_template('full-calendar.html', recipes=database.query_all(Recipe))

    ingredients = ';'.join(ingredients.splitlines())

    same_recipe = Recipe.query.filter_by(name=name).first()
    if same_recipe:
        flash(f'Das Rezept {name} existiert bereits.', 'negative')
        return render_template('full-calendar.html', recipes=database.query_all(Recipe))

    # if user does not select file, browser also submit an empty part without filename
    if image.filename == '':
        database.add_instance(Recipe, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time), image=None)
    elif not allowed_file(image.filename):
        flash(f'Nur folgende Dateiformate für Bilder erlaubt: {ALLOWED_EXTENSIONS}.', 'negative')
        return render_template('full-calendar.html', recipes=database.query_all(Recipe))
    else:
        database.add_instance(Recipe, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time), image=image.read())
        
    flash(f'Rezept {name} gespeichert.', 'positive')
    return render_template('full-calendar.html', recipes=database.query_all(Recipe))

@app.route('/import-recipe', methods=['POST'])
def import_recipe():
    link = request.form['link']
    image = request.files['image']

    scraper = scrape_me(link)

    name = f'{scraper.title()} - {scraper.yields()}'
    time = scraper.total_time()
    ingredients = ';'.join(scraper.ingredients())
    instructions = scraper.instructions()

    same_recipe = Recipe.query.filter_by(name=name).first()
    if same_recipe:
        flash(f'Das Rezept {name} existiert bereits.', 'negative')
        return render_template('full-calendar.html', recipes=database.query_all(Recipe))

    # if user does not select file, browser also submit an empty part without filename
    if image.filename == '':
        image_stream = BytesIO(urlopen(scraper.image()).read())
        database.add_instance(Recipe, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time), image=image_stream.read())
    elif not allowed_file(image.filename):
        flash(f'Nur folgende Dateiformate für Bilder erlaubt: {ALLOWED_EXTENSIONS}.', 'negative')
        return render_template('full-calendar.html', recipes=database.query_all(Recipe))
    else:
        database.add_instance(Recipe, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time), image=image.read())
        
    flash(f'Rezept {name} gespeichert.', 'positive')
    return render_template('full-calendar.html', recipes=database.query_all(Recipe))

@app.route("/edit-recipe",  methods = ['POST'])
def edit_recipe():
    recipe_id = int(request.form["id"])
    name = request.form['name']
    time = request.form['time']
    ingredients = request.form['ingredients']
    instructions = request.form['instructions']
    image = request.files['image']

    if time == '': 
        time = 30 # default in min
 
    if len(name) == 0 or len(ingredients) == 0 or len(instructions) == 0:
        flash('Bitte mindestens Namen, Zutaten und Zubereitung ausfüllen.', 'negative')
        return render_template('full-calendar.html', recipes=database.query_all(Recipe))

    ingredients = ';'.join(ingredients.splitlines())

    same_recipe = Recipe.query.filter_by(name=name).first()
    if same_recipe and same_recipe.id != recipe_id:
        flash(f'Das Rezept {name} existiert bereits.', 'negative')
        return render_template('full-calendar.html', recipes=database.query_all(Recipe))

    # if user does not select file, browser also submit an empty part without filename
    if image.filename == '':
        database.update_instance(Recipe, recipe_id, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time))
    elif not allowed_file(image.filename):
        flash(f'Nur folgende Dateiformate für Bilder erlaubt: {ALLOWED_EXTENSIONS}.', 'negative')
        return render_template('full-calendar.html', recipes=database.query_all(Recipe))
    else:
        database.update_instance(Recipe, recipe_id, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time), image=image.read())
        
    flash(f'Rezept {name} gespeichert.', 'positive')
    return render_template('full-calendar.html', recipes=database.query_all(Recipe))
    
@app.route("/delete-recipe", methods=['POST'])
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

@app.route('/recipe/<recipe_id>/img')
def recipe_image(recipe_id):
    recipe = Recipe.query.filter_by(id=recipe_id).first()
    return app.response_class(recipe.image, mimetype='application/octet-stream')

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
    start = request.args.get('start')
    end = request.args.get('end')

    if start == 'undefined' or end == 'undefined':
        start_date = helper_functs.get_today_string()
        end_date = helper_functs.get_week_from_string()
        events = Event.query.filter(Event.date >= helper_functs.get_start_of_week())
    else:
        start_date = "{date:%d.%m}".format(date=datetime.strptime(start, '%Y-%m-%d').date())
        end_date = "{date:%d.%m}".format(date=datetime.strptime(end, '%Y-%m-%d').date())
        events = Event.query.filter(Event.date.between(start, end))

    ingredient_lists = []
    for event in events:
        recipe = Recipe.query.filter_by(id=event.fk_recipe).first()
        ingredient_lists.append(recipe.get_ingredients_list())
    
    return render_template('ingredients.html', ingredients_dict=helper_functs.make_shopping_list(ingredient_lists), start=start_date, end=end_date)
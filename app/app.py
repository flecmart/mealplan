from flask.helpers import url_for
from .debugger import initialize_flask_server_debugger_if_needed
initialize_flask_server_debugger_if_needed()

import os
import json
import time

from datetime import datetime, timedelta
from io import BytesIO
from urllib.request import urlopen
from flask import request, flash, render_template, jsonify, redirect
from sqlalchemy import and_
from recipe_scrapers import scrape_me
from todoist.api import TodoistAPI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from PIL import Image

from . import create_app
from . import database
from . import helper_functs
from .models import db, Recipe, Event

def get_todoist_project_id(api, name):
    for project in api.state['projects']:
        if project['name'] == name:
            return project['id']
    return None

todoist_api = TodoistAPI(os.environ['TODOIST_TOKEN'])
todoist_api.sync()
shopping_list = get_todoist_project_id(todoist_api, os.environ['TODOIST_LIST'])

app = create_app()
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def bust_cache_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(app.root_path,
                                     endpoint, filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)

@app.route("/")
def index():
    return render_template('full-calendar.html', recipes=database.query_all(Recipe))

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
            "time": recipe.time
        }
        recipe_json.append(new_recipe)
    return json.dumps(recipe_json), 200

@app.route('/data')
def return_data():
    events = database.query_all(Event)
    all_events = []
    for event in events:
        recipe = Recipe.query.filter_by(id=event.fk_recipe).first()
        all_events.append({"title":recipe.name, "start":event.date, "id":event.id, "imageurl":f"/static/images/{recipe.icon}"})
    
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

        events = Event.query.filter_by(date=date).all()
        for event in events:
            if int(recipe_id) == event.fk_recipe:
                 flash("Dieses Rezept ist an diesem Tag bereits geplant.", 'negative')
                 return render_template('full-calendar.html', recipes=recipes)

        database.add_instance(Event, fk_recipe=recipe_id, date=date)
        return render_template('full-calendar.html', recipes=recipes)

@app.route('/add-recipe', methods=['POST'])
def add_recipe():
    name = request.form['name']
    time = request.form['time']
    ingredients = request.form['ingredients']
    instructions = request.form['instructions']
    icon = request.form['icon']
    image = request.files['image']

    if time == '': 
        time = 30 # default in min
 
    if len(name) == 0 or len(ingredients) == 0 or len(instructions) == 0:
        flash('Bitte mindestens Namen, Zutaten und Zubereitung ausfüllen.', 'negative')
        return redirect(url_for('cal_display'))

    ingredients = ';'.join(ingredients.splitlines())

    same_recipe = Recipe.query.filter_by(name=name).first()
    if same_recipe:
        flash(f'Das Rezept {name} existiert bereits.', 'negative')
        return redirect(url_for('cal_display'))

    if icon == '':
        icon = 'defaultIcon.png'

    # if user does not select file, browser also submit an empty part without filename
    if image.filename == '':
        database.add_instance(Recipe, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time), icon=icon, image=None)
    elif not allowed_file(image.filename):
        flash(f'Nur folgende Dateiformate für Bilder erlaubt: {ALLOWED_EXTENSIONS}.', 'negative')
        return redirect(url_for('cal_display'))
    else:
        database.add_instance(Recipe, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time), icon=icon, image=image.read())
        
    flash(f'Rezept {name} gespeichert.', 'positive')
    return redirect(url_for('display_index'))

@app.route('/import-recipe', methods=['POST'])
def import_recipe():
    link = request.form['link']
    icon = request.form['icon']
    image = request.files['image']

    scraper = scrape_me(link)

    name = f'{scraper.title()} - {scraper.yields()}'
    time = scraper.total_time()
    ingredients = ';'.join(scraper.ingredients())
    instructions = scraper.instructions()

    same_recipe = Recipe.query.filter_by(name=name).first()
    if same_recipe:
        flash(f'Das Rezept {name} existiert bereits.', 'negative')
        return redirect(url_for('cal_display'))

    if icon == '':
        icon = 'defaultIcon.png'

    # if user does not select file, browser also submit an empty part without filename
    if image.filename == '':
        image_stream = BytesIO(urlopen(scraper.image()).read())
        database.add_instance(Recipe, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time), icon=icon, image=image_stream.read())
    elif not allowed_file(image.filename):
        flash(f'Nur folgende Dateiformate für Bilder erlaubt: {ALLOWED_EXTENSIONS}.', 'negative')
        return redirect(url_for('cal_display'))
    else:
        database.add_instance(Recipe, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time), icon=icon, image=image.read())
        
    flash(f'Rezept {name} gespeichert.', 'positive')
    return redirect(url_for('display_index'))

@app.route("/edit-recipe",  methods = ['POST'])
def edit_recipe():
    recipe_id = int(request.form["id"])
    name = request.form['name']
    time = request.form['time']
    ingredients = request.form['ingredients']
    instructions = request.form['instructions']
    icon = request.form['icon']
    image = request.files['image']

    if time == '': 
        time = 30 # default in min
 
    if len(name) == 0 or len(ingredients) == 0 or len(instructions) == 0:
        flash('Bitte mindestens Namen, Zutaten und Zubereitung ausfüllen.', 'negative')
        return redirect(url_for('display_index'))

    ingredients = ';'.join(ingredients.splitlines())

    same_recipe = Recipe.query.filter_by(name=name).first()
    if same_recipe and same_recipe.id != recipe_id:
        flash(f'Das Rezept {name} existiert bereits.', 'negative')
        return redirect(url_for('display_index'))

    # if user does not select file, browser also submit an empty part without filename
    if image.filename == '':
        database.update_instance(Recipe, recipe_id, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time), icon=icon)
    elif not allowed_file(image.filename):
        flash(f'Nur folgende Dateiformate für Bilder erlaubt: {ALLOWED_EXTENSIONS}.', 'negative')
        return redirect(url_for('display_index'))
    else:
        database.update_instance(Recipe, recipe_id, name=name, ingredients=str(ingredients), instructions=instructions, time=str(time), icon=icon, image=image.read())
        
    flash(f'Rezept {name} gespeichert.', 'positive')
    return redirect(url_for('display_index'))
    
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

    return redirect(url_for('display_index'))

@app.route("/modal-recipe", methods=['POST'])
def display_modal_recipe():
    recipe_date = request.form["recipe_date"]
    recipe_name = request.form["recipe_name"]
    recipe = Recipe.query.filter_by(name=recipe_name).first()

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

@app.route("/move-meal", methods=['POST'])
def move_meal():
    event_date = request.form["event_date"]
    event_name = request.form["event_name"]
    event_delta = request.form["event_delta"]

    old_date = datetime.strptime(event_date, '%Y-%m-%d') - timedelta(days=int(event_delta))

    recipe = Recipe.query.filter_by(name=event_name).first()
    event = Event.query.filter(and_(Event.date == old_date.strftime('%Y-%m-%d'), Event.fk_recipe == recipe.id)).first()

    database.update_instance(Event, event.id, date=event_date)

    return jsonify(success=True)

@app.route('/remove-meal', methods=['POST'])
def delete_meal_event():
    event_date = request.form['date_to_remove']
    event_name = request.form['dinner_to_remove']

    recipe = Recipe.query.filter_by(name=event_name).first()
    Event.query.filter(and_(Event.date == event_date, Event.fk_recipe == recipe.id)).delete()
    db.session.commit()

    return redirect(url_for('cal_display'))

@app.route("/ingredients")
def display_ingredients():
    """
    Diplays a list of ingredients for recipes of all events for the current week
    """
    start = request.args.get('start')
    end = request.args.get('end')

    if start == 'undefined' or start is None or end == 'undefined' or end is None:
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

@app.route("/export-todoist", methods = ['POST'])
def export_todoist():
    """Export checked ingredients to configured todoist list.
    """
    ingedients_to_export = request.form.getlist('export_ingredient')
    for entry in ingedients_to_export:
        todoist_api.items.add(entry, project_id=shopping_list)
    todoist_api.commit()
    flash(f'Zutaten nach Todoist Einkaufsliste exportiert: {ingedients_to_export}')
    return redirect(url_for('cal_display'))

@app.route('/week', methods=['GET'])
def screenshot_week():
    """Generates a screenshot of the current week and returns it. 
    The resolution is 600x800 to be compatible with kindle onlinescreensaver.

    Returns:
        png: Image of current week
    """
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--hide-scrollbars')
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(os.environ["SCREENSHOT_URL"])
    driver.find_element_by_xpath('//*[@id="calendar"]/div[1]/div[2]/div/button[2]').click()
    time.sleep(3)
    element = driver.find_element_by_xpath('//*[@id="calendar"]/div[2]')
    element.screenshot('/app/static/week.png')
    im = Image.open('/app/static/week.png').convert('L')
    im = im.resize((800,600))
    im = im.rotate(90, expand=True)
    im.save('/app/static/week.png')
    driver.quit()
    return redirect(bust_cache_url_for('static', filename='week.png'))

@app.route("/purge")
def purge_events():
    """
    Purge old events from calender.
    Possible Query parameter: before=yyyy-mm-dd
    Default behavior: purge events older than 6 months
    """
    before_date = request.args.get('before')

    if before_date == 'undefined' or before_date is None:
        before_date = helper_functs.get_date_six_months_ago()
    
    Event.query.filter(Event.date <= before_date).delete()
    db.session.commit()
    
    return jsonify(success=True)
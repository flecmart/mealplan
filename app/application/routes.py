from flask.helpers import url_for

import os
import json
import time

from datetime import datetime, timedelta
from io import BytesIO
from urllib.request import urlopen
from flask import current_app, request, flash, render_template, jsonify, redirect, session
from sqlalchemy import and_
from recipe_scrapers import scrape_me
from recipe_scrapers._exceptions import SchemaOrgException
from todoist_api_python.api import TodoistAPI
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from PIL import Image
from collections import defaultdict
from dataclasses import dataclass

from . import database
from . import helper_functs
from .models import db, Recipe, Event

def get_todoist_project_id(api, name):
    for project in api.get_projects():
        if project.name == name:
            return project.id
    return None

@dataclass
class RecipeCache:
    name: str
    time: int
    ingredients: str
    instructions: str
    icon: str
    image_url: str

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def bust_cache_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(current_app.root_path,
                                     endpoint, filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)

@current_app.route("/")
def index():
    return render_template('full-calendar.html', recipes=database.query_all(Recipe))

@current_app.route('/data')
def return_data():
    events = database.query_all(Event)
    all_events = []
    for event in events:
        recipe = Recipe.query.filter_by(id=event.fk_recipe).first()
        all_events.append({"title":recipe.name, "start":event.date, "id":event.id, "imageurl":f"/static/images/{recipe.icon}"})
    
    return json.dumps(all_events, default=str)

@current_app.route('/full-calendar', methods=['POST', 'GET'])
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

@current_app.post('/add-recipe')
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
        database.add_instance(Recipe, name=name, ingredients=str(ingredients), instructions=instructions, time=int(time), icon=icon, image=None)
    elif not allowed_file(image.filename):
        flash(f'Nur folgende Dateiformate für Bilder erlaubt: {ALLOWED_EXTENSIONS}.', 'negative')
        return redirect(url_for('cal_display'))
    else:
        database.add_instance(Recipe, name=name, ingredients=str(ingredients), instructions=instructions, time=int(time), icon=icon, image=image.read())
        
    flash(f'Rezept {name} gespeichert.', 'positive')
    return redirect(url_for('display_index'))

@current_app.post('/import-recipe')
def import_recipe():
    link = request.form['link']
    icon = request.form['icon']
    
    try:
        # scrape with recipe_scraper
        recipe = scrape_recipe(link, icon)
        if recipe == None:
            return redirect(url_for('cal_display'))
        
        database.add_instance(Recipe,
                              name=recipe.name,
                              ingredients=str(recipe.ingredients),
                              instructions=recipe.instructions,
                              time=int(recipe.time),
                              icon=recipe.icon, 
                              image=BytesIO(urlopen(recipe.image_url).read()).read())
        flash(f'Rezept {recipe.name} gespeichert.', 'positive')
    except Exception as ex:
        try:
            # try generic scraping for schema
            recipe = scrape_generic_recipe(link, icon)
            if recipe == None:
                return redirect(url_for('cal_display'))
            if recipe.instructions == '':
                 # handle cookidoo recipes that hide instrutions behind a paywall
                 # cache the scraped info and ask for instructions in an additional modal
                 # instrutions can be copy / pasted from browser with logged in cookidoo account to dump these recipes for the future
                session['import_recipe_cache'] = recipe
                return render_template('full-calendar.html', recipes=database.query_all(Recipe), import_additional_instructions="True")
        except Exception as ex:
            flash(f'Exception during import: {ex}')
    
    return redirect(url_for('display_index'))

def scrape_recipe(link, icon):
    recipe = RecipeCache(None, None, None, None, None, None)
    scraper = scrape_me(link)
    
    recipe.name = scraper.title()
    try:
        recipe.time = scraper.total_time()
    except SchemaOrgException:
        recipe.time = 30 # use default 30 mins
    recipe.ingredients = ';'.join(scraper.ingredients())
    recipe.instructions = scraper.instructions()

    same_recipe = Recipe.query.filter_by(name=recipe.name).first()
    if same_recipe:
        flash(f'Das Rezept {recipe.name} existiert bereits.', 'negative')
        return None

    if icon == '':
        recipe.icon = 'defaultIcon.png'
    else:
        recipe.icon = icon

    recipe.image_url = scraper.image()

    return recipe    

def scrape_generic_recipe(link, icon):
    recipe = RecipeCache(None, None, None, None, None, None)
    scraper = scrape_me(link, wild_mode=True)
    
    recipe.name = scraper.title()
    try:
        recipe.time = scraper.total_time()
    except SchemaOrgException:
        recipe.time = 30 # use default 30 mins
    recipe.ingredients = ';'.join(scraper.ingredients())
    recipe.instructions = scraper.instructions()

    same_recipe = Recipe.query.filter_by(name=recipe.name).first()
    if same_recipe:
        flash(f'Das Rezept {recipe.name} existiert bereits.', 'negative')
        return None

    if icon == '':
        recipe.icon = 'defaultIcon.png'
    else:
        recipe.icon = icon

    recipe.image_url = scraper.image()
    
    return recipe    

@current_app.post('/import-cookidoo-instructions')
def import_cookidoo_instructions():
    instructions = request.form['instructions']
    recipe = session.get('import_recipe_cache')
    if recipe != None:
        recipe['instructions'] = replace_thermomix_symbols(instructions)
        database.add_instance(Recipe,
                              name=recipe['name'],
                              ingredients=str(recipe['ingredients']),
                              instructions=recipe['instructions'],
                              time=int(recipe['time']),
                              icon=recipe['icon'], 
                              image=BytesIO(urlopen(recipe['image_url']).read()).read())
        session['import_recipe_cache'] = None # reset cache
        flash(f'Rezept {recipe["name"]} gespeichert.', 'positive')
        return redirect(url_for('display_index'))
    else:
        flash(f'Rezept {recipe["name"]} konnte nicht gespeichert werden.', 'negative')
    return redirect(url_for('cal_display'))

def replace_thermomix_symbols(instructions):
    # vorwerk uses private unicode char space -> replace them with standard stuff https://unicode-table.com/de/1F963/
    # \ue003 is "Linkslauf"
    # \ue002 is "Rührstufe"
    return instructions.replace('\ue003', '\u27f2').replace('\ue002', '\U0001F963').replace('\ue01e', '\u2707')

@current_app.post("/edit-recipe")
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
        database.update_instance(Recipe, recipe_id, name=name, ingredients=str(ingredients), instructions=instructions, time=int(time), icon=icon)
    elif not allowed_file(image.filename):
        flash(f'Nur folgende Dateiformate für Bilder erlaubt: {ALLOWED_EXTENSIONS}.', 'negative')
        return redirect(url_for('display_index'))
    else:
        database.update_instance(Recipe, recipe_id, name=name, ingredients=str(ingredients), instructions=instructions, time=int(time), icon=icon, image=image.read())
        
    flash(f'Rezept {name} gespeichert.', 'positive')
    return redirect(url_for('display_index'))
    
@current_app.post("/delete-recipe")
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

@current_app.post("/modal-recipe")
def display_modal_recipe():
    recipe_date = request.form["recipe_date"]
    recipe_name = request.form["recipe_name"]
    recipe = Recipe.query.filter_by(name=recipe_name).first()

    return render_template('recipe.html', recipe=recipe, instructions=recipe.get_instructions(), recipe_date=recipe_date, ingredients=recipe.get_ingredients_list())

@current_app.route("/recipe/<recipe_id>")
def display_recipe(recipe_id):
    recipe = Recipe.query.filter_by(id=recipe_id).first()
    button_flag = True
    
    return render_template('recipe.html', recipe=recipe, instructions=recipe.get_instructions(), button_flag=button_flag, ingredients=recipe.get_ingredients_list())

@current_app.route('/recipe/<recipe_id>/img')
def recipe_image(recipe_id):
    recipe = Recipe.query.filter_by(id=recipe_id).first()
    return current_app.response_class(recipe.image, mimetype='application/octet-stream')

@current_app.route("/recipe-index")
def display_index():
    return render_template('recipe-index.html', recipes=database.query_all(Recipe))

@current_app.post("/move-meal")
def move_meal():
    event_date = request.form["event_date"]
    event_name = request.form["event_name"]
    event_delta = request.form["event_delta"]

    old_date = datetime.strptime(event_date, '%Y-%m-%d') - timedelta(days=int(event_delta))

    recipe = Recipe.query.filter_by(name=event_name).first()
    event = Event.query.filter(and_(Event.date == old_date.strftime('%Y-%m-%d'), Event.fk_recipe == recipe.id)).first()

    database.update_instance(Event, event.id, date=event_date)

    return jsonify(success=True)

@current_app.post('/remove-meal')
def delete_meal_event():
    event_date = request.form['date_to_remove']
    event_name = request.form['dinner_to_remove']

    recipe = Recipe.query.filter_by(name=event_name).first()
    Event.query.filter(and_(Event.date == event_date, Event.fk_recipe == recipe.id)).delete()
    db.session.commit()

    return redirect(url_for('cal_display'))

@current_app.route("/ingredients")
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

    ingredient_lists = defaultdict(list)
    for event in events:
        recipe = Recipe.query.filter_by(id=event.fk_recipe).first()
        ingredient_lists[recipe.name] += (recipe.get_ingredients_list())
    
    return render_template('ingredients.html', ingredients_dict=helper_functs.make_shopping_list(ingredient_lists), start=start_date, end=end_date)

@current_app.post("/export-todoist")
def export_todoist():
    """Export checked ingredients to configured todoist list.
    """
    ingedients_to_export = request.form.getlist('export_ingredient')
    todoist_api = TodoistAPI(os.environ['TODOIST_TOKEN'])
    shopping_list_id = get_todoist_project_id(todoist_api, os.environ['TODOIST_LIST'])
    for entry in ingedients_to_export:
        try:
            todoist_api.add_task(content=entry, project_id=shopping_list_id)
        except Exception as e:
            print(f'could not add task {entry} to todoist: {e}')
            flash(f'Fehler beim exportieren von {entry}!')
    flash(f'Zutaten nach Todoist Einkaufsliste exportiert: {ingedients_to_export}')
    return url_for('cal_display') # redirect happens in js handler

@current_app.get('/week')
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
    driver.find_element('xpath', '//*[@id="calendar"]/div[1]/div[2]/div/button[2]').click()
    time.sleep(3)
    element = driver.find_element('xpath', '//*[@id="calendar"]/div[2]')
    element.screenshot('/app/application/static/week.png')
    im = Image.open('/app/application/static/week.png').convert('L')
    im = im.resize((800,600))
    im = im.rotate(90, expand=True)
    im.save('/app/application/static/week.png')
    driver.quit()
    return redirect(bust_cache_url_for('static', filename='week.png'))

@current_app.route("/purge")
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

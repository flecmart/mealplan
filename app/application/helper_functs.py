import datetime
import nltk
import unicodedata
import re

from flask import flash
from fractions import Fraction
from urllib import request

from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import SchemaOrgException
from dataclasses import dataclass
from application.models import Recipe

list_of_measures = ['Pck', 'Packung', 'TL', 'EL', 'Esslöffel', 'Teelöffel', 'liter', 'l' 'can', 'cup', 'cups', 'pint', 'quart', 'tablespoons', 'tablespoon', 'tbs', 'tb', 't', 'ts', 
                    'teaspoon', 'tsps', 'gr', 'grams', 'gram', 'g' ,'kilo', 'kilogram', 'kg', 'dash', 'pinch', 'sprig', 'oz', 'ounce', 'ounces', 'cloves', 'lb', 'pound', 'pd', 'ml',
                    'milliliter', 'Bund', 'Zweig']

words_not_recognized_as_nouns = ['flour', 'olive', 'oz', 'Lauch', 'Couscous', 'Kreuzkümmelpulver']

list_of_pos = ['NN', 'NNP', 'NNS', 'NNPS']

@dataclass
class RecipeCache:
    name: str
    time: int
    ingredients: str
    instructions: str
    icon: str
    image_url: str
    cookidoo_id: str


def get_today_string():
    return "{date:%d.%m}".format(date=datetime.datetime.now())

def get_date_six_months_ago():
    six_months_ago = datetime.datetime.now() - datetime.timedelta(6*30)
    return "{date:%Y-%m-%d}".format(date=six_months_ago)

def get_week_from_string():
    today = datetime.datetime.today()
    week_from_date = today + datetime.timedelta(days=7)
    week_from = "{date:%d.%m}".format(date=week_from_date)
    return week_from

def get_start_of_week():
    today = datetime.datetime.today()
    start = today - datetime.timedelta(days=today.weekday())
    return "{date:%Y-%m-%d}".format(date=start)

def strip_german_plural(string_in):
    return string_in.replace('(s)', '').replace('(n)', '')

def get_nouns(ingredients_string): 
    ''' strips adjectives and amounts from ingredient return LIST'''
    ingredients = nltk.sent_tokenize(strip_german_plural(ingredients_string))
    nouns = []
    for ingredient in ingredients:
        for word,pos in nltk.pos_tag(nltk.word_tokenize(str(ingredient))):
            if word in words_not_recognized_as_nouns:
                nouns.append(word)
            elif (pos in list_of_pos):
                nouns.append(word)
        
    return nouns

def get_amount(ingredient_string):
    ''' given an ingredient as a string extract the amount converts to float'''
    split_list_of_ingredient = ingredient_string.split()
    for word in split_list_of_ingredient:
        try:
            num = int(word)
            #return float(num)
            return num
        except ValueError:
            try:
                fl = float(str(word).replace(',','.'))
                return fl
            except ValueError:
                try:
                    # adding a float to fraction forces Fraction to float
                    fr = Fraction(word)
                    fr += 0.0
                    return fr
                except ValueError:
                    # try and see if unicode
                    try: 
                        uni = ord(word)
                        # use unicode conmversion function here
                        if uni in range(8528-8543) or uni == 188 or uni == 189 or uni == 190:
                            uni_fl = unicodedata.numeric(chr(uni))
                            return uni_fl 
                        else: pass
                    except TypeError:
                        try:
                            pattern = re.compile("\d+-\d+")
                            digits = []
                            if pattern.match(word):
                                value_range = pattern.match(word)
                                print(str(value_range.span()))
                                index_range = value_range.span()
                                value_string = word[index_range[0]:index_range[1]]
                                for item in value_string.split("-"):
                                    digits.append(item)
                                dig_sum = 0
                                for item in digits:
                                    dig_sum += int(item)
                                    
                                return dig_sum//2
                            
                        except TypeError:
                            pass
                            
def get_measure(ingredient):
    ''' parses the list for a word that matches a unit of measure and returns that measure or ""'''
    words = ingredient.split()
    for word in words:
        if word.upper() in map(str.upper, list_of_measures): 
            return word
    return ""

def make_ingredient_dict(recipe, list_of_ingredients):
    ''' takes a list of ingredients and returns a dictionary of key=ingredient, value= number of ounces '''
    ingredient_dict = {}
    for ingredient in list_of_ingredients:
        ingredient = remove_german_recipe_plural(ingredient)
        amt = get_amount(ingredient)
        measurement = get_measure(ingredient)
        k_list = remove_amts_measures(ingredient)
        if not k_list:
            k_list.append(ingredient)
            k_list = k_list[0].split(' ')
            try:
                k_list.remove(str(amt))
            except:
                pass
            try:
                k_list.remove(measurement)
            except:
                pass
        name_key = ' '.join(k_list).title()
        measurement_key = f'__{measurement}' if measurement else ''
        key = f'{name_key}{measurement_key}' 
        # in the case of say water or salt and pepper
        if amt == None: # and measurement == "whole":
            amt = 1
        
        if key in ingredient_dict:
            try:
                # add amount
                ingredient_dict[key][0] += amt
            except TypeError:
                flash(f'Could nto add amount "{amt}" to "{ingredient_dict[key]}"!')
        else:
            ingredient_dict[key] = [amt, measurement, name_key, recipe]

    return ingredient_dict

def make_shopping_list(defaultdict_of_lists_of_ingredients):
    ''' takes a list of list returns one dict with ingred as key '''
    big_dict_of_ingredients = {}
    for recipe in defaultdict_of_lists_of_ingredients:
        ingred_dict = make_ingredient_dict(recipe, defaultdict_of_lists_of_ingredients[recipe])
        for item in ingred_dict:
            if item in big_dict_of_ingredients:
                try:
                    # add amount
                    big_dict_of_ingredients[item][0] += ingred_dict[item][0]
                    # add recipe reference
                    big_dict_of_ingredients[item][3] += ' & ' + ingred_dict[item][3]
                except TypeError:
                    flash(f'Could not add amount "{ingred_dict[item][0]}" to "{big_dict_of_ingredients[item]}"!')
            else:
                big_dict_of_ingredients[item] = ingred_dict[item]

    return big_dict_of_ingredients

def split_string_into_ngrams(string_x, number_for_n_ngram):
    sub_sects = nltk.ngrams(string_x.split(), number_for_n_ngram)
    grams = []
    for gram in sub_sects:
        grams.append(gram)
    return grams

def remove_amts_measures(string_x):
    '''should leave string with just nouns to parse for ngrams'''
    measure_to_remove = get_measure(string_x)
    noun_list = get_nouns(string_x)
    
    try:
        noun_list.remove(measure_to_remove)
    except ValueError:
        # no measure to remove
        pass
    finally:
        noun_list = [item for item in noun_list if item not in ['¼', '¾', '½']]
    return noun_list

def remove_german_recipe_plural(string_ingredient):
    '''remove plural from german ingrediants in brackts, e.g. Zwiebel(n) -> Zwiebel'''
    words = string_ingredient.split()
    stripped_words = []
    regex = re.compile(r"([a-zA-Z]+)(\([^\)]+\))")
    for word in words:
        if regex.match(word):
            stripped_words.append(regex.sub(r"\1", word))
        else:
            stripped_words.append(word)
    return (' ').join(stripped_words)

def prepare_ingredients(instructions):
    '''prepare instructions for better german natural language processing'''
    result = []
    for line in instructions:
        result.append(line
                        .replace('Möhren', 'Karotte(n)')
                        .replace('Karotten', 'Karotte(n)')
                        .replace('Knoblauchzehen', 'Knoblauchzehe(n)')
                        .replace('artoffeln', 'artoffel(n)')
                        .replace('Schalotten', 'Schalotte(n)')
                        .replace ('wiebeln','wiebel(n)'))
    return result

def extract_cookidoo_recipe_id(url):
    pattern = r"cookidoo\.de/recipes/recipe/de-DE/(r\d+)"
    match = re.search(pattern, url)

    if match:
        return match.group(1)
    else:
        return None


def scrape_recipe(link, icon, wild_mode=False):
    recipe = RecipeCache(None, None, None, None, None, None, None)
    html = request.urlopen(link).read()
    scraper = scrape_html(html, org_url=link, wild_mode=wild_mode)
    
    recipe.name = scraper.title()
    try:
        recipe.time = scraper.total_time()
    except SchemaOrgException:
        recipe.time = 30 # use default 30 mins
    recipe.ingredients = ';'.join(prepare_ingredients(scraper.ingredients()))
    recipe.instructions = scraper.instructions()
    recipe.cookidoo_id =  extract_cookidoo_recipe_id(link)

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
  
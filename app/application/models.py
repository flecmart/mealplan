import flask_sqlalchemy
import re

SQLALCHEMY_ENGINE_OPTIONS  = {
    'pool_size': 10,
    'pool_recycle': 60,
    'pool_pre_ping': True
}
db = flask_sqlalchemy.SQLAlchemy(engine_options=SQLALCHEMY_ENGINE_OPTIONS)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    ingredients = db.Column(db.Text, nullable=False) # comma separated
    instructions = db.Column(db.Text, nullable=False) # free text
    time = db.Column(db.Integer, nullable=True) # time in minutes
    icon = db.Column(db.String(64), nullable=False) # icon for calendar
    image = db.Column(db.LargeBinary, nullable=True) # optional recipe image
    __table_args__ = (db.UniqueConstraint('name', name='_uc_recipe_name'),)
    
    def __init__(self, name, ingredients, instructions, time, icon, image):
        self.name = name
        self.ingredients = ingredients
        self.instructions = instructions
        self.time = time
        self.icon = icon
        self.image = image

    def get_ingredients_list(self):
        return self.ingredients.split(';')

    def get_instructions(self):
        # remove step numbers (digits) if present since they are not ubiquitous in api recipes. Step nums added in template view
        instructions = re.sub('\d+\.', '', self.instructions)
        
        # removes html tags
        instructions = re.sub('<.*?>', '', instructions)

        # splits string at "." and ignore abbreviations
        instructions = re.split(r'(?<!ca)(?<!evtl)(?<!bzw)(?<!ggf)(?<!z)(?<!B)(?<!inkl)(?<!min)(?<!st)(?<!sek)(?<!gek)(?<!gr)(?<!g)(?<!kg)\.', instructions, flags=re.IGNORECASE)

        # handles cases where parentheses exist in instructions
        fresh_instructions = []
        for step in instructions:
            step = step.replace('(', '').replace(')', '').replace('!', '')
            fresh_instructions.append(step.strip())  

        # removes empty strings in list
        fresh_instructions = list(filter(lambda x: x not in ['', '/n'], fresh_instructions))

        return fresh_instructions

class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fk_recipe = db.Column(db.Integer, db.ForeignKey('recipe.id')) 
    date = db.Column(db.Date)

    def __init__(self, fk_recipe, date):
        self.fk_recipe = fk_recipe
        self.date = date

import flask_sqlalchemy

db = flask_sqlalchemy.SQLAlchemy()

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ingredients = db.Column(db.Text, nullable=False) # comma separated
    instructions = db.Column(db.Text, nullable=False) # free text vs csv? TODO: Format text
    time = db.Column(db.Integer, nullable=True) # time in minutes
    image_path = db.Column(db.String(255), nullable=True) # path to potential image in filesystem? TODO: new container mount?
    __table_args__ = (db.UniqueConstraint('name', name='_uc_recipe_name'),)
    
    def __init__(self, name, ingredients, instructions, time, image_path):
        self.name = name
        self.ingredients = ingredients
        self.instructions = instructions
        self.time = time
        self.image_path = image_path

    def get_ingredients_list(self):
        return self.ingredients.split(',')

class PlannedMeal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fk_recipe = db.Column(db.Integer, db.ForeignKey('recipe.id')) 
    date = db.Column(db.Date)

    def __init__(self, fk_recipe, date):
        self.fk_recipe = fk_recipe
        self.date = date
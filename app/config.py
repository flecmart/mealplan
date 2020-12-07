import os

user = os.environ['POSTGRES_USER']
password = os.environ['POSTGRESS_PASSWORD']
host = os.environ['POSTGRES_HOST']
database = os.environ['POSTGRES_DB']
port = os.environ['POSTGRES_PORT']

# for local testing
#user = 'test'
#password = 'password'
#host= 'postgress'
#port=5432
#database='example'

DATABASE_CONNECTION_URI = f'postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}'

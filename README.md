# mealplan

Custom Mealplanning and recipe management.

## Abstract

In our household we need an overview of our recipes and a calendar that we can plan our meals within the next week(s).

## Install

Dependencies:
  
- [docker & docker-compose](https://www.docker.com/get-started)  
- [GNU make](https://chocolatey.org/packages/make) (for debugging on a windows machine)

Clone the repository:

```
git clone https://github.com/flecmart/mealplan.git
```

Build and run with docker compose:

```
cd mealplan
docker-compose up -d
```

The app is now reachable at `localhost:5000`

## Development

https://trello.com/b/k5LUVCYC/mealplan

## Debug

To debug the app inside the container I used the great debug approach of [Adrien Cacciaguerra](https://blog.theodo.com/2020/05/debug-flask-vscode/). 

To debug the app:

1. run `make flaskdebug`
2. Press F5 to attach vscode

## Recreate DB

Just remove the volume with the following command:

`docker volume rm mealplan_db_volume`

Then restart the app.

## Backup and restore DB

Backup:

`docker exec mealplan_db /usr/bin/pg_dumpall -U postgres > backup.sql`

`docker exec mealplan_db /usr/bin/pg_dumpall -U postgres | gzip -9 > backup.sql.gz`

``docker exec -t your-db-container pg_dumpall -c -U postgres > dump_`date +%d-%m-%Y"_"%H_%M_%S`.sql``

Restore

`cat your_dump.sql | docker exec mealplan_db psql -U postgres`

## Inspiration

Some code and ideas are inspired by this project https://github.com/digitaljosh/meal-planner
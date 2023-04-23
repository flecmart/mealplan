# mealplan

Custom Mealplanning and recipe management.

## Abstract

In our household we need an overview of our recipes and a calendar that we can plan our meals within the next week(s).

## Install

Dependencies:
  
- [docker & docker-compose](https://www.docker.com/get-started)  
- [GNU make](https://chocolatey.org/packages/make) (for debugging on a windows machine)

1. Clone the repository:

```
git clone https://github.com/flecmart/mealplan.git
```

2. Create your `environment.conf` from `environment.conf.example`

3. Build and run with docker compose:

```
cd mealplan
docker-compose up -d
```

The app is now reachable at `localhost:5000`

## Features

### Manage recipes in a cookbook

![example image cookbook](https://user-images.githubusercontent.com/10167243/107639035-a8db1880-6c70-11eb-82d1-39bfcbb30c13.png)

- you can create & edit recipes with a dialog
- import recipes by pasting links from, e.g. [chefkoch.de](https://www.chefkoch.de/) (using https://pypi.org/project/recipe-scrapers/)

### Show recipes with ingredients and instructions

![example image recipe view](https://user-images.githubusercontent.com/10167243/107639121-c27c6000-6c70-11eb-86f9-ec461e699027.png)

### Assign recipes in a calendar to plan meals

Weekly View:

![example image planning week](https://user-images.githubusercontent.com/10167243/107637407-631d5080-6c6e-11eb-8364-1ab5a3e1f3e6.png)

Monthly View:

![example image planning month](https://user-images.githubusercontent.com/10167243/107637543-8fd16800-6c6e-11eb-86ed-01dc491564f8.png)

- calendar UI is pretty basic to potentially run the mealplan on an e-ink display (I plan to implement this in the future)
- use of symbols to represent meals in the calendar to make the plan readable for the smallest family members
- meals can be rescheduled with drag & drop

### Generate shopping list based on ingredients & export to [todoist](https://todoist.com/)

![example image shopping list](https://user-images.githubusercontent.com/10167243/107638049-58af8680-6c6f-11eb-820f-089468e8f55a.png)

- time range for shopping list selectable in UI
- mealplan tries to aggregate ingredients with natural language processing
- shopping list or certain ingredients can then be exported to [todoist](https://todoist.com/) and are therefore synced on your mobile device for the actual shopping

## Recreate DB

Just remove the volume with the following command:

`docker volume rm mealplan_db_volume`

Then restart the app.

## Backup and restore DB

Backup: https://github.com/prodrigestivill/docker-postgres-backup-local

Restore:

Replace the backupfile name, `$CONTAINER`, `$USERNAME` and `$DBNAME` from the following command:

`zcat backupfile.sql.gz | docker exec --tty --interactive $CONTAINER psql --username=$USERNAME --dbname=$DBNAME -W`

## Inspiration & Development

Some code and ideas, especially the html templates and the use of [fullcalendar.io](https://fullcalendar.io/) are inspired by this project: https://github.com/digitaljosh/meal-planner. The data models & routing were reimplemented to match our personal requirements. The user authentication system was dropped as I wanted to avoid to do the authentication myself and just run the app as a docker service locally, potentially exposing it with a reverse proxy. Also the use of the [spoonacular api](https://spoonacular.com/food-api) to import recipes was replaced by using https://pypi.org/project/recipe-scrapers/ to support multiple recipe websites & languages.
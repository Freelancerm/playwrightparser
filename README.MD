# 🧠 Brain.com.ua Product Parser Project
This project is a Django-based web application designed to parse product information from Brain.com.ua product pages. The application utilizes a combination of Django models, views, and utilities to download product page HTML, parse structured product information, and save the parsed data into a Django model. The project aims to provide a scalable and maintainable solution for product data extraction and management.

## 🚀 Features
* Product data parsing from Brain.com.ua product pages
* Data modeling using Django models
* Utility functions for HTML extraction and normalization
* Support for asynchronous and synchronous web application deployment
* Integration with Django framework for easy development and maintenance

## 🛠️ Tech Stack
* Django framework
* Python 3.x
* PostgreSQL database engine
* requests library for HTTP requests
* Playwright library for HTML parsing
* dataclasses library for data modeling
* pathlib library for file path manipulation
* django.urls for URL routing
* django.core.asgi and django.core.wsgi for ASGI and WSGI configuration

## 📦 Installation
To install the project, follow these steps:
1. Clone the repository using `git clone`
2. Install the required dependencies using `pip install -r requirements.txt`
3. Create a PostgreSQL database and update the database settings in `settings.py`
4. Or for simplify PostgreSQL run just use `docker compose up -d`
5. Set up the Django environment using `python manage.py makemigrations`
6. Complete migration `python manage.py migrate`
7. Change to your project directory in 'modules/load_django.py'
8. Run `python -m playwright install chromium`
9. Run the application using `python modules/1_get_info.py` to start the product parsing process

## 💻 Usage
To use the application, follow these steps:
1. Run the application using `python modules/1_get_info.py` to start the product parsing process

## 📂 Project Structure
```markdown
brainscomua_project/
    asgi.py
    settings.py
    urls.py
    wsgi.py
parser_app/
    models.py
    views.py
modules/
    1_get_info.py
    load_django.py
requirements.txt
manage.py
```


## 🤝 Contributing
To contribute to the project, please follow these steps:
1. Fork the repository using `git fork`
2. Make changes and commit them using `git commit`
3. Push the changes to the forked repository using `git push`
4. Create a pull request to merge the changes into the main repository

## 📝 License
The project is licensed under the MIT License.
import sys
import os
import django

sys.path.append("/home/m/atoms/brainscomua_project")
os.environ["DJANGO_SETTINGS_MODULE"] = "brainscomua_project.settings"
django.setup()

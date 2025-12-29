@echo off

uv run py manage.py makemigrations crm
uv run py manage.py makemigrations xomashyo

uv run py manage.py migrate


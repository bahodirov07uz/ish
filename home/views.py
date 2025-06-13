from django.shortcuts import render
from django.views.generic import TemplateView,ListView
from .models import Home
# Create your views here.


def home(request):
    return render(request, 'index.html')
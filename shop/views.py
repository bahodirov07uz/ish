from django.shortcuts import render
from django.views.generic import TemplateView
from crm.models import Product
class HomeView(TemplateView):
    template_name = "main/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.all()[:3]
        return context
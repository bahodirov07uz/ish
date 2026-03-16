# budget/urls.py
from django.urls import path
from . import views

app_name = 'budget'

urlpatterns = [
    path('',                        views.ByudjetListView.as_view(),      name='list'),
    path('yangi/',                  views.ByudjetCreateView.as_view(),    name='create'),
    path('<int:pk>/',               views.ByudjetDetailView.as_view(),    name='detail'),
    path('<int:pk>/tahrir/',        views.ByudjetUpdateView.as_view(),    name='update'),
    path('<int:pk>/limit/',         views.limit_qoshish,                  name='limit_add'),
    path('limit/<int:pk>/ochir/',   views.limit_ochirish,                 name='limit_delete'),
    path('tranzaksiyalar/',         views.TranzaksiyaListView.as_view(),  name='tranzaksiyalar'),
]
from django.urls import path
from . import views
from .views import noticias, noticia_detalhe, paineis

urlpatterns = [
    path('home2/', views.home2, name='home2'),
    path('agendamento/', views.agendamento, name='agendamento'), 
    path('noticias/', noticias, name='noticias'),
    path('noticias/<int:noticia_id>/', noticia_detalhe, name='noticia_detalhe'),
    path('paineis/', paineis, name='paineis'),
]
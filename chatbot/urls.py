from django.urls import path
from .views import chatbot, ask_chatbot

urlpatterns = [
    path('', chatbot, name='chatbot'),
    path('ask/', ask_chatbot, name='ask_chatbot'),
]
# accounts/admin.py
from django.contrib import admin
from .models import UserProfile

class UserProfileAdmin(admin.ModelAdmin):
    # Campos a serem exibidos na lista principal de perfis
    list_display = ('user', 'funcao', 'cargo', 'genero', 'telefone')
    # Campos para pesquisa e filtros
    search_fields = ('user__username', 'cargo', 'funcao')
    list_filter = ('genero', 'funcao')

# Registrar o modelo personalizado no Admin
admin.site.register(UserProfile, UserProfileAdmin)
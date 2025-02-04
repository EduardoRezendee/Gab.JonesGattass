from django.contrib import admin
from .models import Noticia, BoasPraticas, Painel, AcessoRapido

@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'data_publicacao', 'tempo_leitura')
    search_fields = ('titulo',)
    list_filter = ('data_publicacao',)
    ordering = ('-data_publicacao',)

@admin.register(BoasPraticas)
class BoasPraticasAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'data_publicacao', 'tempo_leitura')
    search_fields = ('titulo',)
    list_filter = ('data_publicacao',)
    ordering = ('-data_publicacao',)

@admin.register(Painel)
class PainelAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'descricao')
    search_fields = ('titulo',)
    ordering = ('titulo',)

@admin.register(AcessoRapido)
class AcessoRapidoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'link', 'imagem')
    search_fields = ('titulo',)
    ordering = ('titulo',)

from django.contrib import admin
from .models import Banner

@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'ativo')
    search_fields = ('titulo',)
    list_filter = ('ativo',)

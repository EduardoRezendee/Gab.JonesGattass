from django.contrib import admin
from .models import BaseConhecimento, ModelosDecisoes, DocumentoProcesso, PromptConfig

# Registro dos modelos no admin
@admin.register(BaseConhecimento)
class BaseConhecimentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "arquivo")  # Campos exibidos na lista
    search_fields = ("nome",)  # Campos pesquisáveis
    list_filter = ("nome",)  # Filtros laterais

@admin.register(ModelosDecisoes)
class ModelosDecisoesAdmin(admin.ModelAdmin):
    list_display = ("nome", "arquivo", "data_upload")  # Campos exibidos na lista
    search_fields = ("nome",)  # Campos pesquisáveis
    list_filter = ("data_upload",)  # Filtros laterais

@admin.register(DocumentoProcesso)
class DocumentoProcessoAdmin(admin.ModelAdmin):
    list_display = ("arquivo",)  # Campos exibidos na lista
    search_fields = ("arquivo",)  # Campos pesquisáveis

@admin.register(PromptConfig)
class PromptConfigAdmin(admin.ModelAdmin):
    list_display = ("texto",)  # Campos exibidos na lista
    search_fields = ("texto",)  # Campos pesquisáveis
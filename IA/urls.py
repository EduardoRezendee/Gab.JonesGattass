from django.urls import path
from .views import (
    painel_ia, editar_prompt, assistente_juridico,
    upload_base_conhecimento, upload_modelos, ask_assistente_juridico,
    deletar_base_conhecimento  # Importe a view de deletar
)

urlpatterns = [
    path("painel-ia/", painel_ia, name="painel_ia"),
    path("configurar-prompt/", editar_prompt, name="editar_prompt"),
    path("assistente-juridico/", assistente_juridico, name="assistente_juridico"),
    path("assistente-juridico/ask/", ask_assistente_juridico, name="ask_assistente_juridico"),
    path("upload/base/", upload_base_conhecimento, name="upload_base"),
    path("upload/modelos/", upload_modelos, name="upload_modelos"),
    path("deletar-base/<int:doc_id>/", deletar_base_conhecimento, name="deletar_base"),  # URL para deletar
]
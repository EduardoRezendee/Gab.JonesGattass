from django.urls import path
from .views import (
    ProcessoListView, ProcessoCreateView, ProcessoUpdateView, ProcessoDeleteView,
    AndamentoListView, AndamentoCreateView, AndamentoUpdateView, AndamentoDeleteView, ProcessoDetailView, AndamentoIniciarView, AndamentoEnviarParaFaseView, AndamentoConcluirProcessoView
, process_metrics_view, adicionar_tarefa, remover_tarefa, export_processos_xlsx, adicionar_comentario, ProcessoPartialUpdateView, configurar_meta_semanal, adicionar_processo_meta, remover_processo_meta)
from . import views
from .views import importar_processos_view

urlpatterns = [
    # URLs para Processo
    path('processos/', ProcessoListView.as_view(), name='processo_list'),
    path('processos/novo/', ProcessoCreateView.as_view(), name='processo_create'),
    path('processos/<int:pk>/', ProcessoDetailView.as_view(), name='processo_detail'),
    path('processos/<int:pk>/editar/', ProcessoUpdateView.as_view(), name='processo_update'),
    path('processos/<int:pk>/deletar/', ProcessoDeleteView.as_view(), name='processo_delete'),
    path('processo/update/<int:processo_id>/', ProcessoPartialUpdateView.as_view(), name='processo_partial_update'),

    # URLs para Andamento
    path('andamentos/', AndamentoListView.as_view(), name='andamento_list'),
    path('andamentos/novo/', AndamentoCreateView.as_view(), name='andamento_create'),
    path('andamentos/<int:pk>/editar/', AndamentoUpdateView.as_view(), name='andamento_update'),
    path('andamentos/<int:pk>/deletar/', AndamentoDeleteView.as_view(), name='andamento_delete'),

    path('andamentos/<int:pk>/iniciar/', AndamentoIniciarView.as_view(), name='andamento_iniciar'),
    path('andamentos/<int:pk>/enviar/', AndamentoEnviarParaFaseView.as_view(), name='andamento_enviar'),
    path('andamentos/<int:pk>/concluir/', AndamentoConcluirProcessoView.as_view(), name='andamento_concluir'),
    path('definir-tema/<int:pk>/', views.definir_tema, name='definir_tema'),

    path('metrics/', process_metrics_view, name='process_metrics'),

    path('adicionar-tarefa/<int:processo_id>/', adicionar_tarefa, name='adicionar_tarefa'),
    path('remover-tarefa/<int:processo_id>/', remover_tarefa, name='remover_tarefa'),

    path('exportar-excel/', export_processos_xlsx, name='exportar_excel'),

    path("adicionar-comentario/<int:processo_id>/", adicionar_comentario, name="adicionar_comentario"),
    path('api/v1/processos/', views.ProcessosCreateListAPIView.as_view(), name='processos-create-list-api-view'),
    path('importar-processos/', importar_processos_view, name='importar_processos'),
    
    path('metas-semanais/', views.listar_metas_semanal, name='listar_metas_semanal'),
    path('api/meta-detalhes/', views.api_meta_detalhes, name='api_meta_detalhes'),
    path('api/meta-processos/', views.api_meta_processos, name='api_meta_processos'),
    path('exportar-metas/', views.exportar_metas_relatorio, name='exportar_metas'),
    path('minhas-metas/', views.minhas_metas, name='minhas_metas'),
    path('ver-processos-meta/', views.ver_todos_processos_meta, name='ver_todos_processos_meta'),
    path('api/detalhes-meta/', views.api_detalhes_meta, name='api_detalhes_meta'),
    path('editar-meta-semanal/', views.editar_meta_semanal, name='editar_meta_semanal'),
    path('excluir-meta-semanal/', views.excluir_meta_semanal, name='excluir_meta_semanal'),
    path('processo/<int:processo_id>/adicionar-meta/', views.adicionar_processo_meta, name='adicionar_processo_meta'),
    path('processo/<int:processo_id>/remover-meta/', views.remover_processo_meta, name='remover_processo_meta'),
    path('meta-semanal/status/', views.status_meta_semanal, name='status_meta_semanal'),
    path('configurar-meta-semanal/', configurar_meta_semanal, name='configurar_meta_semanal'),
    path('excluir-comentario/<int:comentario_id>/', views.excluir_comentario, name='excluir_comentario'),

# ── Processos em Pauta ──────────────────────────────────────────
    path('pauta/importar/', views.importar_pauta, name='importar_pauta'),
    path('pauta/adicionar-manual/', views.adicionar_pauta_manual, name='adicionar_pauta_manual'),
    path('pauta/json/', views.pauta_json, name='pauta_json'),
    path('pauta/limpar/', views.limpar_pauta, name='limpar_pauta'),
    path('pauta/remover/<int:item_id>/', views.remover_pauta_item, name='remover_pauta_item'),
    path('pauta/alterar-tipo/<int:item_id>/', views.alterar_tipo_sessao_pauta, name='alterar_tipo_sessao_pauta'),
    path('pauta/editar/<int:item_id>/', views.editar_pauta_item, name='editar_pauta_item'),

    # ── Quadro de Avisos ──────────────────────────────────────────
    path('avisos/', views.avisos_lista, name='avisos_lista'),
    path('avisos/<int:pk>/', views.aviso_detalhe, name='aviso_detalhe'),
    path('avisos/salvar/', views.aviso_salvar, name='aviso_salvar'),
    path('avisos/<int:pk>/deletar/', views.aviso_deletar, name='aviso_deletar'),
]

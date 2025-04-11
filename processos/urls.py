from django.urls import path
from .views import (
    ProcessoListView, ProcessoCreateView, ProcessoUpdateView, ProcessoDeleteView,
    AndamentoListView, AndamentoCreateView, AndamentoUpdateView, AndamentoDeleteView, ProcessoDetailView, AndamentoIniciarView, AndamentoEnviarParaFaseView, AndamentoConcluirProcessoView
, process_metrics_view, adicionar_tarefa, remover_tarefa, export_processos_xlsx, adicionar_comentario, ProcessoPartialUpdateView)
from . import views

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

]

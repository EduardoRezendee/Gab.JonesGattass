from django.contrib import admin
from .models import (
    Resultado, Tipo, Camara, Fase, Especie, Status,
    Processo, ProcessoAndamento, HistoricoAndamento, Tema,
    Ferias, Plantao, NotificacaoInterna,
)



@admin.register(Tema)
class TemaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo', 'dt_criacao', 'dt_atualizacao')
    search_fields = ('nome', 'descricao')
    list_filter = ('ativo',)
# Configuração para modelos simples
@admin.register(Resultado)
class ResultadoAdmin(admin.ModelAdmin):
    list_display = ('resultado', 'dt_criacao', 'dt_atualizacao')
    search_fields = ('resultado',)


@admin.register(Tipo)
class TipoAdmin(admin.ModelAdmin):
    list_display = ('tipo', 'dt_criacao', 'dt_atualizacao')
    search_fields = ('tipo',)


@admin.register(Camara)
class CamaraAdmin(admin.ModelAdmin):
    list_display = ('camara', 'dt_criacao', 'dt_atualizacao')
    search_fields = ('camara',)


@admin.register(Fase)
class FaseAdmin(admin.ModelAdmin):
    list_display = ('fase', 'dt_criacao', 'dt_atualizacao')
    search_fields = ('fase',)


@admin.register(Especie)
class EspecieAdmin(admin.ModelAdmin):
    list_display = ('especie', 'sigla', 'dt_criacao', 'dt_atualizacao')
    search_fields = ('especie', 'sigla')


@admin.register(Status)
class StatusAdmin(admin.ModelAdmin):
    list_display = ('status', 'dt_criacao', 'dt_atualizacao')
    search_fields = ('status',)


# Configuração para o modelo Processo
@admin.register(Processo)
class ProcessoAdmin(admin.ModelAdmin):
    list_display = (
        'numero_processo', 'especie', 'tipo', 'camara', 'usuario', 'dt_julgamento', 'dt_prazo', 'concluido'
    )
    list_filter = ('concluido', 'tipo', 'camara')
    search_fields = ('numero_processo',)
    date_hierarchy = 'dt_criacao'


# Configuração para o modelo Andamento
@admin.register(ProcessoAndamento)
class AndamentoAdmin(admin.ModelAdmin):
    list_display = ('processo', 'andamento', 'fase', 'usuario', 'dt_inicio', 'dt_conclusao', 'dt_criacao')
    list_filter = ('fase', 'usuario')
    search_fields = ('processo__numero_processo', 'andamento')
    date_hierarchy = 'dt_criacao'


# Configuração para o modelo HistoricoAndamento
@admin.register(HistoricoAndamento)
class HistoricoAndamentoAdmin(admin.ModelAdmin):
    list_display = ('andamento', 'fase_anterior', 'fase_atual', 'dt_transicao', 'usuario')
    list_filter = ('fase_anterior', 'fase_atual', 'usuario')
    search_fields = ('andamento__processo__numero_processo',)


# ──────────────────────────────────────────────────────────────────
#  MÓDULO: GESTÃO DE FÉRIAS E PLANTÕES
# ──────────────────────────────────────────────────────────────────

@admin.register(Ferias)
class FeriasAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'data_inicio', 'data_fim', 'status', 'criado_por', 'criado_em')
    list_filter = ('status',)
    search_fields = ('usuario__first_name', 'usuario__last_name')
    date_hierarchy = 'data_inicio'
    raw_id_fields = ('usuario', 'criado_por')


@admin.register(Plantao)
class PlantaoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'data_inicio', 'data_fim', 'status', 'criado_por', 'criado_em')
    list_filter = ('status',)
    search_fields = ('usuario__first_name', 'usuario__last_name')
    date_hierarchy = 'data_inicio'
    raw_id_fields = ('usuario', 'criado_por')


@admin.register(NotificacaoInterna)
class NotificacaoInternaAdmin(admin.ModelAdmin):
    list_display = ('destinatario', 'tipo', 'titulo', 'lida', 'criado_em')
    list_filter = ('tipo', 'lida')
    search_fields = ('destinatario__first_name', 'destinatario__last_name', 'titulo')
    date_hierarchy = 'criado_em'
    raw_id_fields = ('destinatario',)

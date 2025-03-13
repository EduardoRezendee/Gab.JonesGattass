from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

# MODELS
from processos.models import Processo, TarefaDoDia, ComentarioProcesso, ProcessoAndamento
from accounts.models import UserProfile
from django.db.models import Count
# MÉTRICAS E GAMIFICAÇÃO (exemplos, ajuste se seus imports forem diferentes)
from .metrics import (
    get_process_metrics,
    get_process_gamification_metrics,
    get_top_users_by_xp,
    get_pending_and_concluded_by_assessor,         # <- Funções de exemplo
    get_daily_entries_and_exits_by_assessor
)

# IMPORTAMOS BIBLIOTECAS DO PLOTLY
import plotly.offline as pyo
import plotly.graph_objs as go


@login_required(login_url='login')
def home(request):
    user = request.user

    # Verificar roles do usuário
    is_revisor = UserProfile.objects.filter(user=user, funcao="revisor(a)").exists()
    is_desembargadora = UserProfile.objects.filter(user=user, funcao="Desembargadora").exists()
    is_chefe = UserProfile.objects.filter(user=user, funcao="Chefe de Gabinete").exists()
    is_assessor = UserProfile.objects.filter(user=user, funcao="Assessor(a)").exists()

    # Inicializar variáveis
    andamento_metrics = []
    plot_div_pc = None
    plot_div_es = None
    plot_div_revisoes_hoje = None
    plot_div_fases = None
    plot_div_es_assessor_hoje = None
    plot_div_especies = None
    active_tab = None
    fases = None

    # Data atual para cálculos diários
    hoje = timezone.now().date()

    # Função auxiliar para gerar gráficos gerais
    def generate_performance_charts():
        data_list = get_pending_and_concluded_by_assessor()
        if data_list:
            assessores = [item['assessor'] for item in data_list]
            pendentes = [item['pendentes'] for item in data_list]
            concluidos = [item['concluidos'] for item in data_list]
            trace_pend = go.Bar(x=assessores, y=pendentes, name='Pendentes', marker_color='#EF4444')
            trace_conc = go.Bar(x=assessores, y=concluidos, name='Concluídos', marker_color='#10B981')
            layout_pc = go.Layout(
                title='Pendentes vs. Concluídos por Assessor',
                xaxis=dict(title='Assessor', tickangle=-45),
                yaxis=dict(title='Quantidade'),
                barmode='group',
                template='plotly_white',
                height=400
            )
            fig_pc = go.Figure(data=[trace_pend, trace_conc], layout=layout_pc)
            plot_div_pc = pyo.plot(fig_pc, auto_open=False, output_type='div')
        else:
            plot_div_pc = "<p class='text-muted text-center'>Nenhum dado disponível para Pendentes x Concluídos.</p>"

        es_data = get_daily_entries_and_exits_by_assessor()
        if es_data['dias']:
            dias = [d.strftime("%d/%m/%Y") for d in es_data['dias']]
            entradas_totais = [sum(es_data['entradas'].get((u, d), 0) for u in es_data['assessores']) for d in es_data['dias']]
            saidas_totais = [sum(es_data['saidas'].get((u, d), 0) for u in es_data['assessores']) for d in es_data['dias']]
            trace_ent = go.Bar(x=dias, y=entradas_totais, name='Entradas', marker_color='#3B82F6')
            trace_sai = go.Bar(x=dias, y=saidas_totais, name='Saídas', marker_color='#F59E0B')
            layout_es = go.Layout(
                title='Entradas vs. Saídas (Últimos 7 Dias)',
                xaxis=dict(title='Data', tickangle=-45),
                yaxis=dict(title='Quantidade'),
                barmode='group',
                template='plotly_white',
                height=400
            )
            fig_es = go.Figure(data=[trace_ent, trace_sai], layout=layout_es)
            plot_div_es = pyo.plot(fig_es, auto_open=False, output_type='div')
        else:
            plot_div_es = "<p class='text-muted text-center'>Nenhum dado disponível para Entradas x Saídas.</p>"

        return plot_div_pc, plot_div_es

    # Métricas diárias
    revisoes_hoje = ProcessoAndamento.objects.filter(
        fase__fase__in=["Revisão", "Revisão Desa"],
        dt_criacao__date=hoje
    ).values('processo').distinct().count()

    concluidos_revisao_hoje = ProcessoAndamento.objects.filter(
        fase__fase__in=["Revisão", "Revisão Desa"],
        dt_conclusao__date=hoje,
        status__status="Concluído"
    ).values('processo').distinct().count()

    # Gráfico de Revisões Hoje
    trace_revisoes_hoje = go.Bar(
        x=["Colocados em Revisão", "Concluídos Revisão"],
        y=[revisoes_hoje, concluidos_revisao_hoje],
        marker_color=['#3B82F6', '#10B981'],
        text=[revisoes_hoje, concluidos_revisao_hoje],
        textposition='auto'
    )
    layout_revisoes_hoje = go.Layout(
        title=f'Revisões Hoje ({hoje.strftime("%d/%m/%Y")})',
        yaxis=dict(title='Quantidade'),
        barmode='group',
        template='plotly_white',
        height=300
    )
    fig_revisoes_hoje = go.Figure(data=[trace_revisoes_hoje], layout=layout_revisoes_hoje)
    plot_div_revisoes_hoje = pyo.plot(fig_revisoes_hoje, auto_open=False, output_type='div')

    # Métricas gerais
    total_pendentes = Processo.objects.filter(concluido=False).count()
    processos_por_fase = (
        ProcessoAndamento.objects.filter(
            processo__concluido=False,
            status__status__in=["Não iniciado", "Em andamento"]
        )
        .values('fase__fase')
        .annotate(quantidade=Count('processo', distinct=True))
        .order_by('fase__fase')
    )

    # Gráfico de Total Pendentes e Por Fase
    fases_nomes = [f['fase__fase'] for f in processos_por_fase]
    fases_quantidades = [f['quantidade'] for f in processos_por_fase]
    trace_fases = go.Bar(
        x=fases_nomes,
        y=fases_quantidades,
        name='Por Fase',
        marker_color='#3B82F6',
        text=fases_quantidades,
        textposition='auto'
    )
    trace_total = go.Bar(
        x=['Total Pendentes'],
        y=[total_pendentes],
        name='Total Pendentes',
        marker_color='#EF4444',
        text=[total_pendentes],
        textposition='auto'
    )
    layout_fases = go.Layout(
        title='Total de Processos Pendentes e Por Fase',
        yaxis=dict(title='Quantidade'),
        barmode='group',
        template='plotly_white',
        height=400
    )
    fig_fases = go.Figure(data=[trace_fases, trace_total], layout=layout_fases)
    plot_div_fases = pyo.plot(fig_fases, auto_open=False, output_type='div')

    # Gráfico: Entradas e Saídas por Assessor Hoje (Corrigido)
    entradas_hoje = (
        Processo.objects.filter(data_dist__date=hoje)
        .values('usuario__first_name', 'usuario__last_name')  # Corrigido: removido 'userprofile'
        .annotate(quantidade=Count('id'))
    )
    saidas_hoje = (
        Processo.objects.filter(dt_conclusao__date=hoje, concluido=True)
        .values('usuario__first_name', 'usuario__last_name')  # Corrigido: removido 'userprofile'
        .annotate(quantidade=Count('id'))
    )
    assessores = UserProfile.objects.filter(funcao="Assessor(a)").select_related('user')
    assessores_nomes = [f"{a.user.first_name} {a.user.last_name}" for a in assessores]
    entradas_dict = {f"{e['usuario__first_name']} {e['usuario__last_name']}": e['quantidade'] for e in entradas_hoje}
    saidas_dict = {f"{s['usuario__first_name']} {s['usuario__last_name']}": s['quantidade'] for s in saidas_hoje}
    entradas_vals = [entradas_dict.get(nome, 0) for nome in assessores_nomes]
    saidas_vals = [saidas_dict.get(nome, 0) for nome in assessores_nomes]

    trace_ent_assessor = go.Bar(
        x=assessores_nomes,
        y=entradas_vals,
        name='Entradas',
        marker_color='#3B82F6',
        text=entradas_vals,
        textposition='auto'
    )
    trace_sai_assessor = go.Bar(
        x=assessores_nomes,
        y=saidas_vals,
        name='Saídas',
        marker_color='#F59E0B',
        text=saidas_vals,
        textposition='auto'
    )
    layout_es_assessor = go.Layout(
        title=f'Entradas e Saídas por Assessor Hoje ({hoje.strftime("%d/%m/%Y")})',
        xaxis=dict(title='Assessor', tickangle=-45),
        yaxis=dict(title='Quantidade'),
        barmode='group',
        template='plotly_white',
        height=400
    )
    fig_es_assessor = go.Figure(data=[trace_ent_assessor, trace_sai_assessor], layout=layout_es_assessor)
    plot_div_es_assessor_hoje = pyo.plot(fig_es_assessor, auto_open=False, output_type='div')

    # Gráfico: Quantidade de Processos por Espécie
    processos_por_especie = (
        Processo.objects.filter(concluido=False)
        .values('especie__especie')
        .annotate(quantidade=Count('id'))
        .order_by('especie__especie')
    )
    especies_nomes = [e['especie__especie'] if e['especie__especie'] else "Sem Espécie" for e in processos_por_especie]
    especies_quantidades = [e['quantidade'] for e in processos_por_especie]
    trace_especies = go.Bar(
        x=especies_nomes,
        y=especies_quantidades,
        marker_color='#10B981',
        text=especies_quantidades,
        textposition='auto'
    )
    layout_especies = go.Layout(
        title='Quantidade de Processos Pendentes por Espécie',
        xaxis=dict(title='Espécie', tickangle=-45),
        yaxis=dict(title='Quantidade'),
        template='plotly_white',
        height=400
    )
    fig_especies = go.Figure(data=[trace_especies], layout=layout_especies)
    plot_div_especies = pyo.plot(fig_especies, auto_open=False, output_type='div')

    # 1) VISÃO DO REVISOR(A)
    if is_revisor:
        numero_processo = request.GET.get('numero_processo', '').strip()
        processos_em_revisao = Processo.objects.filter(
            andamentos__fase__fase="Revisão",
            andamentos__usuario=user,
            concluido=False
        ).distinct().select_related('especie', 'usuario')
        if numero_processo:
            processos_em_revisao = processos_em_revisao.filter(numero_processo__icontains=numero_processo)
        for processo in processos_em_revisao:
            ultimo_andamento = processo.andamentos.filter(
                fase__fase="Revisão",
                usuario=user,
                status__status__in=["Não iniciado", "Em andamento"]
            ).order_by('-dt_criacao').first()
            if ultimo_andamento:
                especie_nome = processo.especie.especie if processo.especie else "Sem espécie"
                comentarios = ComentarioProcesso.objects.filter(processo=processo).select_related('usuario')
                andamento_metrics.append({
                    'pk': ultimo_andamento.pk,
                    'processo_pk': processo.pk,
                    'numero_processo': processo.numero_processo,
                    'data_dist': processo.data_dist,
                    'dias_no_gabinete': processo.dias_no_gabinete() or 0,
                    'fase': ultimo_andamento.fase.fase if ultimo_andamento else "Sem fase",
                    'descricao': ultimo_andamento.andamento if ultimo_andamento else "Sem descrição",
                    'status': ultimo_andamento.status.status if ultimo_andamento and ultimo_andamento.status else "Sem status",
                    'data_inicio': ultimo_andamento.dt_inicio if ultimo_andamento else None,
                    'data_conclusao': ultimo_andamento.dt_conclusao if ultimo_andamento else None,
                    'link_doc': ultimo_andamento.link_doc if ultimo_andamento else None,
                    'usuario_processo': processo.usuario.get_full_name() if processo.usuario else "Não atribuído",
                    'especie': especie_nome,
                    'sigla_especie': processo.especie.sigla if processo.especie else "",
                    'data_envio_revisao': ultimo_andamento.dt_criacao,
                    'comentarios': [{'texto': c.texto, 'data_criacao': c.data_criacao, 'usuario': c.usuario.get_full_name()} for c in comentarios]
                })
        andamento_metrics.sort(key=lambda p: (0 if p['especie'] == "Liminar" else 1, p['data_dist']))

    # 2) VISÃO DA DESEMBARGADORA
    elif is_desembargadora:
        numero_processo = request.GET.get('numero_processo', '').strip()
        processos_em_revisao_desa = Processo.objects.filter(
            andamentos__fase__fase="Revisão Desa",
            andamentos__usuario=user,
            concluido=False
        ).distinct().select_related('especie', 'usuario')
        if numero_processo:
            processos_em_revisao_desa = processos_em_revisao_desa.filter(numero_processo__icontains=numero_processo)
        for processo in processos_em_revisao_desa:
            ultimo_andamento = processo.andamentos.filter(
                fase__fase="Revisão Desa",
                usuario=user,
                status__status__in=["Não iniciado", "Em andamento"]
            ).order_by('-dt_criacao').first()
            if ultimo_andamento:
                especie_nome = processo.especie.especie if processo.especie else "Sem espécie"
                comentarios = ComentarioProcesso.objects.filter(processo=processo).select_related('usuario')
                revisoes_desa_count = processo.andamentos.filter(fase__fase="Revisão Desa").count()
                andamento_metrics.append({
                    'pk': ultimo_andamento.pk,
                    'processo_pk': processo.pk,
                    'numero_processo': processo.numero_processo,
                    'data_dist': processo.data_dist,
                    'dias_no_gabinete': processo.dias_no_gabinete() or 0,
                    'fase': ultimo_andamento.fase.fase if ultimo_andamento else "Sem fase",
                    'descricao': ultimo_andamento.andamento if ultimo_andamento else "Sem descrição",
                    'status': ultimo_andamento.status.status if ultimo_andamento and ultimo_andamento.status else "Sem status",
                    'data_inicio': ultimo_andamento.dt_inicio if ultimo_andamento else None,
                    'data_conclusao': ultimo_andamento.dt_conclusao if ultimo_andamento else None,
                    'link_doc': ultimo_andamento.link_doc if ultimo_andamento else None,
                    'usuario_processo': processo.usuario.get_full_name() if processo.usuario else "Não atribuído",
                    'especie': especie_nome,
                    'sigla_especie': processo.especie.sigla if processo.especie else "",
                    'comentarios': [{'texto': c.texto, 'data_criacao': c.data_criacao, 'usuario': c.usuario.get_full_name()} for c in comentarios],
                    'revisoes_desa': revisoes_desa_count
                })
        andamento_metrics.sort(key=lambda p: (0 if p['especie'] == "Liminar" else 1, -(p['dias_no_gabinete'] or 0)))
        plot_div_pc, plot_div_es = generate_performance_charts()

    # 3) VISÃO DO CHEFE DE GABINETE
    elif is_chefe:
        processos_pendentes = Processo.objects.filter(concluido=False).count()
        processos_concluidos = Processo.objects.filter(concluido=True).count()
        andamento_metrics.append({
            'info': "Visão do Chefe de Gabinete",
            'processos_pendentes': processos_pendentes,
            'processos_concluidos': processos_concluidos
        })
        plot_div_pc, plot_div_es = generate_performance_charts()

    # 4) VISÃO DO ASSESSOR/USUÁRIO COMUM
    else:
        numero_processo = request.GET.get('numero_processo', '').strip()
        processos_nao_concluidos = Processo.objects.filter(
            usuario=user,
            concluido=False
        ).select_related('especie', 'usuario')
        if numero_processo:
            processos_nao_concluidos = processos_nao_concluidos.filter(numero_processo__icontains=numero_processo)
        processos_detalhados = []
        for processo in processos_nao_concluidos:
            ultimo_andamento = processo.andamentos.order_by('-dt_criacao').first()
            if ultimo_andamento:
                processos_detalhados.append({
                    'pk': processo.pk,
                    'andamento_pk': ultimo_andamento.pk,
                    'andamento_link_doc': ultimo_andamento.link_doc if ultimo_andamento else None,
                    'numero_processo': processo.numero_processo,
                    'especie': processo.especie.especie if processo.especie else "Sem espécie",
                    'sigla': processo.especie.sigla if processo.especie else "Sem sigla",
                    'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento.fase else "Sem fase",
                    'status_atual': ultimo_andamento.status.status if ultimo_andamento.status else "Sem status",
                    'data_prazo': processo.dt_prazo,
                    'data_dist': processo.data_dist,
                    'dias_no_gabinete': processo.dias_no_gabinete() or 0,
                    'usuario_processo': processo.usuario.get_full_name() if processo.usuario else "Não atribuído",
                    'comentarios': ComentarioProcesso.objects.filter(processo=processo).values(
                        'texto', 'data_criacao', 'usuario__first_name', 'usuario__last_name'
                    )
                })
        processos_detalhados.sort(key=lambda p: (0 if p['especie'] == "Liminar" else 1, -(p['dias_no_gabinete'] or 0)))

        fixed_phase_order = ['Elaboração', 'Revisão', 'Correção', 'Revisão Desa', 'Devolvido', 'L. PJE']
        phase_dict = {}
        for processo in processos_detalhados:
            phase_dict.setdefault(processo['fase_atual'], []).append(processo)
        fases = [(phase, phase_dict.get(phase, [])) for phase in fixed_phase_order if phase in phase_dict]
        fase_param = request.GET.get('fase', None)
        if fase_param and fase_param in fixed_phase_order and fase_param in phase_dict:
            active_tab = fase_param
        elif fases:
            active_tab = fases[0][0]
        if is_assessor:
            plot_div_pc, plot_div_es = generate_performance_charts()

    # Tarefas do Dia
    tarefas_do_dia = TarefaDoDia.objects.filter(usuario=user).select_related('processo')
    tarefas_detalhadas = []
    for tarefa in tarefas_do_dia:
        ultimo_andamento = tarefa.processo.andamentos.order_by('-dt_criacao').first() if tarefa.processo else None
        tarefa_dict = {
            'id': tarefa.id,
            'processo': {
                'id': tarefa.processo.id if tarefa.processo else None,
                'numero_processo': tarefa.processo.numero_processo if tarefa.processo else "Sem número",
                'especie': tarefa.processo.especie.especie if tarefa.processo and tarefa.processo.especie else "Sem espécie",
                'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else "Sem fase",
                'data_dist': tarefa.processo.data_dist if tarefa.processo else None,
                'dias_no_gabinete': tarefa.processo.dias_no_gabinete() if tarefa.processo else 0,
                'dt_prazo': tarefa.processo.dt_prazo if tarefa.processo else None,
                'andamento_pk': ultimo_andamento.pk if ultimo_andamento else None,
                'andamento_link_doc': ultimo_andamento.link_doc if ultimo_andamento else None,
                'andamento': ultimo_andamento,
                'comentarios': ComentarioProcesso.objects.filter(processo=tarefa.processo).select_related('usuario') if tarefa.processo else []
            }
        }
        tarefas_detalhadas.append(tarefa_dict)
    tarefas_ids = [tarefa['processo']['id'] for tarefa in tarefas_detalhadas if tarefa['processo']['id']]

    # Métricas e Gamificação
    process_metrics = get_process_metrics(user)
    if not (is_revisor or is_desembargadora or is_chefe):
        process_metrics['detalhes_processos'] = processos_detalhados

    photo_url = user.profile.photo.url if hasattr(user, 'profile') and user.profile.photo else '/static/default-profile.png'
    process_gamification = get_process_gamification_metrics(user)
    top_users = get_top_users_by_xp()

    # Contexto
    context = {
        'user': user,
        'is_revisor': is_revisor,
        'is_desembargadora': is_desembargadora,
        'is_chefe': is_chefe,
        'is_assessor': is_assessor,
        'andamento_metrics': andamento_metrics,
        'plot_div_pc': plot_div_pc,
        'plot_div_es': plot_div_es,
        'plot_div_revisoes_hoje': plot_div_revisoes_hoje,
        'plot_div_fases': plot_div_fases,
        'plot_div_es_assessor_hoje': plot_div_es_assessor_hoje,
        'plot_div_especies': plot_div_especies,
        'process_metrics': process_metrics,
        'process_gamification': process_gamification,
        'top_users': top_users,
        'photo_url': photo_url,
        'tarefas_ids': tarefas_ids,
        'tarefas_do_dia': tarefas_detalhadas,
        'fases': fases,
        'active_tab': active_tab,
        'today': hoje,
        'revisoes_hoje': revisoes_hoje,
        'concluidos_revisao_hoje': concluidos_revisao_hoje,
        'total_pendentes': total_pendentes,
        'processos_por_fase': processos_por_fase,
    }

    return render(request, 'home.html', context)
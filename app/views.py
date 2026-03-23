
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import JsonResponse
from django.db.models.functions import Left
# MODELS
from processos.models import Processo, TarefaDoDia, ComentarioProcesso, ProcessoAndamento, Tema, Tipo
from accounts.models import UserProfile
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Count
from datetime import datetime, timedelta, timezone as dt_timezone
from processos.models import ProcessoAndamento, User
from django.db.models import F, ExpressionWrapper, DateField, DurationField, IntegerField, CharField, Value, Max
from django.db.models.functions import Cast
from collections import defaultdict
from processos.models import ProcessoAndamento


def home3(request):
    return render(request, 'home3.html')
# MÉTRICAS E GAMIFICAÇÃO
from .metrics import (
    get_process_metrics,
    get_process_gamification_metrics,
    get_top_users_by_xp,
    get_pending_and_concluded_by_assessor,
    get_daily_entries_and_exits_by_assessor,
    get_user_daily_productivity,
    get_user_weekly_productivity,
    get_user_meta_semanal_metrics
)

@login_required(login_url='login')
def home(request):
    user = request.user
    
    atrasados_por_assessor_detalhado: list[dict] = []
    total_atrasados: int = 0

    # Verificar roles do usuário (cache simples)
    cache_key_roles = f'user_roles_{user.id}'
    roles = cache.get(cache_key_roles)
    if not roles:
        roles = {
            'is_revisor': UserProfile.objects.filter(user=user, funcao="revisor(a)").exists(),
            'is_desembargador': UserProfile.objects.filter(user=user, funcao="Desembargador").exists(),
            'is_chefe': UserProfile.objects.filter(user=user, funcao="Chefe de Gabinete").exists(),
            'is_assessor': UserProfile.objects.filter(user=user, funcao="Assessor(a)").exists(),
        }
        cache.set(cache_key_roles, roles, timeout=3600)

    is_revisor = roles['is_revisor']
    is_desembargador = roles['is_desembargador']
    is_chefe = roles['is_chefe']
    is_assessor = roles['is_assessor']

    # Inicializar variáveis
    andamento_metrics = []
    numero_de_processos_em_revisao = 0
    numero_de_processos_em_revisao_des = 0
    active_tab = None
    fases = None
    hoje = timezone.now()
    processos_nao_concluidos = Processo.objects.none()
    processos_detalhados = []  # Inicializar aqui para evitar UnboundLocalError
    processos_antigos_detalhados = []
    processos_liminares_detalhados = []
    processos_concluidos_detalhados = []
    processos_revisao_des_detalhados = []
    tarefas_detalhadas = []
    tarefas_ids = []
    numero_de_processos_em_revisao_des = 0


    # Métricas diárias
    revisoes_hoje = ProcessoAndamento.objects.filter(
        fase__fase__in=["Revisão", "Revisão Des"],
        dt_criacao__date=hoje.date()
    ).values('processo').distinct().count()

    concluidos_revisao_hoje = ProcessoAndamento.objects.filter(
        fase__fase__in=["Concluído", "Revisão Des"],
        dt_conclusao__date=hoje.date(),
        status__status="Concluído"
    ).values('processo').distinct().count()

    # Métricas gerais (com cache)
    cache_key_metrics = 'general_metrics'
    general_metrics = cache.get(cache_key_metrics)
    if not general_metrics:
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
        general_metrics = {
            'total_pendentes': total_pendentes,
            'processos_por_fase': processos_por_fase
        }
        cache.set(cache_key_metrics, general_metrics, timeout=3600)

    total_pendentes = general_metrics['total_pendentes']
    processos_por_fase = general_metrics['processos_por_fase']

    # VISÃO DO REVISOR(A)
    if is_revisor:
        numero_processo = request.GET.get('numero_processo', '').strip()
        processos_em_revisao = Processo.objects.filter(
            andamentos__fase__fase="Revisão",
            andamentos__usuario=user,
            concluido=False
        ).distinct().select_related('especie', 'usuario').prefetch_related('andamentos', 'andamentos__fase', 'andamentos__status', 'andamentos__usuario')
        if numero_processo:
            processos_em_revisao = processos_em_revisao.filter(numero_processo__icontains=numero_processo)
        
        comentarios_dict = {
            p.pk: list(ComentarioProcesso.objects.filter(processo=p).select_related('usuario'))
            for p in processos_em_revisao
        }
        for processo in processos_em_revisao:
            total_comentarios = processo.comentarios.count()
            ultimo_andamento = processo.andamentos.filter(
                fase__fase="Revisão",
                usuario=user,
                status__status__in=["Não iniciado", "Em andamento"]
            ).order_by('-dt_criacao').first()
            if ultimo_andamento:
                especie_nome = processo.especie.especie if processo.especie else "Sem espécie"
                comentarios = comentarios_dict.get(processo.pk, [])
                andamento_metrics.append({
                    'pk': ultimo_andamento.pk,
                    'processo_pk': processo.pk,
                    'numero_processo': processo.numero_processo,
                    'data_dist': processo.data_dist,
                    'dias_no_gabinete': processo.dias_no_gabinete() or 0,
                    'fase': ultimo_andamento.fase.fase,
                    'descricao': ultimo_andamento.andamento,
                    'status': ultimo_andamento.status.status,
                    'data_inicio': ultimo_andamento.dt_inicio,
                    'data_conclusao': ultimo_andamento.dt_conclusao,
                    'tipo': processo.tipo.tipo if processo.tipo else "Sem tipo",
                    'link_doc': ultimo_andamento.link_doc,
                    'usuario_processo': processo.usuario.get_full_name() if processo.usuario else "Não atribuído",
                    'especie': especie_nome,
                    'sigla_especie': processo.especie.sigla if processo.especie else "",
                    'data_envio_revisao': ultimo_andamento.dt_criacao,
                    'tema': processo.tema.nome if processo.tema else None,
                    'comentarios': [{'texto': c.texto, 'data_criacao': c.data_criacao, 'usuario': c.usuario.get_full_name()} for c in comentarios],
                    'tem_comentario': total_comentarios > 0, # <-- ADICIONE ESTA LINHA
                    'total_comentarios': total_comentarios,   # <-- ADICIONE ESTA LINHA

                })
        andamento_metrics.sort(
                    key=lambda p: (0 if p.get('tipo') == "2ª Correção" else 1,
                        0 if p.get('tipo') == "Redistribuído" else 2,
                        0 if p.get('especie') == "Voto Vista" else 3,
                        0 if p.get('especie') == "EDCIV" else 4,
                        0 if p.get('especie') == "Revisitado" else 5,
                        0 if p.get('especie') == "Voto de Divergência" else 6,
                        0 if p.get('tipo') == "Urgentíssimo" else 7,
                        0 if p.get('tipo') == "Prioridade" else 8,
                        0 if p.get('tipo') == "Monocrática" else 9,                      
                        -(p.get('dias_no_gabinete') or 0))
)


 # --- VISÃO DA DESEMBARGADORA ---

    elif is_desembargador:
        numero_processo = request.GET.get('numero_processo', '').strip()

        # Pegamos somente processos com último andamento em "Revisão Des",
        # do próprio usuário (desembargadora), e com status "Não iniciado" ou "Em andamento".
        processos_em_revisao_des = (
            Processo.objects
            .filter(
                concluido=False,
                andamentos__fase__fase="Revisão Des",
                andamentos__usuario=user,
            )
            .annotate(
                max_dt_criacao=Max('andamentos__dt_criacao')
            )
            .filter(
                andamentos__dt_criacao=F('max_dt_criacao'),
                andamentos__status__status__in=["Não iniciado", "Em andamento"]
            )
            .distinct()
            .select_related('especie', 'usuario', 'tipo')
            .prefetch_related('andamentos', 'andamentos__fase', 'andamentos__status', 'andamentos__usuario')
        )

        if numero_processo:
            processos_em_revisao_des = processos_em_revisao_des.filter(numero_processo__icontains=numero_processo)

        numero_de_processos_em_revisao_des = processos_em_revisao_des.count()

        comentarios_dict = {
            p.pk: list(ComentarioProcesso.objects.filter(processo=p).select_related('usuario'))
            for p in processos_em_revisao_des
        }

        andamento_metrics = []
        for processo in processos_em_revisao_des:
            # Último andamento em Revisão Des desta desembargadora (em aberto)
            total_comentarios = processo.comentarios.count()
            ultimo_andamento = processo.andamentos.filter(
                fase__fase="Revisão Des",
                usuario=user,
                status__status__in=["Não iniciado", "Em andamento"]
            ).order_by('-dt_criacao').first()

            if ultimo_andamento:
                especie_nome = processo.especie.especie if processo.especie else "Sem espécie"
                tipo_nome = processo.tipo.tipo if processo.tipo else "Sem tipo"
                comentarios = comentarios_dict.get(processo.pk, [])
                revisoes_des_count = processo.andamentos.filter(fase__fase="Revisão Des").count()

                andamento_metrics.append({
                    'pk': ultimo_andamento.pk,
                    'processo_pk': processo.pk,
                    'numero_processo': processo.numero_processo,
                    'data_dist': processo.data_dist,
                    'dias_no_gabinete': processo.dias_no_gabinete() or 0,
                    'fase': ultimo_andamento.fase.fase,
                    'descricao': ultimo_andamento.andamento,
                    'status': ultimo_andamento.status.status,
                    'data_inicio': ultimo_andamento.dt_inicio,
                    'data_conclusao': ultimo_andamento.dt_conclusao,
                    'link_doc': ultimo_andamento.link_doc,
                    'usuario_processo': processo.usuario.get_full_name() if processo.usuario else "Não atribuído",
                    'especie': especie_nome,
                    'sigla_especie': processo.especie.sigla if processo.especie else "",
                    'tipo': tipo_nome,
                    'comentarios': [
                        {'texto': c.texto, 'data_criacao': c.data_criacao, 'usuario': c.usuario.get_full_name()}
                        for c in comentarios
                    ],
                    'revisoes_des': revisoes_des_count,
                    'data_envio_revisao_des': ultimo_andamento.dt_criacao,
                    'tema': processo.tema.nome if processo.tema else None,
                    'camara': processo.camara.camara if getattr(processo, 'camara', None) else "Sem câmara",
                    'tem_comentario': total_comentarios > 0, # <-- ADICIONE ESTA LINHA
                    'total_comentarios': total_comentarios,   # <-- ADICIONE ESTA LINHA
                })

        # Ordenação: Plantão primeiro, depois Liminar, depois mais tempo no gabinete
        andamento_metrics.sort(
            key=lambda p: (0 if p.get('tipo') == "2ª Correção" else 1,
                        0 if p.get('tipo') == "Redistribuído" else 2,
                        0 if p.get('especie') == "Voto Vista" else 3,
                        0 if p.get('especie') == "EDCIV" else 4,
                        0 if p.get('especie') == "Revisitado" else 5,
                        0 if p.get('especie') == "Voto de Divergência" else 6,
                        0 if p.get('tipo') == "Urgentíssimo" else 7,
                        0 if p.get('tipo') == "Prioridade" else 8,
                        0 if p.get('tipo') == "Monocrática" else 9,                      
                        -(p.get('dias_no_gabinete') or 0))
        )

        # Lista de mais antigos
        processos_mais_antigos = (
            Processo.objects.filter(concluido=False, antigo__isnull=False)
            .select_related('especie', 'usuario', 'tipo')
            .order_by('antigo')[:10]
        )
        processos_antigos_detalhados = []
        for processo in processos_mais_antigos:
            ultimo_andamento = processo.andamentos.order_by('-dt_criacao').first()
            dias_no_gabinete = (hoje - processo.antigo).days if processo.antigo else 0
            tipo_nome = processo.tipo.tipo if processo.tipo else "Sem tipo"
            processos_antigos_detalhados.append({
                'numero_processo': processo.numero_processo,
                'especie': processo.especie.especie if processo.especie else "Sem espécie",
                'data_entrada_gabinete': processo.antigo,
                'dias_no_gabinete': dias_no_gabinete,
                'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else "Sem fase",
                'usuario': processo.usuario.get_full_name() if processo.usuario else "Não atribuído",
                'tipo': tipo_nome,
            })
        processos_antigos_detalhados.sort(
            key=lambda p: (0 if p.get('tipo') == "2ª Correção" else 1,
                        0 if p.get('tipo') == "Redistribuído" else 2,
                        0 if p.get('especie') == "Voto Vista" else 3,
                        0 if p.get('especie') == "EDCIV" else 4,
                        0 if p.get('especie') == "Revisitado" else 5,
                        0 if p.get('especie') == "Voto de Divergência" else 6,
                        0 if p.get('tipo') == "Urgentíssimo" else 7,
                        0 if p.get('tipo') == "Prioridade" else 8,
                        0 if p.get('tipo') == "Monocrática" else 9,                      
                        -(p.get('dias_no_gabinete') or 0))
        )

        # Lista de liminares
        processos_liminares = (
            Processo.objects.filter(concluido=False, especie__especie="Liminar")
            .select_related('especie', 'usuario', 'tipo')
            .order_by('antigo')
        )
        processos_liminares_detalhados = []
        for processo in processos_liminares:
            ultimo_andamento = processo.andamentos.order_by('-dt_criacao').first()
            dias_no_gabinete = (hoje - processo.data_dist).days if processo.data_dist else 0
            tipo_nome = processo.tipo.tipo if processo.tipo else "Sem tipo"
            processos_liminares_detalhados.append({
                'numero_processo': processo.numero_processo,
                'data_entrada_gabinete': processo.data_dist,
                'dias_no_gabinete': dias_no_gabinete,
                'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else "Sem fase",
                'usuario': processo.usuario.get_full_name() if processo.usuario else "Não atribuído",
                'tipo': tipo_nome,
            })
        processos_liminares_detalhados.sort(
            key=lambda p: (0 if p['tipo'] == "Prioridade" else 1, -(p['dias_no_gabinete'] or 0))
        )

    # VISÃO DO CHEFE DE GABINETE
    elif is_chefe:
        andamento_metrics = []
        processos_mais_antigos = Processo.objects.filter(
            concluido=False,
            antigo__isnull=False
        ).select_related('especie', 'usuario').order_by('antigo')[:10]
        processos_antigos_detalhados = []
        for processo in processos_mais_antigos:
            ultimo_andamento = processo.andamentos.order_by('-dt_criacao').first()
            dias_no_gabinete = (hoje - processo.antigo).days if processo.antigo else 0
            processos_antigos_detalhados.append({
                'numero_processo': processo.numero_processo,
                'especie': processo.especie.especie if processo.especie else "Sem espécie",
                'data_entrada_gabinete': processo.antigo,
                'dias_no_gabinete': dias_no_gabinete,
                'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else "Sem fase",
                'usuario': processo.usuario.get_full_name() if processo.usuario else "Não atribuído",
            })
        processos_liminares = Processo.objects.filter(
            concluido=False,
            especie__especie="Liminar"
        ).select_related('especie', 'usuario').order_by('antigo')
        processos_liminares_detalhados = []
        for processo in processos_liminares:
            ultimo_andamento = processo.andamentos.order_by('-dt_criacao').first()
            dias_no_gabinete = (hoje - processo.data_dist).days if processo.data_dist else 0
            processos_liminares_detalhados.append({
                'numero_processo': processo.numero_processo,
                'data_entrada_gabinete': processo.data_dist,
                'dias_no_gabinete': dias_no_gabinete,
                'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else "Sem fase",
                'usuario': processo.usuario.get_full_name() if processo.usuario else "Não atribuído",
            })
             # Processos com +30 dias por assessor
        processos_mais_30 = (
            Processo.objects
            .filter(concluido=False, antigo__isnull=False, usuario__isnull=False)
            .annotate(
                antigo_date=Cast('antigo', output_field=DateField()),
                dias_no_gabinete=ExpressionWrapper(
                    timezone.now().date() - F('antigo_date'),
                    output_field=DurationField()
                )
            )
            .filter(dias_no_gabinete__gt=timedelta(days=30))
            .select_related('usuario', 'especie', 'tipo')
            .prefetch_related('andamentos', 'andamentos__fase')
        )

        # Agrupar por assessor com contagem
        atrasados_por_assessor = defaultdict(list)
        for p in processos_mais_30:
            nome_assessor = p.usuario.get_full_name()
            ultimo_andamento = p.andamentos.order_by('-dt_criacao').first()
            atrasados_por_assessor[nome_assessor].append({
                'numero_processo': p.numero_processo,
                'dias_no_gabinete': p.dias_no_gabinete.days,
                'especie': p.especie.sigla if p.especie else '—',
                'tipo': p.tipo.tipo if p.tipo else 'Sem tipo',
                'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else 'Sem fase',
                'is_liminar': p.tipo.tipo == "Liminar" if p.tipo else False
            })

        # Criar lista estruturada para o template
        atrasados_por_assessor_detalhado = [
            {
                'assessor': nome,
                'quantidade': len(processos),
                'processos': sorted(
                    processos,
                    key=lambda x: (
                        0 if x['is_liminar'] else 1,  # Priorizar liminares
                        -x['dias_no_gabinete']  # Maior tempo no gabinete
                    )
                )
            }
            for nome, processos in atrasados_por_assessor.items()
        ]
        
        # Ordenar assessores por quantidade de processos atrasados (descendente) ou nome
        atrasados_por_assessor_detalhado.sort(key=lambda x: (-x['quantidade'], x['assessor']))

        # Quantitativo total
        total_atrasados = processos_mais_30.count()

    # VISÃO DO ASSESSOR/USUÁRIO COMUM
    else:
        numero_processo = request.GET.get('numero_processo', '').strip()
        despacho = request.GET.get('despacho', '').strip()
        tipo = request.GET.get('tipo', '').strip()
        especie = request.GET.get('especie', '').strip()  # Novo parâmetro para espécie

        processos_nao_concluidos = Processo.objects.filter(
            usuario=user,
            concluido=False
        ).select_related('especie', 'usuario').prefetch_related('andamentos', 'andamentos__fase', 'andamentos__status')

        # Aplicar filtros
        if numero_processo:
            numero_processo = numero_processo.strip()[:10]
            processos_nao_concluidos = processos_nao_concluidos.annotate(
                numero_processo_truncado=Left('numero_processo', 10)
            ).filter(
                numero_processo_truncado__icontains=numero_processo
            )
        if despacho:
            if despacho.lower() == 'sim':
                processos_nao_concluidos = processos_nao_concluidos.filter(despacho=True)
            elif despacho.lower() == 'nao':
                processos_nao_concluidos = processos_nao_concluidos.filter(despacho=False)
        if tipo:
            processos_nao_concluidos = processos_nao_concluidos.filter(tipo__tipo__icontains=tipo)
        if especie:  # Novo filtro por espécie
            processos_nao_concluidos = processos_nao_concluidos.filter(especie__sigla__iexact=especie)

        if not is_revisor and not is_desembargador and not is_chefe:
            comentarios_dict = {
                p.pk: list(ComentarioProcesso.objects.filter(processo=p).select_related('usuario'))
                for p in processos_nao_concluidos
            }
            for processo in processos_nao_concluidos:
                total_comentarios = processo.comentarios.count()
                ultimo_andamento = processo.andamentos.order_by('-dt_criacao').first()
                if ultimo_andamento and processo.pk:
                    processos_detalhados.append({
                        'pk': processo.pk,
                        'andamento_pk': ultimo_andamento.pk,
                        'andamento_link_doc': ultimo_andamento.link_doc if ultimo_andamento else None,
                        'numero_processo': processo.numero_processo,
                        'especie': processo.especie.especie if processo.especie else "Sem espécie",
                        'sigla': processo.especie.sigla if processo.especie else "Sem sigla",
                        'tema': processo.tema.nome if processo.tema else None,
                        'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else "Sem fase",
                        'status_atual': ultimo_andamento.status.status if ultimo_andamento and ultimo_andamento.status else "Sem status",
                        'data_prazo': processo.dt_prazo,
                        'data_dist': processo.data_dist,
                        'despacho': processo.despacho,
                        'prioridade_urgente': processo.prioridade_urgente,
                        'tipo': processo.tipo.tipo if processo.tipo else "Sem tipo",
                        'dias_no_gabinete': processo.dias_no_gabinete() or 0,
                        'usuario_processo': processo.usuario.get_full_name() if processo.usuario else "Não atribuído",
                        'comentarios': [
                            {'texto': c.texto, 'data_criacao': c.data_criacao, 'usuario': c.usuario.get_full_name()}
                            for c in comentarios_dict.get(processo.pk, [])],
                        'tem_comentario': total_comentarios > 0, # <-- ADICIONE ESTA LINHA
                        'total_comentarios': total_comentarios,   # <-- ADICIONE ESTA LINHA
                        
                    })
            processos_detalhados.sort(
                key=lambda p: (0 if p.get('tipo') == "2ª Correção" else 1,
                            0 if p.get('tipo') == "Redistribuído" else 2,
                            0 if p.get('especie') == "Voto Vista" else 3,
                            0 if p.get('especie') == "EDCIV" else 4,
                            0 if p.get('especie') == "Revisitado" else 5,
                            0 if p.get('especie') == "Voto de Divergência" else 6,
                            0 if p.get('tipo') == "Urgentíssimo" else 7,
                            0 if p.get('tipo') == "Prioridade" else 8,
                            0 if p.get('tipo') == "Monocrática" else 9,                      
                            -(p.get('dias_no_gabinete') or 0))
        )

            fixed_phase_order = ['Elaboração', 'Revisão', 'Correção', 'Revisão Des', 'Devolvido', 'L. PJE']
            phase_dict = {}
            for processo in processos_detalhados:
                phase_dict.setdefault(processo['fase_atual'], []).append(processo)

            fases = [(phase, phase_dict.get(phase, [])) for phase in fixed_phase_order if phase in phase_dict]
            fase_param = request.GET.get('fase', None)
            if fase_param and fase_param in fixed_phase_order and fase_param in phase_dict:
                active_tab = fase_param
            elif fases:
                active_tab = fases[0][0]

        # Nova Lista: Processos Concluídos do Usuário Logado (apenas hoje)
        processos_concluidos = Processo.objects.filter(
            usuario=user,
            concluido=True,
            dt_conclusao__date=hoje
        ).select_related('especie', 'usuario').prefetch_related('andamentos', 'andamentos__fase', 'andamentos__status')
        for processo in processos_concluidos:
            ultimo_andamento = processo.andamentos.order_by('-dt_criacao').first()
            if ultimo_andamento and processo.pk:
                processos_concluidos_detalhados.append({
                    'pk': processo.pk,
                    'andamento_pk': ultimo_andamento.pk,
                    'numero_processo': processo.numero_processo,
                    'especie': processo.especie.especie if processo.especie else "Sem espécie",
                    'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else "Sem fase",
                    'data_dist': processo.data_dist,
                    'dt_conclusao': processo.dt_conclusao,
                    'dias_no_gabinete': processo.dias_no_gabinete() or 0,
                })
        processos_concluidos_detalhados.sort(
            key=lambda p: p['dt_conclusao'] if p['dt_conclusao'] is not None else timezone.make_aware(timezone.datetime.min),
            reverse=True
        )

        # Nova Lista: Processos Enviados para Revisão Desa pelo Usuário Logado (apenas hoje)
        processos_revisao_des = Processo.objects.filter(
            usuario=user,
            andamentos__fase__fase="Revisão Des",
            andamentos__dt_criacao__date=hoje
        ).distinct().select_related('especie', 'usuario').prefetch_related('andamentos', 'andamentos__fase', 'andamentos__status')
        for processo in processos_revisao_des:
            ultimo_andamento = processo.andamentos.order_by('-dt_criacao').first()
            andamento_revisao_des = processo.andamentos.filter(
                fase__fase="Revisão Des",
                dt_criacao__date=hoje
            ).order_by('-dt_criacao').first()
            if ultimo_andamento and andamento_revisao_des and processo.pk:
                processos_revisao_des_detalhados.append({
                    'pk': processo.pk,
                    'andamento_pk': ultimo_andamento.pk,
                    'numero_processo': processo.numero_processo,
                    'especie': processo.especie.especie if processo.especie else "Sem espécie",
                    'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else "Sem fase",
                    'data_dist': processo.data_dist,
                    'data_envio_revisao_des': andamento_revisao_des.dt_criacao,
                    'dias_no_gabinete': processo.dias_no_gabinete() or 0,
                })
        processos_revisao_des_detalhados.sort(
            key=lambda p: p['data_envio_revisao_des'] if p['data_envio_revisao_des'] is not None else timezone.make_aware(timezone.datetime.min),
            reverse=True
        )

        # Adicionar espécies disponíveis para o formulário de filtros
        especies = Processo.objects.filter(
            usuario=user,
            concluido=False
        ).values('especie__sigla').distinct()
    # Tarefas do Dia (comum a todos os papéis)
    tarefas_do_dia = TarefaDoDia.objects.filter(usuario=user).select_related('processo', 'processo__especie', 'processo__tema').prefetch_related('processo__andamentos', 'processo__andamentos__fase')
    for tarefa in tarefas_do_dia:
        ultimo_andamento = tarefa.processo.andamentos.order_by('-dt_criacao').first() if tarefa.processo else None
        tarefa_dict = {
            'id': tarefa.id,
            'processo': {
                'id': tarefa.processo.id if tarefa.processo else None,
                'numero_processo': tarefa.processo.numero_processo if tarefa.processo else "Sem número",
                'especie': tarefa.processo.especie.especie if tarefa.processo and tarefa

.processo.especie else "Sem espécie",
                'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else "Sem fase",
                'data_dist': tarefa.processo.data_dist if tarefa.processo else None,
                'tema': tarefa.processo.tema.nome if tarefa.processo and tarefa.processo.tema else "Sem tema",
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
    
    # Processos de todas as espécies com mais de 30 dias
    processos_queryset = (
        Processo.objects
        .filter(usuario=user, concluido=False, antigo__isnull=False)
        .annotate(
            antigo_date = Cast('antigo', output_field=DateField()),
            dias_no_gabinete = ExpressionWrapper(
                timezone.now().date() - F('antigo_date'), output_field=DurationField()
            )
        )
        .filter(dias_no_gabinete__gt=timedelta(days=30))
        .select_related('especie')
    )

    processos_atrasados = [
        {
            "numero_processo": p.numero_processo,
            "dias_no_gabinete": p.dias_no_gabinete.days,
            "especie": p.especie.sigla,
        }
        for p in processos_queryset
    ]

    # Métricas e Gamificação (comum a todos os papéis)
    process_metrics = get_process_metrics(user)
    if not is_revisor and not is_desembargador and not is_chefe:
        process_metrics['detalhes_processos'] = processos_detalhados
    process_gamification = get_process_gamification_metrics(user)
    meta_semanal_progresso = get_user_meta_semanal_metrics(user)
    top_users = get_top_users_by_xp()
    photo_url = user.profile.photo.url if hasattr(user, 'profile') and user.profile.photo else '/static/default-profile.png'

    # Contexto comum a todos os papéis
    context = {
        'user': user,
        'is_revisor': is_revisor,
        'is_desembargador': is_desembargador,
        'is_chefe': is_chefe,
        'is_assessor': is_assessor,
        'andamento_metrics': andamento_metrics,
        'process_metrics': process_metrics,
        'process_gamification': process_gamification,
        'meta_semanal_progresso': meta_semanal_progresso,
        'top_users': top_users,
        'photo_url': photo_url,
        'tarefas_ids': tarefas_ids,
        'tarefas_do_dia': tarefas_detalhadas,
        'fases': fases,
        'active_tab': active_tab,
        'temas': Tema.objects.all(),
        'today': hoje,
        'tipos': Tipo.objects.all(),
        'revisoes_hoje': revisoes_hoje,
        'concluidos_revisao_hoje': concluidos_revisao_hoje,
        'total_pendentes': total_pendentes,
        'processos_por_fase': processos_por_fase,
        'processos_antigos_detalhados': processos_antigos_detalhados,
        'processos_liminares_detalhados': processos_liminares_detalhados,
        'processos_concluidos_detalhados': processos_concluidos_detalhados,
        'processos_revisao_des_detalhados': processos_revisao_des_detalhados,
        'numero_de_processos_em_revisao_des': numero_de_processos_em_revisao_des,
        "processos_atrasados": processos_atrasados,
        'atrasados_por_assessor': atrasados_por_assessor_detalhado,
        'total_atrasados': total_atrasados,
        'numero_de_processos_em_revisao_des': numero_de_processos_em_revisao_des,
    }

    if not is_revisor and not is_desembargador and not is_chefe:
        context['show_productivity_charts'] = True

    return render(request, 'home.html', context)

# Endpoints para Chart.js
def get_pending_concluded_data(request):
    data = get_pending_and_concluded_by_assessor()
    return JsonResponse(data)

def get_entries_exits_data(request):
    data = get_daily_entries_and_exits_by_assessor()
    return JsonResponse(data)

def get_revisoes_hoje_data(request):
    # Obter a data atual
    hoje = timezone.now()
    
    # Definir o intervalo de datas: início e fim do dia atual
    data_inicio = timezone.make_aware(timezone.datetime(hoje.year, hoje.month, hoje.day, 0, 0, 0))
    data_fim = timezone.make_aware(timezone.datetime(hoje.year, hoje.month, hoje.day, 23, 59, 59))

    # Contar processos enviados para "Revisão Desa" hoje, agrupados por assessor responsável pelo processo
    enviados_por_assessor = ProcessoAndamento.objects.filter(
        fase__fase="Revisão Des",
        dt_criacao__range=(data_inicio, data_fim)
    ).values('processo__usuario__first_name', 'processo__usuario__last_name').annotate(
        total=Count('processo', distinct=True)
    ).order_by('processo__usuario__first_name', 'processo__usuario__last_name')

    # Contar o total de processos enviados para "Revisão Desa" hoje
    total_enviados = ProcessoAndamento.objects.filter(
        fase__fase="Revisão Des",
        dt_criacao__range=(data_inicio, data_fim)
    ).values('processo').distinct().count()

    # Preparar os dados para o gráfico
    labels = [f"{assessor['processo__usuario__first_name']} {assessor['processo__usuario__last_name']}" for assessor in enviados_por_assessor]
    labels.append("Total Enviados")  # Adicionar o total como último rótulo

    data = [assessor['total'] for assessor in enviados_por_assessor]
    data.append(total_enviados)  # Adicionar o total como último valor

    # Gerar cores dinamicamente para cada assessor (e o total)
    cores = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#6B7280']  # Lista de cores
    background_colors = []
    for i in range(len(labels)):
        background_colors.append(cores[i % len(cores)])  # Ciclar pelas cores se houver mais assessores

    # Atualizar o rótulo para refletir apenas o dia atual
    response_data = {
        'labels': labels,
        'datasets': [{
            'label': f'Enviados para Revisão Des ({hoje.strftime("%d/%m/%Y")})',
            'data': data,
            'backgroundColor': background_colors
        }]
    }
    return JsonResponse(response_data)

def get_fases_data(request):
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

    fases_nomes = [f['fase__fase'] for f in processos_por_fase]
    fases_quantidades = [f['quantidade'] for f in processos_por_fase]

    data = {
        'labels': fases_nomes + ['Total Pendentes'],
        'datasets': [
            {
                'label': 'Por Fase',
                'data': fases_quantidades + [total_pendentes],
                'backgroundColor': ['#3B82F6'] * len(fases_nomes) + ['#EF4444']
            }
        ]
    }
    return JsonResponse(data)

def get_es_assessor_hoje_data(request):
    hoje = timezone.now().date()
    entradas_hoje = (
        Processo.objects.filter(data_dist__date=hoje, usuario__isnull=False)
        .values('usuario__first_name', 'usuario__last_name')
        .annotate(quantidade=Count('id'))
    )
    saidas_hoje = (
        Processo.objects.filter(dt_conclusao__date=hoje, concluido=True, usuario__isnull=False)
        .values('usuario__first_name', 'usuario__last_name')
        .annotate(quantidade=Count('id'))
    )

    # Criar uma lista única de nomes de assessores a partir de entradas e saídas
    assessores_nomes = list(set(
        [f"{e['usuario__first_name']} {e['usuario__last_name']}".strip() for e in entradas_hoje] +
        [f"{s['usuario__first_name']} {s['usuario__last_name']}".strip() for s in saidas_hoje]
    ))

    entradas_dict = {f"{e['usuario__first_name']} {e['usuario__last_name']}".strip(): e['quantidade'] for e in entradas_hoje}
    saidas_dict = {f"{s['usuario__first_name']} {s['usuario__last_name']}".strip(): s['quantidade'] for s in saidas_hoje}
    entradas_vals = [entradas_dict.get(nome, 0) for nome in assessores_nomes]
    saidas_vals = [saidas_dict.get(nome, 0) for nome in assessores_nomes]

    data = {
        'labels': assessores_nomes,
        'datasets': [
            {
                'label': 'Entradas',
                'data': entradas_vals,
                'backgroundColor': '#3B82F6'
            },
            {
                'label': 'Saídas',
                'data': saidas_vals,
                'backgroundColor': '#F59E0B'
            }
        ]
    }
    return JsonResponse(data)

def get_especies_data(request):
    cache_key_especies = 'processos_por_especie'
    processos_por_especie = cache.get(cache_key_especies)
    if not processos_por_especie:
        processos_por_especie = (
            Processo.objects.filter(concluido=False)
            .values('especie__especie')
            .annotate(quantidade=Count('id'))
            .order_by('especie__especie')
        )
        cache.set(cache_key_especies, processos_por_especie, timeout=3600)

    especies_nomes = [e['especie__especie'] if e['especie__especie'] else "Sem Espécie" for e in processos_por_especie]
    especies_quantidades = [e['quantidade'] for e in processos_por_especie]

    data = {
        'labels': especies_nomes,
        'datasets': [{
            'label': 'Processos por Espécie',
            'data': especies_quantidades,
            'backgroundColor': '#10B981'
        }]
    }
    return JsonResponse(data)

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import os

@login_required
def change_profile_photo(request):
    if request.method == 'POST':
        if 'photo' in request.FILES:
            user_profile, created = UserProfile.objects.get_or_create(user=request.user)
            # Deletar a foto antiga, se existir
            if user_profile.photo and os.path.isfile(user_profile.photo.path):
                os.remove(user_profile.photo.path)
            # Salvar a nova foto
            user_profile.photo = request.FILES['photo']
            user_profile.save()
            messages.success(request, 'Foto de perfil atualizada com sucesso!')
            return redirect('home')
        else:
            messages.error(request, 'Por favor, selecione uma imagem.')
    return render(request, 'change_profile_photo.html', {'user_profile': request.user.profile})


def get_user_weekly_productivity_data(request):
    if request.user.is_authenticated:
        data = get_user_weekly_productivity(request.user)
        return JsonResponse(data)
    return JsonResponse({'error': 'Usuário não autenticado'}, status=403)

def get_user_daily_productivity_data(request):
    if request.user.is_authenticated:
        data = get_user_daily_productivity(request.user)
        return JsonResponse(data)
    return JsonResponse({'error': 'Usuário não autenticado'}, status=403)

def get_revisoes_hoje_data(request):
    hoje = timezone.localtime(timezone.now())
    data_str = request.GET.get('data', hoje.strftime('%Y-%m-%d'))

    try:
        data = datetime.strptime(data_str, '%Y-%m-%d')
    except ValueError:
        data = hoje

    local_tz = timezone.get_current_timezone()
    local_data_inicio = timezone.make_aware(datetime(data.year, data.month, data.day, 0, 0, 0), local_tz)
    local_data_fim = timezone.make_aware(datetime(data.year, data.month, data.day, 23, 59, 59), local_tz)

    data_inicio = local_data_inicio.astimezone(dt_timezone.utc)  # Usar dt_timezone.utc
    data_fim = local_data_fim.astimezone(dt_timezone.utc)  # Usar dt_timezone.utc

    enviados_por_assessor = ProcessoAndamento.objects.filter(
        fase__fase="Revisão Des",
        dt_criacao__range=(data_inicio, data_fim),
        processo__usuario__isnull=False
    ).values(
        'processo__usuario__id',
        'processo__usuario__first_name',
        'processo__usuario__last_name'
    ).annotate(
        enviados_des=Count('processo', distinct=True)
    ).order_by('processo__usuario__first_name', 'processo__usuario__last_name')

    meta = 5
    labels, data_enviados, photo_urls = [], [], []

    for assessor in enviados_por_assessor:
        user_id = assessor['processo__usuario__id']
        first_name = assessor['processo__usuario__first_name'] or 'Sem Nome'
        last_name = assessor['processo__usuario__last_name'] or ''
        enviados = assessor['enviados_des']

        labels.append(f"{first_name} {last_name}")
        data_enviados.append(enviados)

        try:
            user = User.objects.get(id=user_id)
            photo_url = (
                user.profile.photo.url if hasattr(user, 'profile') and user.profile.photo
                else f"https://via.placeholder.com/60/083464/FFFFFF?text={first_name[0].upper()}"
            )
        except User.DoesNotExist:
            photo_url = f"https://via.placeholder.com/60/083464/FFFFFF?text={first_name[0].upper()}"

        photo_urls.append(photo_url)

    data_meta = [meta] * len(labels)

    response_data = {
        'labels': labels,
        'datasets': [
            {'label': f'Enviados para Revisão Des ({data.strftime("%d/%m/%Y")})', 'data': data_enviados, 'photo_urls': photo_urls},
            {'label': 'Meta', 'data': data_meta}
        ]
    }
    return JsonResponse(response_data)


from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Count
from datetime import datetime, timedelta, timezone as dt_timezone 
from processos.models import ProcessoAndamento, User

def get_revisoes_semana_data(request):
    hoje = timezone.localtime(timezone.now())
    inicio_semana = hoje - timedelta(days=hoje.weekday())  # segunda-feira
    fim_semana = inicio_semana + timedelta(days=6)  # domingo

    local_tz = timezone.get_current_timezone()
    local_data_inicio = timezone.make_aware(datetime(inicio_semana.year, inicio_semana.month, inicio_semana.day, 0, 0, 0), local_tz)
    local_data_fim = timezone.make_aware(datetime(fim_semana.year, fim_semana.month, fim_semana.day, 23, 59, 59), local_tz)

    data_inicio = local_data_inicio.astimezone(dt_timezone.utc)  # Usar dt_timezone.utc
    data_fim = local_data_fim.astimezone(dt_timezone.utc)  # Usar dt_timezone.utc

    enviados_por_assessor = ProcessoAndamento.objects.filter(
        fase__fase="Revisão Des",
        dt_criacao__range=(data_inicio, data_fim),
        processo__usuario__isnull=False  # Evita processos sem usuário
    ).values(
        'processo__usuario__id',
        'processo__usuario__first_name',
        'processo__usuario__last_name'
    ).annotate(
        enviados_des=Count('processo', distinct=True)
    ).order_by('processo__usuario__first_name')

    labels, data_enviados, photo_urls, medias_diarias = [], [], [], []

    for item in enviados_por_assessor:
        user_id = item['processo__usuario__id']
        first_name = item['processo__usuario__first_name'] or 'Sem Nome'
        last_name = item['processo__usuario__last_name'] or ''
        enviados = item['enviados_des']

        media_dia = enviados / 4  # média considerando 5 dias úteis (segunda a sexta)
        media_dia = round(media_dia, 2)  # arredonda para 2 casas decimais

        try:
            user = User.objects.get(id=user_id)
            photo_url = (
                user.profile.photo.url if hasattr(user, 'profile') and user.profile.photo
                else '/static/default-profile.png'
            )
        except User.DoesNotExist:
            photo_url = '/static/default-profile.png'

        labels.append(f"{first_name} {last_name}")
        data_enviados.append(enviados)
        photo_urls.append(photo_url)
        medias_diarias.append(media_dia)

    response_data = {
        'labels': labels,
        'datasets': [
            {'label': 'Enviados para Revisão na Semana', 'data': data_enviados, 'photo_urls': photo_urls},
            {'label': 'Média por Dia', 'data': medias_diarias}
        ]
    }
    return JsonResponse(response_data)

import json
import os
from openai import OpenAI
from django.conf import settings
from decouple import config
from django.views.decorators.csrf import csrf_exempt

@login_required
def chat_ia_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            question = data.get('question', '')
            
            if not question:
                return JsonResponse({'response': 'Por favor, faça uma pergunta válida.'})

            # Conectar à API da OpenAI
            api_key = config('OPENAI_API_KEY', default='')
            if not api_key or 'sk-cole' in api_key:
                return JsonResponse({'response': 'A chave OPENAI_API_KEY não foi configurada corretamente. Verifique o seu .env.'})
                
            assistant_id = config('OPENAI_ASSISTANT_ID', default='')
            if not assistant_id:
                return JsonResponse({'response': 'O código do Assistente (OPENAI_ASSISTANT_ID) não foi adicionado ao arquivo .env ainda.'})
                
            client = OpenAI(api_key=api_key)
            
            # 1. Cria uma "Sala de Conversa" no lado da OpenAI e manda a Pergunta do Assessor
            thread = client.beta.threads.create()
            client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=question
            )
            
            # 2. Acorda o "Assistente de Gabinete" e manda ele consultar os 5 mil PDFs e responder
            run = client.beta.threads.runs.create_and_poll(
                thread_id=thread.id,
                assistant_id=assistant_id
            )
            
            # 3. Pega a resposta final
            if run.status == 'completed':
                messages = client.beta.threads.messages.list(
                    thread_id=thread.id
                )
                resposta_ia = messages.data[0].content[0].text.value
                
                # Opcional: A OpenAI costuma adicionar referências feias [^1^] ou 【4:0†source】. Limpa via Regex.
                import re
                resposta_limpa = re.sub(r'【.*?】|\[\^.*?\^\]', '', resposta_ia)
                
                return JsonResponse({'response': resposta_limpa})
            else:
                detalhe_erro = run.last_error.message if hasattr(run, 'last_error') and run.last_error else run.status
                return JsonResponse({'response': f'A OpenAI bloqueou a resposta. Motivo: {detalhe_erro}'})
            
        except Exception as e:
            return JsonResponse({'response': f'Erro no processamento da IA: {str(e)}'})
    
    return JsonResponse({'error': 'Apenas requisições POST são permitidas'}, status=400)
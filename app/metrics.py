from django.contrib.auth import get_user_model
from processos.models import Processo
from django.utils.timezone import now
from django.db.models import Count
from datetime import date, datetime
from django.core.cache import cache

def get_process_metrics(user):
    processos_nao_concluidos = Processo.objects.filter(usuario=user, concluido=False).select_related('especie').prefetch_related('andamentos', 'andamentos__fase', 'andamentos__status')

    contagem_por_especie = (
        processos_nao_concluidos
        .values('especie__especie', 'especie__sigla')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    processos_detalhados = []
    hoje = date.today()
    for processo in processos_nao_concluidos:
        andamentos_lista = list(processo.andamentos.all())
        ultimo_andamento = max(andamentos_lista, key=lambda a: a.dt_criacao) if andamentos_lista else None
        prazo_status = "Sem prazo"
        dias_diferenca = None
        if processo.dt_prazo:
            prazo_data = processo.dt_prazo.date() if isinstance(processo.dt_prazo, datetime) else processo.dt_prazo
            dias_diferenca = (prazo_data - hoje).days
            prazo_status = "Vence hoje" if dias_diferenca == 0 else f"Faltam {dias_diferenca} dias" if dias_diferenca > 0 else f"Atrasado {-dias_diferenca} dias"

        processos_detalhados.append({
            'pk': processo.pk,
            'numero_processo': processo.numero_processo,
            'especie': processo.especie.especie if processo.especie else "Sem espécie",
            'sigla': processo.especie.sigla if processo.especie else "Sem sigla",
            'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento else "Sem fase",
            'status_atual': ultimo_andamento.status.status if ultimo_andamento else "Sem status",
            'data_prazo': processo.dt_prazo,
            'data_dist': processo.data_dist,
            'prazo_status': prazo_status,
            'dias_diferenca': dias_diferenca,
        })

    processos_detalhados.sort(key=lambda x: (0 if x['especie'] == "Liminar" else 1, x['data_dist']))

    return {
        'metrics': {
            'total_processos_nao_concluidos': processos_nao_concluidos.count(),
            'contagem_por_especie': list(contagem_por_especie),
        },
        'detalhes_processos': processos_detalhados,
    }

def get_process_gamification_metrics(user):
    completed_processes = Processo.objects.filter(usuario=user, concluido=True).select_related('especie', 'resultado')
    
    if not completed_processes:
        return {'points': 0, 'details': [], 'species_count': {}}

    total_points = 0
    species_count = {}
    details = []
    species_weights = {"LIM": 1, "OUTROS": 1, "RED": 1, "RCL": 1, "RAI": 1, "RAC": 1, "QN": 1, "PV": 1, "PET": 1, "MS": 1, "HC": 1, "CC": 1, "AR": 1, "ADI": 1, "AGR I": 1}
    penalties = {("AGR I", "PROVIDO"): -2, ("AGR I", "PARCIALMENTE PROVIDO"): -1, ("RED", "ACOLHIDO"): -2, ("RED", "PARCIALMENTE ACOLHIDO"): -1}

    for process in completed_processes:
        sigla_especie = process.especie.sigla if process.especie else "Sem Sigla"
        species_count[sigla_especie] = species_count.get(sigla_especie, 0) + 1
        weight = species_weights.get(sigla_especie, 1)
        resultado_processo = process.resultado.resultado if process.resultado else None
        penalty = penalties.get((sigla_especie, resultado_processo), 0)
        final_points = max(0, weight + penalty)
        total_points += final_points
        details.append({
            'numero_processo': process.numero_processo,
            'especie': sigla_especie,
            'resultado': resultado_processo,
            'points': final_points,
            'penalty': penalty,
        })

    return {'points': total_points, 'details': details, 'species_count': species_count}

User = get_user_model()

def get_top_users_by_xp():
    cache_key = 'top_users_gamification'
    top_users = cache.get(cache_key)
    if top_users is not None:
        return top_users

    species_weights = {"LIM": 1, "OUTROS": 1, "RED": 1, "RCL": 1, "RAI": 1, "RAC": 1, "QN": 1, "PV": 1, "PET": 1, "MS": 1, "HC": 1, "CC": 1, "AR": 1, "ADI": 1, "AGR I": 1}
    penalties = {("AGR I", "PROVIDO"): -2, ("AGR I", "PARCIALMENTE PROVIDO"): -1, ("RED", "ACOLHIDO"): -2, ("RED", "PARCIALMENTE ACOLHIDO"): -1}

    all_users_data = []
    for user in User.objects.prefetch_related('processo_set'):
        completed_processes = user.processo_set.filter(concluido=True).select_related('especie', 'resultado')
        points = 0
        species_count = {}

        for process in completed_processes:
            sigla_especie = process.especie.sigla if process.especie else "Sem Sigla"
            species_count[sigla_especie] = species_count.get(sigla_especie, 0) + 1
            weight = species_weights.get(sigla_especie, 1)
            resultado_processo = process.resultado.resultado if process.resultado else None
            penalty = penalties.get((sigla_especie, resultado_processo), 0)
            points += max(0, weight + penalty)

        all_users_data.append({
            'user': user,
            'name': user.get_full_name(),
            'photo': user.profile.photo.url if hasattr(user, 'profile') and user.profile.photo else '',
            'points': points,
            'species_count': species_count,
        })

    result = sorted(all_users_data, key=lambda x: x['points'], reverse=True)[:3]
    cache.set(cache_key, result, timeout=3600)
    return result


from django.db.models import Count, Q
from accounts.models import UserProfile
from processos.models import Processo

def get_pending_and_concluded_by_assessor():
    """
    Retorna processos pendentes e concluídos por assessor em formato para Chart.js.
    Inclui apenas assessores com processos atribuídos.
    """
    assessores = UserProfile.objects.filter(funcao="Assessor(a)").select_related('user')
    usuario_ids = assessores.values_list('user_id', flat=True)

    # Agregar processos por usuário em uma única consulta
    processos_por_assessor = (
        Processo.objects.filter(usuario__in=usuario_ids)
        .values('usuario')
        .annotate(
            total=Count('id'),
            concluidos=Count('id', filter=Q(concluido=True))
        )
        .order_by('usuario')
    )

    # Mapear IDs para nomes
    usuario_nome_map = {perfil.user.id: perfil.user.get_full_name() for perfil in assessores}

    # Preparar dados para Chart.js
    labels = []
    pendentes_data = []
    concluidos_data = []

    for processo in processos_por_assessor:
        usuario_id = processo['usuario']
        total_processos = processo['total'] or 0
        concluidos = processo['concluidos'] or 0
        pendentes = total_processos - concluidos

        if total_processos > 0:  # Só inclui assessores com processos
            labels.append(usuario_nome_map.get(usuario_id, "Desconhecido"))
            pendentes_data.append(pendentes)
            concluidos_data.append(concluidos)

    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Pendentes',
                'data': pendentes_data,
                'backgroundColor': '#EF4444',
            },
            {
                'label': 'Concluídos',
                'data': concluidos_data,
                'backgroundColor': '#10B981',
            }
        ]
    }

from django.db.models import Count, Q
from django.db.models.functions import TruncDay
from django.utils import timezone
from datetime import timedelta
from accounts.models import UserProfile

def get_daily_entries_and_exits_by_assessor(days=7):
    """
    Retorna entradas e saídas dos últimos 'days' dias em formato para Chart.js.
    """
    hoje = timezone.now().date()
    data_inicio = hoje - timedelta(days=days)

    # Entradas
    entradas_qs = (
        Processo.objects.filter(data_dist__gte=data_inicio)
        .annotate(dia=TruncDay('data_dist'))
        .values('dia')
        .annotate(quantidade=Count('id'))
        .order_by('dia')
    )

    # Saídas
    saidas_qs = (
        Processo.objects.filter(dt_conclusao__gte=data_inicio)
        .annotate(dia=TruncDay('dt_conclusao'))
        .values('dia')
        .annotate(quantidade=Count('id'))
        .order_by('dia')
    )

    # Preparar dados para Chart.js
    dias = sorted(set([e['dia'] for e in entradas_qs] + [s['dia'] for s in saidas_qs]))
    entradas_dict = {e['dia']: e['quantidade'] for e in entradas_qs}
    saidas_dict = {s['dia']: s['quantidade'] for s in saidas_qs}

    labels = [d.strftime("%d/%m/%Y") for d in dias]
    entradas_data = [entradas_dict.get(d, 0) for d in dias]
    saidas_data = [saidas_dict.get(d, 0) for d in dias]

    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Entradas',
                'data': entradas_data,
                'backgroundColor': '#3B82F6',
            },
            {
                'label': 'Saídas',
                'data': saidas_data,
                'backgroundColor': '#F59E0B',
            }
        ]
    }


from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

def get_user_weekly_productivity(user):
    hoje = timezone.now().date()
    inicio_semana = hoje - timedelta(days=6)

    # Processos distribuídos por dia
    distribuídos_qs = (
        Processo.objects.filter(usuario=user, data_dist__gte=inicio_semana)
        .annotate(dia=TruncDay('data_dist'))
        .values('dia')
        .annotate(quantidade=Count('id'))
        .order_by('dia')
    )
    
    from processos.models import ProcessoAndamento
    from django.db.models import Subquery, OuterRef
    
    fases_validas = ["Revisão", "Revisão Des", "Processo Concluído"]
    processos_validos_ids = set(
        Processo.objects.annotate(
            fase_atual=Subquery(
                ProcessoAndamento.objects.filter(
                    processo=OuterRef('pk')
                ).order_by('-dt_criacao').values('fase__fase')[:1]
            )
        ).filter(fase_atual__in=fases_validas).values_list('id', flat=True)
    )
    
    # Processos concluídos por dia (agora: Revisão + Monocráticas)
    revisao_qs = (
        ProcessoAndamento.objects.filter(
            processo__usuario=user,
            processo__id__in=processos_validos_ids,
            fase__fase__in=fases_validas,
            dt_criacao__date__gte=inicio_semana
        )
        .annotate(dia=TruncDay('dt_criacao'))
        .values('dia')
        .annotate(quantidade=Count('processo', distinct=True))
    )
    
    monocraticas_qs = (
        Processo.objects.filter(
            usuario=user,
            tipo__tipo="Monocrática",
            concluido=True,
            dt_conclusao__date__gte=inicio_semana
        )
        .annotate(dia=TruncDay('dt_conclusao'))
        .values('dia')
        .annotate(quantidade=Count('id'))
    )

    dias = [inicio_semana + timedelta(days=x) for x in range(7)]
    
    distribuídos_dict = {}
    for d in distribuídos_qs:
        dia_val = d['dia']
        if isinstance(dia_val, datetime):
            dia_val = dia_val.date()
        distribuídos_dict[dia_val] = d['quantidade']
        
    concluídos_dict = {}
    for d in revisao_qs:
        dia_val = d['dia']
        if isinstance(dia_val, datetime):
            dia_val = dia_val.date()
        concluídos_dict[dia_val] = concluídos_dict.get(dia_val, 0) + d['quantidade']
        
    for d in monocraticas_qs:
        dia_val = d['dia']
        if isinstance(dia_val, datetime):
            dia_val = dia_val.date()
        concluídos_dict[dia_val] = concluídos_dict.get(dia_val, 0) + d['quantidade']

    labels = [d.strftime("%d/%m") for d in dias]
    distribuídos_data = [distribuídos_dict.get(d, 0) for d in dias]
    concluídos_data = [concluídos_dict.get(d, 0) for d in dias]

    # Soma total
    total_distribuidos = sum(distribuídos_data)
    total_concluidos = sum(concluídos_data)
    saldo_semana = total_distribuidos - total_concluidos

    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Distribuídos',
                'data': distribuídos_data,
                'backgroundColor': '#3B82F6',
            },
            {
                'label': 'Concluídos',
                'data': concluídos_data,
                'backgroundColor': '#10B981',
            }
        ],
        # Adicionamos extras para exibir no front
        'total_distribuidos': total_distribuidos,
        'total_concluidos': total_concluidos,
        'saldo_semana': saldo_semana
    }


def get_user_daily_productivity(user):
    """
    Retorna a produtividade diária do usuário (processos distribuídos e concluídos hoje) em formato para Chart.js.
    """
    hoje = timezone.now().date()

    # Processos distribuídos hoje
    distribuídos_hoje = Processo.objects.filter(
        usuario=user, data_dist__date=hoje
    ).count()

    from django.db.models import Subquery, OuterRef
    from processos.models import ProcessoAndamento
    
    # Processos concluídos hoje (agora: enviados para Revisão hoje + Monocráticas concluídas hoje)
    fases_validas = ["Revisão", "Revisão Des", "Processo Concluído"]
    processos_hoje_qs = Processo.objects.filter(
        Q(andamentos__fase__fase__in=fases_validas, andamentos__dt_criacao__date=hoje) | 
        Q(tipo__tipo="Monocrática", concluido=True, dt_conclusao__date=hoje),
        usuario=user
    ).distinct().annotate(
        fase_atual=Subquery(
            ProcessoAndamento.objects.filter(
                processo=OuterRef('pk')
            ).order_by('-dt_criacao').values('fase__fase')[:1]
        )
    )

    concluídos_hoje = 0
    for p in processos_hoje_qs:
        if (p.tipo and p.tipo.tipo == "Monocrática" and p.concluido) or (p.fase_atual in fases_validas):
            concluídos_hoje += 1

    return {
        'labels': ['Distribuídos', 'Concluídos'],
        'datasets': [
            {
                'label': 'Produtividade Hoje',
                'data': [distribuídos_hoje, concluídos_hoje],
                'backgroundColor': ['#3B82F6', '#10B981'],
            }
        ]
    }

def get_user_meta_semanal_metrics(user):
    from processos.models import MetaSemanal, ProcessoAndamento
    from datetime import timedelta
    from django.utils import timezone
    
    agora_dt = timezone.localtime()
    hoje = agora_dt.date()
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana = inicio_semana + timedelta(days=6)
    
    meta = MetaSemanal.objects.filter(
        usuario=user,
        semana_inicio=inicio_semana,
        semana_fim=fim_semana
    ).first()
    
    if not meta:
        return None
        
    total_meta = meta.meta_qtd
    processos_ids = list(meta.processos.values_list('id', flat=True))
    processos = Processo.objects.filter(id__in=processos_ids)
    
    FASES_EXATAS = ["Revisão", "Revisão Des", "L. PJE", "L.PJE", "Processo Concluído"]
    
    # Processo concluído pelo assessor = passou pela fase de conclusão na semana da meta
    # (independente de onde está hoje — pode já estar em Revisão Des, Concluído, etc.)
    concluidos_ids = set(
        ProcessoAndamento.objects.filter(
            processo__in=processos,
            fase__fase__in=FASES_EXATAS,
            dt_criacao__date__range=(inicio_semana, fim_semana)
        ).values_list('processo_id', flat=True).distinct()
    )
    
    total_concluidas = len(concluidos_ids)
            
    faltam = max(0, total_meta - total_concluidas)
    progresso = int((total_concluidas / total_meta * 100)) if total_meta > 0 else 0
    
    return {
        'total': total_meta,
        'concluidas': total_concluidas,
        'faltam': faltam,
        'progresso': min(progresso, 100),
    }

from django.contrib.auth import get_user_model
from processos.models import Processo
from django.utils.timezone import now
from django.db.models import Count
from datetime import date, datetime

def get_process_metrics(user):
    processos_nao_concluidos = Processo.objects.filter(usuario=user, concluido=False).select_related('especie')

    contagem_por_especie = (
        processos_nao_concluidos
        .values('especie__especie', 'especie__sigla')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    processos_detalhados = []
    hoje = date.today()
    for processo in processos_nao_concluidos:
        ultimo_andamento = processo.andamentos.order_by('-dt_criacao').select_related('fase', 'status').first()
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

    return sorted(all_users_data, key=lambda x: x['points'], reverse=True)[:3]
from django.contrib.auth import get_user_model
from processos.models import Processo, ProcessoAndamento
from django.utils.timezone import now
from django.db.models import Count
from datetime import date

from datetime import datetime, date
def get_process_metrics(user):
    """
    Gera métricas e detalhamento de processos que ainda não foram concluídos.
    Inclui fase atual, status, espécie e status do prazo.
    """
    processos_nao_concluidos = Processo.objects.filter(usuario=user, concluido=False)

    # Contagem por espécie com siglas corretas
    contagem_por_especie = (
        processos_nao_concluidos
        .values('especie__especie', 'especie__sigla')  # Adiciona 'sigla'
        .annotate(total=Count('id'))  # Conta os processos de cada espécie
        .order_by('-total')  # Ordena pela quantidade
    )

    processos_detalhados = []
    for processo in processos_nao_concluidos:
        ultimo_andamento = processo.andamentos.order_by('-dt_criacao').first()
        hoje = date.today()
        prazo_status = "Sem prazo"
        dias_diferenca = None
        if processo.dt_prazo:
            prazo_data = processo.dt_prazo.date() if isinstance(processo.dt_prazo, datetime) else processo.dt_prazo
            dias_diferenca = (prazo_data - hoje).days
            if dias_diferenca == 0:
                prazo_status = "Vence hoje"
            elif dias_diferenca > 0:
                prazo_status = f"Faltam {dias_diferenca} dias"
            else:
                prazo_status = f"Atrasado {-dias_diferenca} dias"

        processos_detalhados.append({
            'pk': processo.pk,
            'numero_processo': processo.numero_processo,
            'especie': processo.especie.especie if processo.especie else "Sem espécie",
            'sigla': processo.especie.sigla if processo.especie and processo.especie.sigla else "Sem sigla",
            'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else "Sem fase",
            'status_atual': ultimo_andamento.status.status if ultimo_andamento and ultimo_andamento.status else "Sem status",
            'data_prazo': processo.dt_prazo,
            'data_dist': processo.data_dist,
            'prazo_status': prazo_status,
            'dias_diferenca': dias_diferenca,
        })

    # Ordenar os processos atrasados primeiro
    processos_detalhados = sorted(
        processos_detalhados,
        key=lambda x: (0 if x['especie'] == "Liminar" else 1, x['data_dist'])
    )


    metrics = {
        'total_processos_nao_concluidos': processos_nao_concluidos.count(),
        'contagem_por_especie': list(contagem_por_especie),  # Lista com contagem por espécie
    }

    return {
        'metrics': metrics,
        'detalhes_processos': processos_detalhados,
    }


def get_process_gamification_metrics(user):
    """
    Calcula a gamificação baseada nos processos concluídos, sem dependência de prazos.
    Mantém a contagem por espécie e penalizações específicas por resultado.
    """
    # 🔹 Filtra os processos concluídos do usuário
    completed_processes = Processo.objects.filter(usuario=user, concluido=True)

    print(f"🔹 Usuário: {user}")
    print(f"🔹 Processos Concluídos Encontrados: {completed_processes.count()}")

    if not completed_processes.exists():
        print("⚠️ Nenhum processo concluído encontrado!")

    total_points = 0
    species_count = {}  # Contagem por espécie
    details = []

    species_weights = {
        "LIM": 1,  
        "OUTROS": 1,
        "RED": 1,
        "RCL": 1,
        "RAI": 1,
        "RAC": 1,
        "QN": 1,
        "PV": 1,
        "PET": 1,
        "MS": 1,
        "HC": 1,
        "CC": 1,
        "AR": 1,
        "ADI": 1,
        "AGR I": 1,  
    }


    penalties = {
        ("AGR I", "PROVIDO"): -2,
        ("AGR I", "PARCIALMENTE PROVIDO"): -1,
        ("RED", "ACOLHIDO"): -2,
        ("RED", "PARCIALMENTE ACOLHIDO"): -1,
    }

    for process in completed_processes:
        sigla_especie = process.especie.sigla if process.especie else "Sem Sigla"
        species_count[sigla_especie] = species_count.get(sigla_especie, 0) + 1

        weight = species_weights.get(sigla_especie, 1)
        resultado_processo = process.resultado.resultado if process.resultado else None
        penalty = penalties.get((sigla_especie, resultado_processo), 0)

        final_points = weight + penalty
        final_points = max(0, final_points)
        total_points += final_points

        details.append({
            'numero_processo': process.numero_processo,
            'especie': sigla_especie,
            'resultado': resultado_processo,
            'points': final_points,
            'penalty': penalty,
        })

    print("🔹 Contagem por Espécie:", species_count)

    return {
        'points': total_points,
        'details': details,
        'species_count': species_count,
    }



User = get_user_model()

def get_top_users_by_xp():
    """
    Calcula a gamificação para todos os usuários e retorna os 3 com mais pontos.
    Inclui contagem por espécie com pesos específicos e penalizações baseadas no resultado.
    """
    all_users_data = []

    # 🔹 Dicionário de pesos específicos para cada espécie
    species_weights = {
        "LIM": 1,  
        "OUTROS": 1,
        "RED": 1,
        "RCL": 1,
        "RAI": 1,
        "RAC": 1,
        "QN": 1,
        "PV": 1,
        "PET": 1,
        "MS": 1,
        "HC": 1,
        "CC": 1,
        "AR": 1,
        "ADI": 1,
        "AGR I": 1,  
    }

    # 🔹 Penalizações específicas por resultado
    penalties = {
        ("AGR I", "PROVIDO"): -2,
        ("AGR I", "PARCIALMENTE PROVIDO"): -1,
        ("RED", "ACOLHIDO"): -2,
        ("RED", "PARCIALMENTE ACOLHIDO"): -1,
    }

    for user in User.objects.all():
        # Filtra os processos concluídos do usuário
        completed_processes = Processo.objects.filter(usuario=user, concluido=True)

        points = 0
        species_count = {}

        for process in completed_processes:
            # Obtém a sigla da espécie
            sigla_especie = process.especie.sigla if process.especie else "Sem Sigla"
            species_count[sigla_especie] = species_count.get(sigla_especie, 0) + 1

            # Obtém o peso da espécie (padrão 1 se não estiver no dicionário)
            weight = species_weights.get(sigla_especie, 1)

            # Verifica se a espécie e o resultado possuem penalização
            resultado_processo = process.resultado.resultado if process.resultado else None
            penalty = penalties.get((sigla_especie, resultado_processo), 0)  # Padrão 0 se não houver penalização
            
            # Aplica a pontuação final considerando a penalização
            points += weight + penalty

        # 🔹 Adiciona o usuário e seus pontos à lista
        all_users_data.append({
            'user': user,
            'name': user.get_full_name(),
            'photo': user.profile.photo.url if hasattr(user, 'profile') and user.profile.photo else '',
            'points': points,
            'species_count': species_count,  
        })

    # 🔹 Ordena os usuários pelo total de pontos em ordem decrescente e pega os 3 primeiros
    top_users = sorted(all_users_data, key=lambda x: x['points'], reverse=True)[:3]

    return top_users


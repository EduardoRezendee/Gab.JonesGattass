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
        key=lambda x: (x['dias_diferenca'] if x['dias_diferenca'] is not None else float('inf'))
    )

    metrics = {
        'total_processos_nao_concluidos': processos_nao_concluidos.count(),
        'contagem_por_especie': list(contagem_por_especie),  # Lista com contagem por espécie
    }

    return {
        'metrics': metrics,
        'detalhes_processos': processos_detalhados,
    }




from django.utils.timezone import now

def get_process_gamification_metrics(user):
    """
    Calcula a gamificação baseada nos processos concluídos no prazo e fora do prazo.
    Inclui contagem por espécie com pesos específicos.
    """
    # Filtra os processos concluídos do usuário
    completed_processes = Processo.objects.filter(usuario=user, concluido=True)

    # Inicializa variáveis
    points_no_prazo = 0
    points_fora_prazo = 0
    species_count = {}  # Contagem por espécie
    details = []

    # Dicionário de pesos específicos para cada espécie
    species_weights = {
        "LIM": 5,  # Exemplo: 'Liminar' tem peso 5
        "OUTROS": 1,
        "RED": 3,
        "RCL": 2,
        "RAI": 3,
        "RAC": 2,
        "QN": 1,
        "PV": 2,
        "PET": 1,
        "MS": 1,
        "HC": 2,
        "CC": 3,
        "AR": 2,
        "ADI": 4,
        "AGR I": 4,  # Exemplo: 'Agravo Interno' tem peso 4
    }

    for process in completed_processes:
        # Contabiliza espécie
        sigla_especie = process.especie.sigla if process.especie else "Sem Sigla"
        species_count[sigla_especie] = species_count.get(sigla_especie, 0) + 1

        # Obtém o peso da espécie, com valor padrão 1 se não estiver no dicionário
        weight = species_weights.get(sigla_especie, 1)

        if process.dt_conclusao and process.dt_prazo:
            # Verifica se foi concluído no prazo
            if process.dt_conclusao <= process.dt_prazo:
                points_no_prazo += 1.5 * weight  # Pontos com peso da espécie
                status = "No Prazo"
            else:
                points_fora_prazo += 1 * weight  # Pontos com peso da espécie
                status = "Fora do Prazo"

            # Adiciona detalhes para o template
            details.append({
                'numero_processo': process.numero_processo,
                'prazo': process.dt_prazo,
                'data_conclusao': process.dt_conclusao,
                'status': status,
                'points': 1.5 * weight if status == "No Prazo" else 1 * weight,
                'especie': sigla_especie,
            })

    total_points = points_no_prazo + points_fora_prazo

    return {
        'points': total_points,
        'points_no_prazo': points_no_prazo,
        'points_fora_prazo': points_fora_prazo,
        'details': details,
        'species_count': species_count,  # Adiciona contagem por espécie
    }






User = get_user_model()

def get_top_users_by_xp():
    """
    Calcula a gamificação para todos os usuários e retorna os 3 com mais pontos.
    Inclui contagem por espécie com pesos específicos.
    """
    all_users_data = []

    # Dicionário de pesos específicos para cada espécie
    species_weights = {
        "LIM": 5,  # Exemplo: 'Liminar' tem peso 5
        "OUTROS": 1,
        "RED": 3,
        "RCL": 2,
        "RAI": 3,
        "RAC": 2,
        "QN": 1,
        "PV": 2,
        "PET": 1,
        "MS": 1,
        "HC": 2,
        "CC": 3,
        "AR": 2,
        "ADI": 4,
        "AGR I": 4,  # Exemplo: 'Agravo Interno' tem peso 4
    }

    for user in User.objects.all():
        # Filtra os processos concluídos do usuário
        completed_processes = Processo.objects.filter(usuario=user, concluido=True)

        points = 0
        species_count = {}

        for process in completed_processes:
            # Contabiliza espécie
            sigla_especie = process.especie.sigla if process.especie else "Sem Sigla"
            species_count[sigla_especie] = species_count.get(sigla_especie, 0) + 1

            # Obtém o peso da espécie
            weight = species_weights.get(sigla_especie, 1)  # Peso padrão 1 caso a espécie não esteja no dicionário

            if process.dt_conclusao and process.dt_prazo:
                # Verifica se foi concluído no prazo
                if process.dt_conclusao <= process.dt_prazo:
                    points += 1.5 * weight  # Pontos com peso da espécie
                else:
                    points += 1 * weight  # Pontos com peso da espécie

        # Adiciona o usuário e seus pontos à lista
        all_users_data.append({
            'user': user,
            'name': user.get_full_name(),
            'photo': user.profile.photo.url if hasattr(user, 'profile') and user.profile.photo else '',
            'points': points,
            'species_count': species_count,  # Contagem por espécie
        })

    # Ordena os usuários pelo total de pontos em ordem decrescente e pega os 3 primeiros
    top_users = sorted(all_users_data, key=lambda x: x['points'], reverse=True)[:3]

    return top_users

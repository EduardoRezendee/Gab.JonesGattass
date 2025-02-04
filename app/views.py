from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .metrics import get_process_metrics, get_process_gamification_metrics, get_top_users_by_xp
from processos.models import Processo
from processos.models import TarefaDoDia  # Importe o modelo de TarefaDoDia

@login_required(login_url='login')
def home(request):
    user = request.user

    # Obtém as métricas gerais
    process_metrics = get_process_metrics(user)
    process_gamification = get_process_gamification_metrics(user)
    top_users = get_top_users_by_xp()  # Obtém o Top 3 usuários com mais pontos
    tarefas_do_dia = TarefaDoDia.objects.filter(usuario=request.user)

    # Processos não concluídos atribuídos ao usuário
    processos_nao_concluidos = Processo.objects.filter(usuario=user, concluido=False)

    # Adiciona 'pk' ao processo detalhado, garantindo que não haverá erros no link
    processos_detalhados = []
    for processo in processos_nao_concluidos:
        ultimo_andamento = processo.andamentos.order_by('-dt_criacao').first()
        processos_detalhados.append({
            'pk': processo.pk,
            'numero_processo': processo.numero_processo,
            'especie': processo.especie.especie if processo.especie else "Sem espécie",
            'sigla': processo.especie.sigla if processo.especie else "Sem sigla",
            'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else "Sem fase",
            'status_atual': ultimo_andamento.status.status if ultimo_andamento and ultimo_andamento.status else "Sem status",
            'data_prazo': processo.dt_prazo,
            'data_dist': processo.data_dist,
        })

    # Processos no "Meu Dia"
    tarefas_do_dia = TarefaDoDia.objects.filter(usuario=user)
    tarefas_ids = tarefas_do_dia.values_list('processo__id', flat=True)  # IDs dos processos no "Meu Dia"

    # Verifica se o usuário tem uma foto no perfil
    photo_url = user.profile.photo.url if hasattr(user, 'profile') and user.profile.photo else '/static/default-profile.png'

    # Contexto para o template
    context = {
        'user': user,
        'process_metrics': process_metrics,
        'process_gamification': process_gamification,
        'top_users': top_users,  # Inclui o Top 3 no contexto
        'photo_url': photo_url,
        'processos_nao_concluidos': processos_detalhados,  # Processos detalhados com pk incluso
        'tarefas_ids': list(tarefas_ids),  # IDs dos processos no "Meu Dia"
        "tarefas_do_dia": tarefas_do_dia,
    }

    return render(request, 'home.html', context)

from .metrics import get_process_metrics, get_process_gamification_metrics, get_top_users_by_xp
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from processos.models import Processo, ProcessoAndamento, TarefaDoDia
from accounts.models import UserProfile

@login_required(login_url='login')
def home(request):
    user = request.user

    is_revisor = UserProfile.objects.filter(user=user, funcao="revisor(a)").exists()

    andamento_metrics = []
    if is_revisor:
        processos_em_revisao = Processo.objects.filter(
            andamentos__fase__fase="Revisão",
            andamentos__usuario=user,
            concluido=False
        ).distinct().select_related('especie', 'usuario')

        for processo in processos_em_revisao:
            ultimo_andamento = processo.andamentos.filter(
                fase__fase="Revisão", 
                usuario=user, 
                status__status__in=["Não iniciado", "Em andamento"]
            ).order_by('-dt_criacao').first()

            if ultimo_andamento:
                especie_nome = processo.especie.especie if processo.especie else "Sem espécie"
                sigla_especie = processo.especie.sigla if processo.especie else ""

                andamento_metrics.append({
                    'pk': processo.pk,
                    'numero_processo': processo.numero_processo,
                    'data_dist': processo.data_dist,
                    'dias_no_gabinete': processo.dias_no_gabinete(),
                    'fase': ultimo_andamento.fase.fase if ultimo_andamento else "Sem fase",
                    'descricao': ultimo_andamento.andamento if ultimo_andamento else "Sem descrição",
                    'status': ultimo_andamento.status.status if ultimo_andamento and ultimo_andamento.status else "Sem status",
                    'data_inicio': ultimo_andamento.dt_inicio if ultimo_andamento else None,
                    'data_conclusao': ultimo_andamento.dt_conclusao if ultimo_andamento else None,
                    'link_doc': ultimo_andamento.link_doc if ultimo_andamento else None,
                    'usuario_processo': processo.usuario.get_full_name() if processo.usuario else "Não atribuído",
                    'especie': especie_nome,  # 🆕 Adicionado nome da espécie
                    'sigla_especie': sigla_especie  # 🆕 Adicionado sigla da espécie
                })

        # 🔹 Ordena para que os processos "Liminar" fiquem no topo
        andamento_metrics.sort(key=lambda p: (0 if p['especie'] == "Liminar" else 1, p['data_dist']))


    processos_detalhados = []
    if not is_revisor:
        processos_nao_concluidos = Processo.objects.filter(usuario=user, concluido=False).select_related('especie', 'usuario')

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
                'usuario_processo': processo.usuario.get_full_name() if processo.usuario else "Não atribuído"
            })

    tarefas_do_dia = TarefaDoDia.objects.filter(usuario=user)
    tarefas_ids = tarefas_do_dia.values_list('processo__id', flat=True)

    photo_url = user.profile.photo.url if hasattr(user, 'profile') and user.profile.photo else '/static/default-profile.png'

    process_metrics = get_process_metrics(user)
    process_gamification = get_process_gamification_metrics(user)
    top_users = get_top_users_by_xp()

    context = {
        'user': user,
        'is_revisor': is_revisor,
        'andamento_metrics': andamento_metrics,
        'process_metrics': process_metrics,
        'process_gamification': process_gamification,
        'top_users': top_users,
        'photo_url': photo_url,
        'processos_nao_concluidos': processos_detalhados,
        'tarefas_ids': list(tarefas_ids),
        "tarefas_do_dia": tarefas_do_dia,
    }

    return render(request, 'home.html', context)

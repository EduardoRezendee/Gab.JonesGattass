from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from processos.models import Processo, ProcessoAndamento, TarefaDoDia, ComentarioProcesso
from accounts.models import UserProfile
from .metrics import get_process_metrics, get_process_gamification_metrics, get_top_users_by_xp
from django.utils import timezone

@login_required(login_url='login')
def home(request):
    user = request.user
    is_revisor = UserProfile.objects.filter(user=user, funcao="revisor(a)").exists()
    is_desembargadora = UserProfile.objects.filter(user=user, funcao="Desembargadora").exists()

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
            ).order_by('-dt_criacao').select_related('fase', 'status').first()
            if ultimo_andamento:
                especie_nome = processo.especie.especie if processo.especie else "Sem espécie"
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
                    'usuario_processo': processo.usuario.get_full_name(),
                    'especie': especie_nome,
                    'sigla_especie': processo.especie.sigla,
                })
        andamento_metrics.sort(key=lambda p: (0 if p['especie'] == "Liminar" else 1, p['data_dist']))

    elif is_desembargadora:
        processos_em_revisao_desa = Processo.objects.filter(
            andamentos__fase__fase="Revisão Desa",
            andamentos__usuario=user,
            concluido=False
        ).distinct().select_related('especie', 'usuario')
        for processo in processos_em_revisao_desa:
            ultimo_andamento = processo.andamentos.filter(
                fase__fase="Revisão Desa",
                usuario=user,
                status__status__in=["Não iniciado", "Em andamento"]
            ).order_by('-dt_criacao').select_related('fase', 'status').first()
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
                    'fase': ultimo_andamento.fase.fase,
                    'descricao': ultimo_andamento.andamento,
                    'status': ultimo_andamento.status.status,
                    'data_inicio': ultimo_andamento.dt_inicio,
                    'data_conclusao': ultimo_andamento.dt_conclusao,
                    'link_doc': ultimo_andamento.link_doc,
                    'usuario_processo': processo.usuario.get_full_name(),
                    'especie': especie_nome,
                    'sigla_especie': processo.especie.sigla,
                    'comentarios': [{'texto': c.texto, 'data_criacao': c.data_criacao, 'usuario': c.usuario.get_full_name()} for c in comentarios],
                    'revisoes_desa': revisoes_desa_count,
                })
        andamento_metrics.sort(key=lambda p: (0 if p['especie'] == "Liminar" else 1, -(p['dias_no_gabinete'] or 0)))

    processos_detalhados = []
    active_tab = None
    if not is_revisor and not is_desembargadora:
        processos_nao_concluidos = Processo.objects.filter(usuario=user, concluido=False).select_related('especie', 'usuario')
        for processo in processos_nao_concluidos:
            ultimo_andamento = processo.andamentos.order_by('-dt_criacao').select_related('fase', 'status').first()
            if ultimo_andamento and processo.pk:
                processos_detalhados.append({
                    'pk': processo.pk,
                    'andamento_pk': ultimo_andamento.pk,
                    'andamento_link_doc': ultimo_andamento.link_doc,
                    'numero_processo': processo.numero_processo,
                    'especie': processo.especie.especie,
                    'sigla': processo.especie.sigla,
                    'fase_atual': ultimo_andamento.fase.fase,
                    'status_atual': ultimo_andamento.status.status,
                    'data_prazo': processo.dt_prazo,
                    'data_dist': processo.data_dist,
                    'dias_no_gabinete': processo.dias_no_gabinete() or 0,
                    'usuario_processo': processo.usuario.get_full_name(),
                    'comentarios': ComentarioProcesso.objects.filter(processo=processo).values('texto', 'data_criacao', 'usuario__first_name', 'usuario__last_name'),
                })
        processos_detalhados.sort(key=lambda p: (0 if p['especie'] == "Liminar" else 1, -(p['dias_no_gabinete'] or 0)))

        fixed_phase_order = ['Elaboração', 'Revisão', 'Correção', 'Revisão Desa', 'Devolvido', 'L. PJE']
        phase_dict = {proc['fase_atual']: [proc] for proc in processos_detalhados if proc['fase_atual']}
        fases = [(phase, phase_dict.get(phase, [])) for phase in fixed_phase_order if phase in phase_dict]
        fase_param = request.GET.get('fase')
        active_tab = fase_param if fase_param in fixed_phase_order else fases[0][0] if fases else None

    tarefas_do_dia = TarefaDoDia.objects.filter(usuario=user).select_related('processo')
    tarefas_detalhadas = []
    for tarefa in tarefas_do_dia:
        ultimo_andamento = tarefa.processo.andamentos.order_by('-dt_criacao').select_related('fase').first() if tarefa.processo else None
        tarefas_detalhadas.append({
            'id': tarefa.id,
            'processo': {
                'id': tarefa.processo.id if tarefa.processo else None,
                'numero_processo': tarefa.processo.numero_processo if tarefa.processo else "Sem número",
                'especie': tarefa.processo.especie.especie if tarefa.processo and tarefa.processo.especie else "Sem espécie",
                'fase_atual': ultimo_andamento.fase.fase if ultimo_andamento else "Sem fase",
                'data_dist': tarefa.processo.data_dist if tarefa.processo else None,
                'dias_no_gabinete': tarefa.processo.dias_no_gabinete() if tarefa.processo else 0,
                'dt_prazo': tarefa.processo.dt_prazo if tarefa.processo else None,
                'andamento_pk': ultimo_andamento.pk if ultimo_andamento else None,
                'andamento_link_doc': ultimo_andamento.link_doc if ultimo_andamento else None,
                'andamento': ultimo_andamento,
                'comentarios': ComentarioProcesso.objects.filter(processo=tarefa.processo).values('texto', 'data_criacao', 'usuario__first_name', 'usuario__last_name') if tarefa.processo else [],
            }
        })
    tarefas_ids = [tarefa['processo']['id'] for tarefa in tarefas_detalhadas if tarefa['processo']['id']]

    process_metrics = get_process_metrics(user)
    if not is_revisor and not is_desembargadora:
        process_metrics['detalhes_processos'] = processos_detalhados

    photo_url = user.profile.photo.url if hasattr(user, 'profile') and user.profile.photo else '/static/default-profile.png'
    process_gamification = get_process_gamification_metrics(user)
    top_users = get_top_users_by_xp()

    return render(request, 'home.html', {
        'user': user,
        'is_revisor': is_revisor,
        'is_desembargadora': is_desembargadora,
        'andamento_metrics': andamento_metrics,
        'process_metrics': process_metrics,
        'process_gamification': process_gamification,
        'top_users': top_users,
        'photo_url': photo_url,
        'tarefas_ids': tarefas_ids,
        'tarefas_do_dia': tarefas_detalhadas,
        'fases': fases if not is_revisor and not is_desembargadora else None,
        'active_tab': active_tab,
        'today': timezone.now().date(),
    })

from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from django.contrib import messages

class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'change_password.html'
    success_url = reverse_lazy('home')

    def form_valid(self, form):
        messages.success(self.request, 'Sua senha foi alterada com sucesso!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Erro ao alterar a senha. Verifique os campos.')
        return super().form_invalid(form)
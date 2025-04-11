from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from .forms import ProcessoForm, AndamentoForm, ComentarioProcessoForm
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import datetime, timedelta
from calendar import month_name
from .models import Processo, Fase, Status, Camara, Tipo, Especie, TarefaDoDia, ProcessoAndamento, Fase, Resultado, Tema
import locale
from calendar import month_name
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils.timezone import make_aware
import openpyxl
from django.http import HttpResponse
from django.shortcuts import render
from .metrics import get_advanced_metrics
from accounts.models import UserProfile
from django.urls import reverse
from django.utils.timezone import now
from django.views import View
from django.db.models import Subquery, OuterRef
from django.contrib import messages


locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')

def definir_tema(request, pk):
    """Processa o formulário do modal e define/atualiza o Tema do Processo."""
    processo = get_object_or_404(Processo, pk=pk)
    
    if request.method == 'POST':
        tema_id = request.POST.get('tema_id')
        if tema_id:
            tema = get_object_or_404(Tema, pk=tema_id)
            processo.tema = tema
            processo.save()
            messages.success(request, "Tema atualizado com sucesso!")
        else:
            messages.error(request, "Selecione um tema válido.")
        return redirect('processo_list')  # Ajuste para onde você quer voltar
    
    return redirect('processo_list')

class ProcessoListView(LoginRequiredMixin, ListView):
    model = Processo
    template_name = 'processo_list.html'
    context_object_name = 'processos'
    paginate_by = 20

    def get_queryset(self):
        """
        Filtra os processos com base nos parâmetros fornecidos na URL.
        """
        queryset = Processo.objects.all()

        # 🔹 Captura filtros da URL
        despacho = self.request.GET.get('despacho')
        prioridade = self.request.GET.get('prioridade')
        status = self.request.GET.get('status', "").strip().lower() or "pendente"
        fase_atual = self.request.GET.get('fase_atual')
        camara = self.request.GET.get('camara')
        tipo = self.request.GET.get('tipo')
        especie = self.request.GET.get('especie')
        numero_processo = self.request.GET.get('numero_processo')
        meus_processos = self.request.GET.get('meus_processos', None)
        user_id = self.request.GET.get('user_id')

        tema = self.request.GET.get('tema')

        # 🔹 Filtra corretamente o status antes da ordenação
        if status == "concluído":
            queryset = queryset.filter(concluido=True)
        else:
            queryset = queryset.filter(concluido=False)

        # 🔹 Obtém a última fase ativa do processo (excluindo fases concluídas)
        latest_fase = Subquery(
            ProcessoAndamento.objects.filter(
                processo=OuterRef('id'),
                status__status__in=["Em andamento", "Não iniciado"]  # 🔹 Garante que só pega fases ativas
            ).order_by('-dt_criacao').values('fase__fase')[:1]
        )

        queryset = queryset.annotate(fase_atual=latest_fase).filter(fase_atual__isnull=False)

        # 🔹 Aplicar filtros específicos
        filtros = {
            'fase_atual': fase_atual,
            'camara__camara': camara,
            'tipo__tipo': tipo,
            'especie__especie': especie,
            'numero_processo__icontains': numero_processo,
        }
        if tema:
            # Exemplo: filtrar pelo nome do tema
            filtros['tema__nome'] = tema
            # Se preferir filtrar por ID, troque por: filtros['tema__id'] = tema

        for campo, valor in filtros.items():
            if valor:
                queryset = queryset.filter(**{campo: valor})

        # 🔹 Filtrar processos apenas do usuário logado (se opção estiver ativada)
        if meus_processos == 'on':
            queryset = queryset.filter(usuario=self.request.user)

        # 🔹 Filtrar por usuário específico
        if user_id:
            queryset = queryset.filter(usuario__id=user_id)

        # 🔹 Filtragem por datas (se aplicável)
        data_filtros = {
            'data_dist': 'data_dist',
            'data_prazo': 'dt_prazo',
            'data_julgamento': 'dt_julgamento',
        }

        for param, field in data_filtros.items():
            valor = self.request.GET.get(param)
            if valor:
                queryset = queryset.filter(**{f"{field}__date": datetime.strptime(valor, '%Y-%m-%d').date()})

         # 🔹 Aplicar os filtros de despacho e prioridade
        if despacho == 'sim':
            queryset = queryset.filter(despacho=True)
        if prioridade == 'sim':
            queryset = queryset.filter(prioridade_urgente=True)
        # 🔹 Captura o parâmetro de ordenação da URL, com padrão "mais_recente"
        order_by = self.request.GET.get("ordenar", "mais_recente")

        # 🔹 Aplica ordenação segura
        ordering_dict = {
            "mais_recente": "-data_dist",
            "mais_antigo": "data_dist",
        }

        if order_by in ordering_dict:
            queryset = queryset.order_by(ordering_dict[order_by])

        # 🔹 Ordenação por 'dias_no_gabinete' (realiza sorting manual)
        elif order_by in ["dias_gabinete_recente", "dias_gabinete_antigo"]:
            queryset_list = list(queryset)
            reverse = order_by == "dias_gabinete_recente"
            queryset_list.sort(key=lambda p: p.dias_no_gabinete() or 0, reverse=reverse)
            return queryset_list

        return queryset

    def get_context_data(self, **kwargs):
        """
        Adiciona dados adicionais ao contexto do template.
        """
        context = super().get_context_data(**kwargs)

        # Captura o status da requisição ou define "Pendente" como padrão
        status_atual = self.request.GET.get('status', 'pendente')

        # Opções de ordenação
        context["ordenacao_opcoes"] = [
            {"valor": "mais_recente", "label": "Mais Recente"},
            {"valor": "mais_antigo", "label": "Mais Antigo"},
            {"valor": "dias_gabinete_recente", "label": "Mais Tempo no Gabinete"},
            {"valor": "dias_gabinete_antigo", "label": "Menos Tempo no Gabinete"},
        ]

        # Usuários ordenados
        context['users'] = User.objects.filter(
            id__in=Processo.objects.values_list('usuario_id', flat=True)
        ).select_related('profile').order_by('first_name', 'last_name')

        # Adiciona filtros para os campos relacionados
        context['statuses'] = ["Em andamento", "Não iniciado", "Concluído", "Pendente"]
        context['status_selecionado'] = status_atual
        context['fases'] = Fase.objects.exclude(fase="Concluído").values_list('fase', flat=True)
        context['camaras'] = Camara.objects.all()
        context['tipos'] = Tipo.objects.all()
        context['especies'] = Especie.objects.all()
        context['temas'] = Tema.objects.all()

        # Captura o tema selecionado para manter no dropdown
        context['tema_selecionado'] = self.request.GET.get('tema', '')

        # 🔹 Adiciona tarefas do dia do usuário
        tarefas = TarefaDoDia.objects.filter(usuario=self.request.user)
        context['tarefas_do_dia'] = tarefas
        context['tarefas_do_dia_ids'] = list(tarefas.values_list('processo__id', flat=True))
        context['despacho_selecionado'] = self.request.GET.get('despacho', 'nao')
        context['prioridade_selecionada'] = self.request.GET.get('prioridade', 'nao')

        # 🔹 Adiciona métricas de processos por usuário
        metrics_data = get_advanced_metrics()
        context["assessor_process_data"] = {
            item["id"]: item for item in metrics_data["assessor_process_data"]

        
        }

        return context

class ProcessoCreateView(CreateView):
    model = Processo
    form_class = ProcessoForm
    template_name = 'processo_form.html'  # sem extends, apenas o corpo do form
    success_url = reverse_lazy('processo_list')

    def form_invalid(self, form):
        """
        Se o formulário for inválido (erro de validação),
        retorne novamente o HTML do form (template) para exibir os erros dentro do modal.
        """
        # Basta fazer um render normal do template
        return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        """
        Se o formulário for válido, salve e retorne algo que indique 'sucesso' para o Ajax.
        """
        super().form_valid(form)
        # Aqui podemos retornar, por exemplo, apenas um status 204 (no content)
        return HttpResponse('', status=204)
        # ou um JsonResponse({'msg': 'criado com sucesso!'}, status=200)


class ProcessoDetailView(LoginRequiredMixin, DetailView):
    model = Processo
    template_name = 'processo_detail.html'
    context_object_name = 'processo'


class ProcessoUpdateView(LoginRequiredMixin, UpdateView):
    model = Processo
    form_class = ProcessoForm
    template_name = 'processo_form_update.html'
    success_url = reverse_lazy('processo_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Adiciona o usuário logado
        return kwargs


class ProcessoDeleteView(LoginRequiredMixin, DeleteView):
    model = Processo
    template_name = 'processo_confirm_delete.html'
    success_url = reverse_lazy('processo_list')


class AndamentoListView(LoginRequiredMixin, ListView):
    template_name = 'andamento_list.html'
    context_object_name = 'andamentos'

    def get_queryset(self):
        """
        Retorna os andamentos relacionados ao processo atual, com validação de ID.
        """
        processo_id = self.request.GET.get('processo')
        if not processo_id or not processo_id.isdigit():
            raise Http404("Processo inválido ou não encontrado.")
        
        return ProcessoAndamento.objects.filter(processo_id=processo_id).select_related('fase', 'usuario', 'status')

    def get_context_data(self, **kwargs):
        """
        Adiciona informações adicionais ao contexto, excluindo a fase 'Processo Concluído'.
        """
        context = super().get_context_data(**kwargs)

        processo_id = self.request.GET.get('processo')
        if not processo_id or not processo_id.isdigit():
            raise Http404("Processo inválido ou não encontrado.")

        # Busca o processo
        processo = get_object_or_404(Processo, pk=processo_id)

        # Exclui a fase "Processo Concluído"
        fases = Fase.objects.exclude(fase="Processo Concluído")

        # Organiza os andamentos por fase
        andamentos_por_fase = [
            {
                'fase': fase,
                'nao_iniciado_em_andamento': self.get_queryset().filter(fase=fase).exclude(status__status="Concluído"),
                'concluidos': self.get_queryset().filter(fase=fase, status__status="Concluído"),
            }
            for fase in fases
        ]

        # Criar o formulário com os dados do processo
        form = ProcessoForm(instance=processo)

        # Carregar opções corretamente para os dropdowns
        form.fields["tipo"].queryset = Tipo.objects.all()
        form.fields["resultado"].queryset = Resultado.objects.all()

        # DEBUG: Verifique se os valores estão sendo carregados corretamente
        print(f"Tipo Selecionado: {processo.tipo}, Resultado Selecionado: {processo.resultado}")

        # Atualiza o contexto com os dados do processo, andamentos e formulário
        context.update({
            'processo': processo,
            'andamentos_por_fase': andamentos_por_fase,
            'form': form,
        })
        return context

class ProcessoPartialUpdateView(View):
    def post(self, request, processo_id):
        processo = get_object_or_404(Processo, id=processo_id)

        tipo_id = request.POST.get("tipo")
        resultado_id = request.POST.get("resultado")

        # Verifica se os campos foram enviados corretamente
        if not tipo_id or not resultado_id:
            return JsonResponse({'error': 'Campos obrigatórios não foram enviados'}, status=400)

        # Converte os IDs para instâncias reais do modelo
        tipo = get_object_or_404(Tipo, id=tipo_id)
        resultado = get_object_or_404(Resultado, id=resultado_id)

        # Atualiza os valores no processo
        processo.tipo = tipo
        processo.resultado = resultado
        processo.save()

        print(f"✅ Processo atualizado - Tipo: {processo.tipo}, Resultado: {processo.resultado}")  # DEBUG

        # 🔹 Redirecionar para a página correta com o objeto atualizado
        return redirect(f'/andamentos/?processo={processo.id}')
    

class ProcessoUpdateView(LoginRequiredMixin, UpdateView):
    model = Processo
    form_class = ProcessoForm
    template_name = 'processo_form_update.html'
    success_url = reverse_lazy('processo_list')

    # Passa o usuário logado para o formulário
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user  # Adiciona o usuário logado
        return kwargs


from django.http import Http404


class AndamentoCreateView(LoginRequiredMixin,CreateView):
    model = ProcessoAndamento
    form_class = AndamentoForm
    template_name = 'andamento_form.html'
    success_url = reverse_lazy('andamento_list')


class AndamentoUpdateView(LoginRequiredMixin, UpdateView):
    model = ProcessoAndamento
    form_class = AndamentoForm
    template_name = 'andamento_form_update.html'

    def get_success_url(self):
        # Obtém o parâmetro 'origem' do formulário (pode ser 'home' ou 'andamento_list')
        origem = self.request.POST.get('origem', 'andamento_list')  # Default para 'andamento_list'

        # Obtém o processo associado ao andamento
        processo_id = self.object.processo.id

        # Define a URL de redirecionamento com base na origem
        if origem == 'home':
            return reverse('home')
        else:
            # Redireciona para a URL da lista de andamentos, incluindo o parâmetro 'processo'
            return f"{reverse('andamento_list')}?processo={processo_id}"

    def get_context_data(self, **kwargs):
        # Adiciona o objeto andamento ao contexto para evitar erro no template
        context = super().get_context_data(**kwargs)
        context["andamento"] = self.object
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Verifica se a ação é para iniciar o andamento
        if 'iniciar_andamento' in request.POST:
            if not self.object.dt_inicio:  # Evita reiniciar um andamento já iniciado
                self.object.dt_inicio = now()
                self.object.status = Status.objects.get(status="Em andamento")
                self.object.save()
            return redirect(self.get_success_url())
        
        # Verifica se a ação é para enviar para outra fase
        if 'enviar_para_fase' in request.POST:
            nova_fase = request.POST.get('nova_fase')
            if nova_fase:
                self.object.concluir_andamento()
                nova_fase_obj = Fase.objects.get(fase=nova_fase)
                ProcessoAndamento.objects.create(
                    processo=self.object.processo,
                    andamento=f"Movido para {nova_fase}",
                    fase=nova_fase_obj,
                    usuario=request.user,
                    status=Status.objects.get(status="Não iniciado")
                )
            return redirect(self.get_success_url())
        
        # Processa o formulário padrão (atualização via UpdateView)
        response = super().post(request, *args, **kwargs)
        return response




class AndamentoDeleteView(LoginRequiredMixin,DeleteView):
    model = ProcessoAndamento
    template_name = "andamento_confirm_delete.html"

    def get_success_url(self):
        """
        Redireciona para a lista de andamentos do processo atual após a exclusão.
        """
        processo_id = self.object.processo.id  # Obtém o ID do processo relacionado
        return reverse('andamento_list') + f'?processo={processo_id}'



class AndamentoIniciarView(LoginRequiredMixin,UpdateView):
    def post(self, request, pk, *args, **kwargs):
        andamento = get_object_or_404(ProcessoAndamento, pk=pk)
        if not andamento.dt_inicio:  # Verifica se o andamento ainda não foi iniciado
            andamento.dt_inicio = now()
            andamento.status = Status.objects.get(status="Em andamento")  # Atualiza o status
            andamento.save()
        return redirect(reverse('andamento_update', kwargs={'pk': pk}))


class AndamentoEnviarParaFaseView(LoginRequiredMixin, UpdateView):
    def post(self, request, pk, *args, **kwargs):
        andamento = get_object_or_404(ProcessoAndamento, pk=pk)
        nova_fase = request.POST.get('nova_fase')
        origem = request.POST.get('origem', 'home')  # Padrão para 'home' se não fornecido

        # Finaliza o andamento atual
        andamento.dt_conclusao = now()
        andamento.status = Status.objects.get(status="Concluído")
        andamento.save()

        # Identifica o responsável baseado na fase
        usuario_responsavel = andamento.processo.usuario  # Usuário padrão (do processo)
        if nova_fase == "Revisão":
            usuario_responsavel = UserProfile.objects.filter(funcao="revisor(a)").first().user
        elif nova_fase == "Revisão Des":
            usuario_responsavel = UserProfile.objects.filter(funcao="Desembargador").first().user

        # Cria o novo andamento
        nova_fase_obj = get_object_or_404(Fase, fase=nova_fase)
        ProcessoAndamento.objects.create(
            processo=andamento.processo,
            andamento=f"Movido para {nova_fase}",
            fase=nova_fase_obj,
            usuario=usuario_responsavel,
            status=Status.objects.get(status="Não iniciado"),
            link_doc=andamento.link_doc  # Copia o link do documento
        )

        # Redireciona para a página de origem
        if origem == "andamento_list":
            return redirect(reverse('andamento_list') + f"?processo={andamento.processo.pk}")
        else:  # Inclui 'home' e qualquer outro caso
            return redirect('home')


class AndamentoConcluirProcessoView(LoginRequiredMixin, UpdateView):
    def post(self, request, pk, *args, **kwargs):
        andamento = get_object_or_404(ProcessoAndamento, pk=pk)
        
        # Finaliza o andamento atual
        andamento.dt_conclusao = now()
        andamento.status = Status.objects.get(status="Concluído")
        andamento.save()

        # Marca o processo como concluído e define a data de conclusão
        processo = andamento.processo
        processo.concluido = True
        processo.dt_atualizacao = now()
        processo.dt_conclusao = now()
        processo.save()

        # **Corrigir a fase do andamento "Processo concluído"**
        fase_concluido, _ = Fase.objects.get_or_create(fase="Processo Concluído")

        # Criar um novo andamento indicando que o processo foi concluído na fase correta
        novo_andamento = ProcessoAndamento.objects.create(
            processo=processo,
            andamento="Processo concluído",
            fase=fase_concluido, 
            usuario=request.user,
            status=Status.objects.get(status="Concluído"),
            dt_inicio=now(),
            dt_conclusao=now()
        )

        # Obtém o parâmetro 'origem' do formulário (pode ser 'home' ou 'andamento_list')
        origem = request.POST.get('origem', 'andamento_list')  # Default para 'andamento_list' se não especificado

        # Define a URL de redirecionamento com base na origem
        if origem == 'home':
            url = reverse('home')
        else:
            url = reverse('andamento_list') + f"?processo={andamento.processo.pk}"

        return redirect(url)



def process_metrics_view(request):

    # Obtém os filtros da URL
    assessor = request.GET.get('assessor')
    mes_distribuicao = request.GET.get('mes_distribuicao')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    status = request.GET.get('status')
    numero_processo = request.GET.get('numero_processo')

    # Converte strings de data para objetos datetime (se fornecidos)
    if data_inicio:
        data_inicio = make_aware(datetime.strptime(data_inicio, "%Y-%m-%d"))
    if data_fim:
        data_fim = make_aware(datetime.strptime(data_fim, "%Y-%m-%d"))

    # Obtém os dados de métricas
    metrics_data = get_advanced_metrics(
        assessor=assessor, 
        mes_distribuicao=mes_distribuicao, 
        data_inicio=data_inicio, 
        data_fim=data_fim,
        status=status,
        numero_processo=numero_processo
    )

    # Lista de meses disponíveis para filtro
    months = [(i, month_name[i]) for i in range(1, 13)]

    # Lista de assessores distintos
    assessores = Processo.objects.values('usuario__id', 'usuario__first_name', 'usuario__last_name').distinct()

    # Passa os dados ao template
    return render(request, 'metrics.html', {
        # Dados de gráficos com quantidade e porcentagem
        "species_data": metrics_data["species_data"],    
        "type_data": metrics_data["type_data"],          
        "camara_data": metrics_data["camara_data"],      
        "resultado_data": metrics_data["resultado_data"],
        "assessor_data": metrics_data["assessor_data"],  
        "total_processos": metrics_data["total_processos"],
        "total_concluidos": metrics_data["total_concluidos"],
        "total_pendentes": metrics_data["total_pendentes"],
        "andamento_data": metrics_data["andamento_data"],
        "porcentagem_concluidos": metrics_data["porcentagem_concluidos"],
        "porcentagem_pendentes": metrics_data["porcentagem_pendentes"],

        # Métricas adicionais
        "average_process_time": metrics_data["average_process_time"], 
        "andamento_durations": metrics_data["andamento_durations"],  
        "andamento_waiting_times": metrics_data["andamento_waiting_times"], 

        # **Novo**: Lista de processos detalhados
        "detalhes_processos": metrics_data["detalhes_processos"],

        # 🔹 **Corrigido**: Passando os dados dos assessores corretamente
        "assessor_process_data": metrics_data["assessor_process_data"],  

        "months": months,
        "assessores": assessores,
        "filtros": {
            "data_inicio": request.GET.get('data_inicio', ''),
            "data_fim": request.GET.get('data_fim', ''),
            "status": request.GET.get('status', ''),
            "numero_processo": request.GET.get('numero_processo', '')
        }
    })


@login_required
def adicionar_tarefa(request, processo_id):
    processo = get_object_or_404(Processo, id=processo_id)
    TarefaDoDia.objects.get_or_create(usuario=request.user, processo=processo)

    # Obtém o parâmetro 'origem' do formulário (pode ser 'home' ou 'processo_list')
    origem = request.POST.get('origem', 'processo_list')  # Default para 'processo_list' se não especificado

    # Captura os parâmetros da URL para manter os filtros
    query_params = request.GET.copy()
    query_params.pop('page', None)  # Remove paginação para evitar problemas

    # Define a URL de redirecionamento com base na origem
    if origem == 'home':
        url = reverse('home')
    else:
        url = reverse('processo_list')

    # Adiciona os parâmetros de query à URL, se existirem
    if query_params:
        return redirect(f"{url}?{query_params.urlencode()}")
    return redirect(url)

@login_required
def remover_tarefa(request, processo_id):
    processo = get_object_or_404(Processo, id=processo_id)
    TarefaDoDia.objects.filter(usuario=request.user, processo=processo).delete()

    # Obtém o parâmetro 'origem' do formulário (pode ser 'home' ou 'processo_list')
    origem = request.POST.get('origem', 'processo_list')  # Default para 'processo_list' se não especificado

    # Captura os parâmetros da URL para manter os filtros
    query_params = request.GET.copy()
    query_params.pop('page', None)  # Remove paginação para evitar problemas

    # Define a URL de redirecionamento com base na origem
    if origem == 'home':
        url = reverse('home')
    else:
        url = reverse('processo_list')

    # Adiciona os parâmetros de query à URL, se existirem
    if query_params:
        return redirect(f"{url}?{query_params.urlencode()}")
    return redirect(url)

def export_processos_xlsx(request):
    """Exporta os processos para um arquivo Excel (.xlsx)"""

    # Criar um novo workbook (arquivo Excel)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Processos"

    # Definir os cabeçalhos da planilha
    headers = [
        "Número do Processo", "Data de Distribuição", "Espécie", "Resultado", "Tipo",
        "Câmara", "Usuário Responsável", "Data de Julgamento", "Prazo", 
        "Data de Criação", "Última Atualização", "Concluído", "Data de Conclusão"
    ]
    ws.append(headers)

    # Buscar os processos no banco de dados
    processos = Processo.objects.all()

    # Adicionar os dados à planilha
    for processo in processos:
        ws.append([
            processo.numero_processo,
            processo.data_dist.strftime('%d/%m/%Y %H:%M') if processo.data_dist else "",
            processo.especie.especie if processo.especie else "",
            processo.resultado.resultado if processo.resultado else "",
            processo.tipo.tipo if processo.tipo else "",
            processo.camara.camara if processo.camara else "",
            f"{processo.usuario.first_name} {processo.usuario.last_name}" if processo.usuario else "Sem responsável",
            processo.dt_julgamento.strftime('%d/%m/%Y %H:%M') if processo.dt_julgamento else "",
            processo.dt_prazo.strftime('%d/%m/%Y %H:%M') if processo.dt_prazo else "",
            processo.dt_criacao.strftime('%d/%m/%Y %H:%M'),
            processo.dt_atualizacao.strftime('%d/%m/%Y %H:%M'),
            "Sim" if processo.concluido else "Não",
            processo.dt_conclusao.strftime('%d/%m/%Y %H:%M') if processo.dt_conclusao else ""
        ])

    # Criar a resposta HTTP com o arquivo Excel
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="processos.xlsx"'
    wb.save(response)

    return response

@login_required 
def adicionar_comentario(request, processo_id):
    """ Adiciona um comentário a um processo específico via AJAX """

    if not processo_id:
        return JsonResponse({"error": "ID do processo não fornecido."}, status=400)

    processo = get_object_or_404(Processo, id=processo_id)

    if request.method == "POST":

        form = ComentarioProcessoForm(request.POST)  # Atualizei para refletir o novo modelo
        if form.is_valid():
            comentario = form.save(commit=False)
            comentario.usuario = request.user
            comentario.processo = processo
            comentario.save()

            return JsonResponse({
                "id": comentario.id,
                "usuario": comentario.usuario.get_full_name(),
                "texto": comentario.texto,
                "data_criacao": comentario.data_criacao.strftime("%d/%m/%Y %H:%M")
            })

        else:
            return JsonResponse({"error": "Erro ao processar o formulário.", "erros": form.errors}, status=400)

    return JsonResponse({"error": "Método não permitido."}, status=405)


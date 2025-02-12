from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from .forms import ProcessoForm, AndamentoForm, ComentarioProcessoForm
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import datetime, timedelta
from calendar import month_name
from .models import Processo, Fase, Status, Camara, Tipo, Especie, TarefaDoDia, ProcessoAndamento, Fase
import locale
from calendar import month_name
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
import pandas as pd
from django.contrib import messages
from .forms import ExcelUploadForm
from django.utils.timezone import make_aware
import openpyxl
from django.http import HttpResponse
from django.shortcuts import render
from .metrics import get_advanced_metrics
from accounts.models import UserProfile
from django.urls import reverse
from django.utils.timezone import now
from django.db.models import Subquery, OuterRef, Exists


locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')

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

        # Captura o parâmetro de ordenação da URL
        order_by = self.request.GET.get('ordenar', 'data_dist')

        # 🔹 Garante uma ordenação segura
        ordering = {
            "mais_recente": "-data_dist",
            "mais_antigo": "data_dist",
            "antigo_recente": "-antigo",
            "antigo_antigo": "antigo",
        }.get(order_by, "-data_dist")  # Ordem padrão

        queryset = queryset.order_by(ordering)

        # Captura filtros da URL
        status = self.request.GET.get('status')
        fase_atual = self.request.GET.get('fase_atual')
        camara = self.request.GET.get('camara')
        tipo = self.request.GET.get('tipo')
        especie = self.request.GET.get('especie')
        numero_processo = self.request.GET.get('numero_processo')
        meus_processos = self.request.GET.get('meus_processos', None)
        user_id = self.request.GET.get('user_id')

        # Filtrar apenas processos NÃO concluídos quando status estiver vazio
        if status:
            status = status.strip().lower()
            if status == "concluído":
                queryset = queryset.filter(concluido=True)
            elif status == "pendente":
                queryset = queryset.filter(concluido=False)
        else:
            queryset = queryset.filter(concluido=False)  # Padrão: exclui concluídos

        # 🔹 **Filtrar apenas pela fase atual (último andamento do processo)**
        latest_fase = Subquery(
            ProcessoAndamento.objects.filter(
                processo=OuterRef('id')
            ).order_by('-dt_criacao').values('fase__fase')[:1]
        )
        queryset = queryset.annotate(fase_atual=latest_fase)

        # 🔹 **Filtrar SOMENTE por status "Em andamento" ou "Não iniciado"**
        andamento_existe = Exists(
            ProcessoAndamento.objects.filter(
                processo=OuterRef('id'),
                status__status__in=["Em andamento", "Não iniciado", "Concluído"]
            )
        )
        queryset = queryset.filter(andamento_existe)

        # Aplicar filtros específicos
        filtros = {
            'fase_atual': fase_atual,  # 🔹 Agora corretamente comparando com nome da fase
            'camara__camara': camara,
            'tipo__tipo': tipo,
            'especie__especie': especie,
            'numero_processo__icontains': numero_processo,
        }

        for campo, valor in filtros.items():
            if valor:
                queryset = queryset.filter(**{campo: valor})

        # Filtrar processos apenas do usuário logado (se opção estiver ativada)
        if meus_processos == 'on':
            queryset = queryset.filter(usuario=self.request.user)

        # Filtrar por usuário específico
        if user_id:
            queryset = queryset.filter(usuario__id=user_id)

        # 🔹 **Corrigido: Filtragem por datas**
        data_dist = self.request.GET.get('data_dist')
        data_prazo = self.request.GET.get('data_prazo')
        data_julgamento = self.request.GET.get('data_julgamento')

        if data_dist:
            queryset = queryset.filter(data_dist__date=datetime.strptime(data_dist, '%Y-%m-%d').date())
        if data_prazo:
            queryset = queryset.filter(dt_prazo__date=datetime.strptime(data_prazo, '%Y-%m-%d').date())
        if data_julgamento:
            queryset = queryset.filter(dt_julgamento__date=datetime.strptime(data_julgamento, '%Y-%m-%d').date())

        return queryset

    def get_context_data(self, **kwargs):
        """
        Adiciona dados adicionais ao contexto do template.
        """
        context = super().get_context_data(**kwargs)

        # Opções de ordenação
        context["ordenacao_opcoes"] = [
            {"valor": "mais_recente", "label": "Mais Recente"},
            {"valor": "mais_antigo", "label": "Mais Antigo"},
            {"valor": "antigo_recente", "label": "Mais Recente por Antiguidade"},
            {"valor": "antigo_antigo", "label": "Mais Antigo por Antiguidade"},
        ]

        # Usuários ordenados
        context['users'] = User.objects.select_related('profile').order_by('first_name', 'last_name')

        # Adiciona filtros para os campos relacionados
        context['statuses'] = ["Em andamento", "Não iniciado"]
        context['fases'] = Fase.objects.exclude(fase="Concluído").values_list('fase', flat=True)
        context['camaras'] = Camara.objects.all()
        context['tipos'] = Tipo.objects.all()
        context['especies'] = Especie.objects.all()

        # 🔹 **Adiciona tarefas do dia do usuário**
        tarefas = TarefaDoDia.objects.filter(usuario=self.request.user)
        context['tarefas_do_dia'] = tarefas
        context['tarefas_do_dia_ids'] = list(tarefas.values_list('processo__id', flat=True))

        # 🔹 **Adiciona métricas de processos por usuário**
        metrics_data = get_advanced_metrics()
        context["assessor_process_data"] = {
            item["id"]: item for item in metrics_data["assessor_process_data"]
        }

        return context


class ProcessoCreateView(LoginRequiredMixin, CreateView):
    model = Processo
    form_class = ProcessoForm
    template_name = 'processo_form.html'
    success_url = reverse_lazy('processo_list')


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

        processo = get_object_or_404(Processo, pk=processo_id)
        fases = Fase.objects.exclude(fase="Processo Concluído")

        andamentos_por_fase = [
            {
                'fase': fase,
                'nao_iniciado_em_andamento': self.get_queryset().filter(fase=fase).exclude(status__status="Concluído"),
                'concluidos': self.get_queryset().filter(fase=fase, status__status="Concluído"),
            }
            for fase in fases
        ]

        context.update({
            'processo': processo,
            'andamentos_por_fase': andamentos_por_fase,
        })
        return context

class ProcessoCreateView(LoginRequiredMixin,CreateView):
    model = Processo
    form_class = ProcessoForm
    template_name = 'processo_form.html'
    success_url = reverse_lazy('processo_list')

class ProcessoDetailView(LoginRequiredMixin,DetailView):
    model = Processo
    template_name = 'processo_detail.html'
    context_object_name = 'processo'

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


class ProcessoDeleteView(LoginRequiredMixin,DeleteView):
    model = Processo
    template_name = 'processo_confirm_delete.html'
    success_url = reverse_lazy('processo_list')


from django.http import Http404

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

        # Valida o processo_id
        processo_id = self.request.GET.get('processo')
        if not processo_id or not processo_id.isdigit():
            raise Http404("Processo inválido ou não encontrado.")

        # Busca o processo
        processo = get_object_or_404(Processo, pk=processo_id)

        # Obtém as fases, excluindo 'Processo Concluído'
        fases = Fase.objects.exclude(fase="Processo Concluído")  # Filtro aplicado

        # Organiza os andamentos por fase
        andamentos_por_fase = []
        for fase in fases:
            andamentos_por_fase.append({
                'fase': fase,
                'nao_iniciado_em_andamento': self.get_queryset().filter(fase=fase).exclude(status__status="Concluído"),
                'concluidos': self.get_queryset().filter(fase=fase, status__status="Concluído"),
            })

        # Atualiza o contexto
        context.update({
            'processo': processo,
            'andamentos_por_fase': andamentos_por_fase,
        })
        return context



class AndamentoCreateView(LoginRequiredMixin,CreateView):
    model = ProcessoAndamento
    form_class = AndamentoForm
    template_name = 'andamento_form.html'
    success_url = reverse_lazy('andamento_list')


class AndamentoUpdateView(LoginRequiredMixin, UpdateView):
    model = ProcessoAndamento
    form_class = AndamentoForm
    template_name = 'andamento_form_update.html'
    success_url = reverse_lazy('andamento_list')

    def get_success_url(self):
        # Obtém o processo associado ao andamento
        processo_id = self.object.processo.id
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
        
        return super().post(request, *args, **kwargs)




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

        # Finaliza o andamento atual
        andamento.dt_conclusao = now()
        andamento.status = Status.objects.get(status="Concluído")
        andamento.save()

        # Identifica o responsável baseado na fase
        usuario_responsavel = andamento.processo.usuario  # Usuário padrão (do processo)
        if nova_fase == "Revisão":
            usuario_responsavel = UserProfile.objects.filter(funcao="revisor(a)").first().user

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

        return redirect(reverse('andamento_list') + f"?processo={andamento.processo.pk}")




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
            fase=fase_concluido,  # 🔥 Ajustado para a fase correta
            usuario=request.user,
            status=Status.objects.get(status="Concluído"),
            dt_inicio=now(),
            dt_conclusao=now()
        )

        return redirect(reverse('andamento_list') + f"?processo={andamento.processo.pk}")



def process_metrics_view(request):
    """
    View para renderizar métricas avançadas com filtros opcionais, incluindo data inicial e final.
    """
    # Obtém os filtros da URL
    assessor = request.GET.get('assessor')
    mes_distribuicao = request.GET.get('mes_distribuicao')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

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
        data_fim=data_fim
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
            "data_fim": request.GET.get('data_fim', '')
        }
    })




@login_required
def adicionar_tarefa(request, processo_id):
    processo = get_object_or_404(Processo, id=processo_id)
    TarefaDoDia.objects.get_or_create(usuario=request.user, processo=processo)

    # Captura os parâmetros da URL para manter os filtros após adicionar a tarefa
    query_params = request.GET.copy()
    query_params.pop('page', None)  # Remove paginação para evitar problemas

    url = reverse('processo_list')  # Define a URL base da lista de processos
    if query_params:
        return redirect(f"{url}?{query_params.urlencode()}")
    return redirect(url)

@login_required
def remover_tarefa(request, processo_id):
    processo = get_object_or_404(Processo, id=processo_id)
    TarefaDoDia.objects.filter(usuario=request.user, processo=processo).delete()

    # Captura os parâmetros da URL para manter os filtros após remover a tarefa
    query_params = request.GET.copy()
    query_params.pop('page', None)  # Remove paginação para evitar problemas

    url = reverse('processo_list')  # Define a URL base da lista de processos
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

def importar_processos(request):
    if request.method == "POST":
        form = ExcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = request.FILES["arquivo"]

            try:
                df = pd.read_excel(arquivo)

                for index, row in df.iterrows():
                    try:
                        especie, _ = Especie.objects.get_or_create(sigla=str(row["especie"]).strip())
                        camara = Camara.objects.filter(camara=str(row["camara"]).strip()).first()

                        # 🔹 Ajuste do usuário - Certifica-se de que o usuário existe
                        usuario = None
                        if "usuario" in row and pd.notna(row["usuario"]):
                            username_input = str(row["usuario"]).strip()
                            usuario = User.objects.filter(username=username_input).first()

                            if not usuario:
                                usuario = User.objects.filter(username__iexact=username_input).first()

                            if not usuario:
                                messages.warning(request, f"⚠ Usuário '{username_input}' não encontrado na linha {index + 1}. Definido como vazio.")

                        data_dist = make_aware(pd.to_datetime(row["data_dist"])) if pd.notna(row["data_dist"]) else None
                        antigo = make_aware(pd.to_datetime(row["antigo"])) if "antigo" in row and pd.notna(row["antigo"]) else None
                        dt_conclusao = make_aware(pd.to_datetime(row["dt_conclusao"])) if "dt_conclusao" in row and pd.notna(row["dt_conclusao"]) else None
                        dt_prazo = make_aware(pd.to_datetime(row["dt_prazo"])) if "dt_prazo" in row and pd.notna(row["dt_prazo"]) else None

                        concluido = row.get("concluido", False)
                        if pd.isna(concluido):
                            concluido = False

                        Processo.objects.create(
                            numero_processo=row["numero_processo"],
                            data_dist=data_dist,
                            especie=especie,
                            camara=camara,
                            usuario=usuario,
                            concluido=concluido,
                            antigo=antigo,
                            dt_conclusao=dt_conclusao,
                            dt_prazo=dt_prazo,
                        )
                    except Exception as e:
                        messages.warning(request, f"❌ Erro ao importar linha {index + 1}: {str(e)}")

                messages.success(request, "✅ Processos importados com sucesso!")
                return redirect("processo_list")

            except Exception as e:
                messages.error(request, f"❌ Erro ao processar o arquivo: {str(e)}")

    else:
        form = ExcelUploadForm()

    return render(request, "importar_processos.html", {"form": form})


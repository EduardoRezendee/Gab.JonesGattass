from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from .models import Processo, Andamento, Fase, Status
from .forms import ProcessoForm, AndamentoForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from .models import Processo
from datetime import datetime, timedelta
from django.views.generic import ListView
from datetime import datetime, timedelta
from calendar import month_name
from .models import Processo, Fase, Status, Camara, Tipo, Especie
import locale
from calendar import month_name
from django.contrib.auth.models import User
from .models import ComentarioProcesso, Andamento
from .forms import ComentarioProcessoForm
from django.http import JsonResponse

# Configura o idioma para português
locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')


from django.contrib.auth.models import User
from django.utils.timezone import datetime, timedelta
from django.utils.translation import gettext_lazy as _
from calendar import month_name
from .models import Processo, Status, Fase, Camara, Tipo, Especie, TarefaDoDia

class ProcessoListView(LoginRequiredMixin, ListView):
    model = Processo
    template_name = 'processo_list.html'
    context_object_name = 'processos'
    paginate_by = 30

    def get_queryset(self):
        """
        Filtra os processos com base nos parâmetros fornecidos na URL.
        """
        queryset = Processo.objects.all()
        users = User.objects.all().order_by('first_name')  # Ordena pelo primeiro nome

        # Captura o parâmetro de ordenação da URL
        order_by = self.request.GET.get('ordenar', 'data_dist')

        # Aplicar a ordenação correta
        if order_by == "mais_recente":
            queryset = queryset.order_by("-data_dist")  # Mais recente primeiro
        elif order_by == "mais_antigo":
            queryset = queryset.order_by("data_dist")  # Mais antigo primeiro
        elif order_by == "antigo_recente":
            queryset = queryset.order_by("-antigo")  # Mais recente primeiro
        elif order_by == "antigo_antigo":
            queryset = queryset.order_by("antigo")  # Mais antigo primeiro

        # Filtros por campos específicos
        status = self.request.GET.get('status')
        fase_atual = self.request.GET.get('fase_atual')
        camara = self.request.GET.get('camara')
        tipo = self.request.GET.get('tipo')
        especie = self.request.GET.get('especie')
        numero_processo = self.request.GET.get('numero_processo')

        # Filtrar por "Meus Processos"
        meus_processos = self.request.GET.get('meus_processos', None)

        # Aplica o filtro se o checkbox estiver marcado
        if meus_processos == 'on':
            queryset = queryset.filter(usuario=self.request.user)

        # Filtrar por usuário (user_id)
        user_id = self.request.GET.get('user_id')
        if user_id:
            queryset = queryset.filter(usuario__id=user_id)

        # Filtrar por datas
        data_ano = self.request.GET.get('data_ano')
        data_mes = self.request.GET.get('data_mes')
        data_semana = self.request.GET.get('data_semana')
        data_prazo = self.request.GET.get('data_prazo')
        data_julgamento = self.request.GET.get('data_julgamento')

        if status:
            status = status.strip().lower()
            
            if status == "concluído":
                queryset = queryset.filter(concluido=True)
            elif status == "pendente":
                queryset = queryset.filter(concluido=False)



        if fase_atual:
            queryset = queryset.filter(andamentos__fase__fase=fase_atual)
        if camara:
            queryset = queryset.filter(camara__camara=camara)
        if tipo:
            queryset = queryset.filter(tipo__tipo=tipo)
        if especie:
            queryset = queryset.filter(especie__especie=especie)  # Se a espécie for filtrada pelo nome

        if numero_processo:
            queryset = queryset.filter(numero_processo__icontains=numero_processo)
        if meus_processos:
            queryset = queryset.filter(usuario=self.request.user)

        # Filtrar por ano
        if data_ano:
            queryset = queryset.filter(data_dist__year=data_ano)

        # Filtrar por mês
        if data_mes:
            queryset = queryset.filter(data_dist__month=data_mes)

        # Filtrar por semana
        if data_semana:
            start_week = datetime.today() - timedelta(days=7)
            queryset = queryset.filter(data_dist__gte=start_week)

        # Filtro por data de prazo e data de julgamento
        if data_prazo:
            queryset = queryset.filter(dt_prazo__date=data_prazo)
        if data_julgamento:
            queryset = queryset.filter(dt_julgamento__date=data_julgamento)

        # Adiciona fase_atual e status_atual para cada processo
        for processo in queryset:
            ultimo_andamento = processo.andamentos.order_by('-dt_criacao').first()
            processo.fase_atual = ultimo_andamento.fase.fase if ultimo_andamento and ultimo_andamento.fase else "Sem Fase"
            processo.status_atual = "Concluído" if processo.concluido else "Pendente"

        return queryset

    def get_context_data(self, **kwargs):
        """
        Adiciona dados adicionais ao contexto do template.
        """
        context = super().get_context_data(**kwargs)

        context["ordenacao_opcoes"] = [
            {"valor": "mais_recente", "label": "Mais Recente"},
            {"valor": "mais_antigo", "label": "Mais Antigo"},
        ]

        # Adiciona os usuários ao contexto, ordenados por nome completo
        context['users'] = User.objects.select_related('profile').order_by('first_name', 'last_name')

        # Obtém métricas de processos
        metrics = get_advanced_metrics()

        # Adiciona meses (número e nome) ao contexto
        context['meses'] = [(i, month_name[i].capitalize()) for i in range(1, 13)]

        # Adiciona filtros para os campos relacionados
        context['statuses'] = ["Concluído", "Pendente"]  # Apenas os dois status do processo
        context['fases'] = Fase.objects.values_list('fase', flat=True)
        context['camaras'] = Camara.objects.all()
        context['tipos'] = Tipo.objects.all()
        context['especies'] = Especie.objects.all()

        # Adiciona informações sobre as tarefas do dia do usuário
        tarefas = TarefaDoDia.objects.filter(usuario=self.request.user)
        context['tarefas_do_dia'] = tarefas  # Lista completa de tarefas
        context['tarefas_do_dia_ids'] = list(tarefas.values_list('processo__id', flat=True))  # IDs dos processos

        # Dicionário para mapear processos por usuário
        processos_por_usuario = {
            item['id']: {
                "total": item["total"], 
                "concluidos": item['concluidos'], 
                "pendentes": item['pendentes']
            }
            for item in metrics['assessor_process_data']
        }

        context['processos_por_usuario'] = processos_por_usuario

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

class AndamentoListView(LoginRequiredMixin,ListView):
    template_name = 'andamento_list.html'
    context_object_name = 'andamentos'

    def get_queryset(self):
        """
        Retorna os andamentos relacionados ao processo atual, com validação de ID.
        """
        processo_id = self.request.GET.get('processo')
        if not processo_id or not processo_id.isdigit():
            raise Http404("Processo inválido ou não encontrado.")
        
        return Andamento.objects.filter(processo_id=processo_id).select_related('fase', 'usuario', 'status')

    def get_context_data(self, **kwargs):
        """
        Adiciona informações adicionais ao contexto.
        """
        context = super().get_context_data(**kwargs)

        # Valida o processo_id
        processo_id = self.request.GET.get('processo')
        if not processo_id or not processo_id.isdigit():
            raise Http404("Processo inválido ou não encontrado.")

        # Busca o processo
        processo = get_object_or_404(Processo, pk=processo_id)

        # Obtém as fases e organiza os andamentos
        fases = Fase.objects.all()
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
    model = Andamento
    form_class = AndamentoForm
    template_name = 'andamento_form.html'
    success_url = reverse_lazy('andamento_list')


class AndamentoUpdateView(LoginRequiredMixin,UpdateView):
    model = Andamento
    form_class = AndamentoForm
    template_name = 'andamento_form_update.html'
    success_url = reverse_lazy('andamento_list')

    def get_success_url(self):
        # Obtém o processo associado ao andamento
        processo_id = self.object.processo.id
        # Redireciona para a URL da lista de andamentos, incluindo o parâmetro 'processo'
        return f"{reverse('andamento_list')}?processo={processo_id}"

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Verifica se a ação é para iniciar o andamento
        if 'iniciar_andamento' in request.POST:
            self.object.dt_inicio = now()
            self.object.save()
            return redirect(self.success_url + f'?processo={self.object.processo.pk}')
        
        # Verifica se a ação é para enviar para outra fase
        if 'enviar_para_fase' in request.POST:
            nova_fase = request.POST.get('nova_fase')
            if nova_fase:
                self.object.concluir_andamento()
                nova_fase_obj = Fase.objects.get(fase=nova_fase)
                Andamento.objects.create(
                    processo=self.object.processo,
                    andamento=f"Movido para {nova_fase}",
                    fase=nova_fase_obj,
                    usuario=request.user
                )
            return redirect(self.success_url + f'?processo={self.object.processo.pk}')
            
        return super().post(request, *args, **kwargs)



class AndamentoDeleteView(LoginRequiredMixin,DeleteView):
    model = Andamento
    template_name = "andamento_confirm_delete.html"

    def get_success_url(self):
        """
        Redireciona para a lista de andamentos do processo atual após a exclusão.
        """
        processo_id = self.object.processo.id  # Obtém o ID do processo relacionado
        return reverse('andamento_list') + f'?processo={processo_id}'


from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.utils.timezone import now

from .models import Andamento, Fase

class AndamentoIniciarView(LoginRequiredMixin,UpdateView):
    def post(self, request, pk, *args, **kwargs):
        andamento = get_object_or_404(Andamento, pk=pk)
        if not andamento.dt_inicio:  # Verifica se o andamento ainda não foi iniciado
            andamento.dt_inicio = now()
            andamento.status = Status.objects.get(status="Em andamento")  # Atualiza o status
            andamento.save()
        return redirect(reverse('andamento_update', kwargs={'pk': pk}))


from django.shortcuts import get_object_or_404, redirect
from django.utils.timezone import now
from django.urls import reverse
from accounts.models import UserProfile  # Certifique-se de importar o modelo correto
from processos.models import Andamento, Fase, Status

class AndamentoEnviarParaFaseView(LoginRequiredMixin, UpdateView):
    def post(self, request, pk, *args, **kwargs):
        andamento = get_object_or_404(Andamento, pk=pk)
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
        Andamento.objects.create(
            processo=andamento.processo,
            andamento=f"Movido para {nova_fase}",
            fase=nova_fase_obj,
            usuario=usuario_responsavel,
            status=Status.objects.get(status="Não iniciado"),
            link_doc=andamento.link_doc  # Copia o link do documento
        )

        return redirect(reverse('andamento_list') + f"?processo={andamento.processo.pk}")




class AndamentoConcluirProcessoView(LoginRequiredMixin,UpdateView):
    def post(self, request, pk, *args, **kwargs):
        # Obtem o andamento pelo ID
        andamento = get_object_or_404(Andamento, pk=pk)
        
        # Finaliza o andamento atual
        andamento.dt_conclusao = now()
        andamento.status = Status.objects.get(status="Concluído")
        andamento.save()

        # Marca o processo como concluído e define a data de conclusão
        processo = andamento.processo
        processo.concluido = True
        processo.dt_atualizacao = now()  # Atualiza a última modificação
        processo.dt_conclusao = now()  # Registra a data de conclusão
        processo.save()

        # Redireciona para a lista de andamentos do processo
        return redirect(reverse('andamento_list') + f"?processo={andamento.processo.pk}")


from django.shortcuts import render
from .metrics import get_advanced_metrics
from calendar import month_name
from processos.models import Processo

def process_metrics_view(request):
    """
    View para renderizar métricas avançadas com filtros opcionais.
    """
    # Obtém os filtros da URL
    assessor = request.GET.get('assessor')
    mes_distribuicao = request.GET.get('mes_distribuicao')

    # Obtém os dados de métricas
    metrics_data = get_advanced_metrics(assessor=assessor, mes_distribuicao=mes_distribuicao)

    # Lista de meses disponíveis para filtro
    months = [(i, month_name[i]) for i in range(1, 13)]

    # Lista de assessores distintos
    assessores = Processo.objects.values('usuario__id', 'usuario__first_name', 'usuario__last_name').distinct()

    # Passa os dados ao template
    return render(request, 'metrics.html', {
        # Dados de gráficos com quantidade e porcentagem
        "species_data": metrics_data["species_data"],    # Processos por Espécie
        "type_data": metrics_data["type_data"],          # Processos por Tipo
        "camara_data": metrics_data["camara_data"],      # Processos por Câmara
        "resultado_data": metrics_data["resultado_data"],# Processos por Resultado
        "assessor_data": metrics_data["assessor_data"],  # Processos por Assessor
        "total_processos": metrics_data["total_processos"],
        "total_concluidos": metrics_data["total_concluidos"],
        "total_pendentes": metrics_data["total_pendentes"],
        "andamento_data": metrics_data["andamento_data"],
        "porcentagem_concluidos": metrics_data["porcentagem_concluidos"],
        "porcentagem_pendentes": metrics_data["porcentagem_pendentes"],

        # Métricas adicionais
        "average_process_time": metrics_data["average_process_time"], # Tempo médio dos processos
        "andamento_durations": metrics_data["andamento_durations"],   # Tempo médio por tipo de andamento
        "andamento_waiting_times": metrics_data["andamento_waiting_times"],  # Tempo médio aguardando início dos andamentos

        # Filtros disponíveis
        "months": months,           # Lista de meses
        "assessores": assessores,    # Lista de assessores

        # **Novo**: Lista de processos detalhados
        "detalhes_processos": metrics_data["detalhes_processos"]
    })


from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import TarefaDoDia, Processo

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

import openpyxl
from django.http import HttpResponse
from .models import Processo

import openpyxl
from django.http import HttpResponse
from .models import Processo

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

    print(f"Recebendo requisição AJAX para processo_id={processo_id}")

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

import pandas as pd
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Processo, Especie, Camara
from .forms import ExcelUploadForm
from django.contrib.auth.models import User
from django.utils.timezone import make_aware

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
                            username_input = str(row["usuario"]).strip()  # Remove espaços extras
                            usuario = User.objects.filter(username=username_input).first()

                            # 🔹 Se não encontrar, tenta buscar sem diferenciar maiúsculas/minúsculas
                            if not usuario:
                                usuario = User.objects.filter(username__iexact=username_input).first()

                            # Exibir mensagem se o usuário não for encontrado
                            if not usuario:
                                messages.warning(request, f"⚠ Usuário '{username_input}' não encontrado na linha {index + 1}. Definido como vazio.")

                        data_dist = make_aware(pd.to_datetime(row["data_dist"])) if pd.notna(row["data_dist"]) else None
                        antigo = make_aware(pd.to_datetime(row["antigo"])) if "antigo" in row and pd.notna(row["antigo"]) else None

                        concluido = row.get("concluido", False)
                        if pd.isna(concluido):
                            concluido = False

                        Processo.objects.create(
                            numero_processo=row["numero_processo"],
                            data_dist=data_dist,
                            especie=especie,
                            camara=camara,
                            usuario=usuario,  # Agora corretamente ajustado
                            concluido=concluido,
                            antigo=antigo,
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


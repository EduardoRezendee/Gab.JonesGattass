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
from rest_framework import generics
from . import models, forms, serializers
import pandas as pd
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime
from django.shortcuts import render
from django.contrib import messages
from django.http import HttpResponseRedirect
from .models import Processo, Especie, Camara, Tema
from django.db import DatabaseError

from django.views.decorators.http import require_http_methods
from .models import Processo, MetaSemanal

@login_required
@require_http_methods(["GET", "POST"])
def configurar_meta_semanal(request):
    if request.method == "POST":
        usuario_id = request.POST.get('usuario_id')
        processo_ids = request.POST.getlist('processo_ids[]')
        meta_qtd = request.POST.get('meta_qtd')
        periodo = request.POST.get('periodo')  # Período selecionado (ex.: "atual" ou "seguinte")

        # Validações
        if not usuario_id:
            return JsonResponse({'success': False, 'message': 'Usuário é obrigatório.'}, status=400)
        if not processo_ids or not meta_qtd:
            return JsonResponse({'success': False, 'message': 'Selecione pelo menos um processo.'}, status=400)
        if not periodo:
            return JsonResponse({'success': False, 'message': 'Período é obrigatório.'}, status=400)

        try:
            meta_qtd = int(meta_qtd)
            if meta_qtd <= 0:
                raise ValueError
        except ValueError:
            return JsonResponse({'success': False, 'message': 'Quantidade de meta inválida.'}, status=400)

        # Calcular semanas dinamicamente
        hoje = timezone.localdate()
        inicio_semana_atual = hoje - timedelta(days=hoje.weekday())  # Segunda-feira da semana atual
        fim_semana_atual = inicio_semana_atual + timedelta(days=6)  # Domingo da semana atual
        inicio_semana_seguinte = inicio_semana_atual + timedelta(days=7)  # Segunda-feira da semana seguinte
        fim_semana_seguinte = inicio_semana_seguinte + timedelta(days=6)  # Domingo da semana seguinte

        # Determinar as datas do período selecionado
        if periodo == "atual":
            inicio_semana = inicio_semana_atual
            fim_semana = fim_semana_atual
        elif periodo == "seguinte":
            inicio_semana = inicio_semana_seguinte
            fim_semana = fim_semana_seguinte
        else:
            return JsonResponse({'success': False, 'message': 'Período inválido.'}, status=400)

        usuario = get_object_or_404(User, id=usuario_id)
        processos = Processo.objects.filter(id__in=processo_ids, usuario=usuario, concluido=False)

        # Cria ou atualiza a meta para o período selecionado
        meta, created = MetaSemanal.objects.get_or_create(
            usuario=usuario,
            semana_inicio=inicio_semana,
            semana_fim=fim_semana,
            defaults={'meta_qtd': meta_qtd}
        )
        if not created:
            meta.meta_qtd = meta_qtd
            meta.save()
        meta.processos.set(processos)

        return JsonResponse({'success': True, 'message': 'Meta salva com sucesso!'})

    # GET: Carregar usuários, processos e períodos disponíveis
    usuarios = User.objects.all()
    processos = Processo.objects.filter(concluido=False).select_related('especie', 'usuario')

    # Subquery para fase atual
    ultima_fase_subquery = ProcessoAndamento.objects.filter(
        processo=OuterRef('pk')
    ).order_by('-dt_criacao').values('fase__fase')[:1]

    # Adiciona anotação de fase atual
    processos = processos.annotate(fase_atual=Subquery(ultima_fase_subquery))

    # Monta dicionário agrupado por usuário
    processos_por_usuario = {}
    for user in usuarios:
        user_procs = processos.filter(usuario=user)
        processos_por_usuario[user.id] = [
            {
                'id': proc.id,
                'numero_processo': proc.numero_processo,
                'especie': proc.especie.especie if proc.especie else 'N/A',
                'dias_no_gabinete': (timezone.now().date() - proc.antigo.date()).days if proc.antigo else 0,
                'fase_atual': proc.fase_atual or '—'
            }
            for proc in user_procs
        ]

    # Determina os períodos disponíveis (semana atual e semana seguinte)
    hoje = timezone.localdate()
    inicio_semana_atual = hoje - timedelta(days=hoje.weekday())
    fim_semana_atual = inicio_semana_atual + timedelta(days=6)
    inicio_semana_seguinte = inicio_semana_atual + timedelta(days=7)
    fim_semana_seguinte = inicio_semana_seguinte + timedelta(days=6)

    periodos = [
        {
            'label': f"Semana Atual ({inicio_semana_atual.strftime('%d/%m/%Y')} a {fim_semana_atual.strftime('%d/%m/%Y')})",
            'value': 'atual'
        },
        {
            'label': f"Semana Seguinte ({inicio_semana_seguinte.strftime('%d/%m/%Y')} a {fim_semana_seguinte.strftime('%d/%m/%Y')})",
            'value': 'seguinte'
        },
    ]

    return render(request, 'configurar_meta_semanal.html', {
        'usuarios': usuarios,
        'processos_por_usuario': processos_por_usuario,
        'periodos': periodos,
    })

from django.contrib.auth import get_user_model
from django.db.models import Prefetch
User = get_user_model()

@login_required
@require_http_methods(["GET"])
def listar_metas_semanal(request):
    # 1) Define a data atual para comparações
    agora = timezone.localtime()
    hoje = timezone.localdate()

    # 2) Obtém todas as metas disponíveis para determinar os períodos
    if request.user.has_perm('app_name.view_all_metas'):
        todas_metas = MetaSemanal.objects.all()
    else:
        todas_metas = MetaSemanal.objects.filter(usuario=request.user)

    # 3) Cria uma lista de períodos disponíveis (semanas únicas)
    periodos_disponiveis = []
    semanas_vistas = set()
    for meta in todas_metas:
        semana_key = (meta.semana_inicio, meta.semana_fim)
        if semana_key not in semanas_vistas:
            semanas_vistas.add(semana_key)
            periodos_disponiveis.append({
                'inicio': meta.semana_inicio,
                'fim': meta.semana_fim,
                'label': f"{meta.semana_inicio.strftime('%d/%m/%Y')} a {meta.semana_fim.strftime('%d/%m/%Y')}",
                'value': f"{meta.semana_inicio.strftime('%Y-%m-%d')}|{meta.semana_fim.strftime('%Y-%m-%d')}"
            })
    # Ordena os períodos por data de início
    periodos_disponiveis.sort(key=lambda x: x['inicio'])

    # 4) Filtra metas com base no período selecionado (via GET)
    periodo_selecionado = request.GET.get('periodo', None)
    if periodo_selecionado:
        try:
            inicio_str, fim_str = periodo_selecionado.split('|')
            inicio_semana = datetime.strptime(inicio_str, '%Y-%m-%d').date()
            fim_semana = datetime.strptime(fim_str, '%Y-%m-%d').date()
            if request.user.has_perm('app_name.view_all_metas'):
                metas = MetaSemanal.objects.filter(semana_inicio=inicio_semana, semana_fim=fim_semana)
            else:
                metas = MetaSemanal.objects.filter(
                    usuario=request.user,
                    semana_inicio=inicio_semana,
                    semana_fim=fim_semana
                )
        except (ValueError, TypeError):
            # Caso o parâmetro esteja malformado, mostra todas as metas
            metas = todas_metas
    else:
        metas = todas_metas

    metas = metas.select_related('usuario', 'usuario__profile').prefetch_related(
        Prefetch('processos', Processo.objects.select_related('especie'))
    )

    # 5) Prepara o dicionário de processos abertos por usuário
    usuarios = User.objects.all()
    processos_abertos = Processo.objects.filter(concluido=False).select_related('especie', 'usuario')

    # Subquery para fase atual
    ultima_fase_subquery = ProcessoAndamento.objects.filter(
        processo=OuterRef('pk')
    ).order_by('-dt_criacao').values('fase__fase')[:1]

    # Adiciona anotação de fase atual
    processos_abertos = processos_abertos.annotate(fase_atual=Subquery(ultima_fase_subquery))

    processos_por_usuario = {
        u.id: [
            {
                'id': p.id,
                'numero_processo': p.numero_processo,
                'especie': p.especie.especie if p.especie else '—',
                'dias_no_gabinete': (hoje - p.antigo.date()).days if p.antigo else 0,
                'fase_atual': p.fase_atual or '—'
            }
            for p in processos_abertos.filter(usuario=u)
        ]
        for u in usuarios
    }

    # 6) Calcula progresso e faixas de dias para cada meta individualmente
    for meta in metas:
        procs_meta = list(meta.processos.all())
        if not procs_meta:
            meta.progresso = 0
            continue

        # Usa o intervalo específico da meta para calcular o progresso
        inicio_semana = meta.semana_inicio
        fim_semana = meta.semana_fim

        # Consulta otimizada para processos revisados no intervalo da meta
        revisados_por_meta = (
            ProcessoAndamento.objects
            .filter(
                processo__in=procs_meta,
                fase__fase="Revisão Des",
                dt_criacao__range=(inicio_semana, fim_semana)
            )
            .values('processo')
            .distinct()
        )
        revisados_ids = set(revisados_por_meta.values_list('processo', flat=True))

        concluidas = sum(1 for p in procs_meta if p.id in revisados_ids)
        meta.progresso = round(min((concluidas / meta.meta_qtd * 100) if meta.meta_qtd else 0, 100), 1)

        # Calcula faixas de dias para todos os processos do usuário
        user_procs = processos_abertos.filter(usuario=meta.usuario)
        total_user = user_procs.count()
        dias = [(hoje - p.antigo.date()).days for p in user_procs if p.antigo]
        mais_30 = sum(1 for d in dias if d > 30)
        mais_40 = sum(1 for d in dias if d > 40)
        mais_50 = sum(1 for d in dias if d > 50)

        meta.range_le30 = total_user - mais_30
        meta.range_31_40 = mais_30 - mais_40
        meta.range_41_50 = mais_40 - mais_50
        meta.range_gt50 = mais_50

        # Adiciona indicador de status da meta (passada, atual ou futura)
        if fim_semana < hoje:
            meta.status = 'passada'
        elif inicio_semana > hoje:
            meta.status = 'futura'
        else:
            meta.status = 'atual'

    # 7) Renderiza o template
    return render(request, 'listar_metas_semanal.html', {
        'metas': metas,
        'processos_por_usuario': processos_por_usuario,
        'periodos': periodos_disponiveis,
        'periodo_selecionado': periodo_selecionado,
    })

@require_http_methods(["GET", "POST"])
@login_required
def editar_meta_semanal(request):
    if request.method == "GET":
        meta_id = request.GET.get('meta_id')
        meta = get_object_or_404(MetaSemanal, id=meta_id)

        # Verificar permissões
        if not request.user.has_perm('app_name.change_metasemanal') and request.user != meta.usuario:
            return JsonResponse({'success': False, 'message': 'Você não tem permissão para editar esta meta.'}, status=403)

        processos = list(meta.processos.all())

        # Subquery para fase atual
        ultima_fase_subquery = ProcessoAndamento.objects.filter(
            processo=OuterRef('pk')
        ).order_by('-dt_criacao').values('fase__fase')[:1]

        processos_com_fase = Processo.objects.filter(pk__in=[p.id for p in processos]).annotate(
            fase_atual=Subquery(ultima_fase_subquery)
        ).select_related('especie')

        data_processos = []
        for p in processos_com_fase:
            data_processos.append({
                'id': p.id,
                'numero_processo': p.numero_processo,
                'especie': p.especie.especie if p.especie else '—',
                'fase_atual': p.fase_atual or 'Não especificado'
            })

        data = {
            'id': meta.id,
            'usuario_id': meta.usuario.id,
            'meta_qtd': meta.meta_qtd,
            'processo_ids': [p.id for p in processos],
            'processos': data_processos
        }
        return JsonResponse(data)

    if request.method == "POST":
        meta_id = request.POST.get('meta_id')
        meta_qtd = request.POST.get('meta_qtd')
        processo_ids = request.POST.getlist('processo_ids[]')

        if not meta_id or not processo_ids:
            return JsonResponse({'success': False, 'message': 'Dados inválidos: meta e processos são obrigatórios.'}, status=400)

        try:
            meta_qtd = int(meta_qtd)
            if meta_qtd <= 0:
                return JsonResponse({'success': False, 'message': 'A meta deve ser maior que 0.'}, status=400)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': 'A meta deve ser um número inteiro válido.'}, status=400)

        meta = get_object_or_404(MetaSemanal, id=meta_id)

        # Verificar permissões
        if not request.user.has_perm('app_name.change_metasemanal') and request.user != meta.usuario:
            return JsonResponse({'success': False, 'message': 'Você não tem permissão para editar esta meta.'}, status=403)

        # Inclui processos válidos (não concluídos e do usuário)
        processos_validos = Processo.objects.filter(id__in=processo_ids, usuario=meta.usuario)

        # Inclui também os concluídos que já estavam na meta
        processos_concluidos_meta = meta.processos.filter(id__in=processo_ids)

        # Combina os dois conjuntos
        processos = (processos_validos | processos_concluidos_meta).distinct()

        if processos.count() != len(processo_ids):
            return JsonResponse({'success': False, 'message': 'Alguns processos não são do usuário ou inválidos.'}, status=400)

        meta.meta_qtd = meta_qtd
        meta.processos.set(processos)
        meta.save()

        return JsonResponse({
            'success': True,
            'message': f'Meta atualizada com sucesso! {len(processos)} processos associados.',
        })


   

@require_http_methods(["POST"])
def excluir_meta_semanal(request):
    meta_id = request.GET.get('meta_id')
    meta = get_object_or_404(MetaSemanal, id=meta_id)
    meta.delete()
    return JsonResponse({'success': True, 'message': 'Meta excluída com sucesso!'})


@login_required
@require_http_methods(["GET"])
def minhas_metas(request):
    user = request.user
    now = timezone.localtime()
    # Calcula início e fim da semana (segunda a domingo)
    inicio_semana = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    fim_semana = (inicio_semana + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)

    # Busca meta da semana atual com prefetch_related otimizado
    meta = MetaSemanal.objects.filter(
        usuario=user,
        semana_inicio=inicio_semana.date(),
        semana_fim=fim_semana.date()
    ).prefetch_related(
        Prefetch('processos', Processo.objects.select_related('especie', 'tipo'))
    ).first()

    # Valores padrão
    total_meta = pendentes = concluidas = progresso = 0
    processos_com_status = []
    processos_fora_meta = []

    if meta:
        total_meta = meta.meta_qtd
        processos = list(meta.processos.all())

        # Busca quais processos foram concluídos (enviados para Revisão Desa) nesta semana
        concluidos_ids = set(
            ProcessoAndamento.objects.filter(
                processo__in=processos,
                fase__fase="Revisão Des",
                dt_criacao__range=(inicio_semana, fim_semana)
            ).values_list('processo', flat=True).distinct()
        )

        # Busca a fase atual de cada processo usando uma subconsulta
        ultima_fase_subquery = ProcessoAndamento.objects.filter(
            processo=OuterRef('pk')
        ).order_by('-dt_criacao').values('fase__fase')[:1]
        processos_com_fase = Processo.objects.filter(pk__in=[p.id for p in processos]).annotate(
            fase_atual=Subquery(ultima_fase_subquery)
        )

        # Mapeia as fases atuais pelos IDs dos processos
        fases_atuais = {p.id: p.fase_atual for p in processos_com_fase}

        concluidas = len(concluidos_ids)
        pendentes = max(0, total_meta - concluidas)  # Evita valores negativos
        progresso = round((concluidas / total_meta * 100) if total_meta > 0 else 0, 1)

        # Constrói lista para processos da meta
        for p in processos:
            data_entrada = p.antigo or p.dt_criacao
            dias_no_gabinete = (now.date() - data_entrada.date()).days if data_entrada else None

            processos_com_status.append({
                'numero_processo': p.numero_processo,
                'data_entrada': data_entrada,
                'dias_no_gabinete': dias_no_gabinete,
                'fase_atual': fases_atuais.get(p.id, 'Não especificado'),
                'especie': p.especie.especie if p.especie else 'Não especificado',
                'tipo': p.tipo.tipo if p.tipo else 'Não especificado',
                'concluido': (p.id in concluidos_ids)
            })

        # Busca processos enviados para Revisão Desa fora da meta
        processos_fora = ProcessoAndamento.objects.filter(
            processo__usuario=user,
            fase__fase="Revisão Des",
            dt_criacao__range=(inicio_semana, fim_semana)
        ).exclude(
            processo__in=[p.id for p in processos]
        ).values('processo').distinct()

        # Obtém detalhes dos processos fora da meta
        processos_fora_ids = [item['processo'] for item in processos_fora]
        processos_fora_detalhes = Processo.objects.filter(
            id__in=processos_fora_ids
        ).select_related('especie', 'tipo').annotate(
            fase_atual=Subquery(ultima_fase_subquery)
        )

        for p in processos_fora_detalhes:
            data_entrada = p.antigo or p.dt_criacao
            dias_no_gabinete = (now.date() - data_entrada.date()).days if data_entrada else None

            processos_fora_meta.append({
                'numero_processo': p.numero_processo,
                'data_entrada': data_entrada,
                'dias_no_gabinete': dias_no_gabinete,
                'fase_atual': p.fase_atual or 'Não especificado',
                'especie': p.especie.especie if p.especie else 'Não especificado',
                'tipo': p.tipo.tipo if p.tipo else 'Não especificado',
                'concluido': True  # Todos são concluídos, pois foram enviados para Revisão Desa
            })

    return render(request, 'minhas_metas.html', {
        'meta': meta,
        'total_meta': total_meta,
        'metas_pendentes': pendentes,
        'metas_concluidas': concluidas,
        'progresso': progresso,
        'processos_com_status': processos_com_status,
        'processos_fora_meta': processos_fora_meta,
    })



# Mapeamento de siglas para nomes completos
MAPEAMENTO_ESPECIES = {
    'ApCrim': 'Apelação Criminal',
    'ArRCrim': 'Agravo Regimental Criminal',
    'AI': 'Agravo de Instrumento',
    'AgExPe': 'Agravo em Execução Penal',
    'AgRCiv': 'Agravo Regimental Cível',
    'ApCiv': 'Apelação Cível',
    'ApCiv/RNCi': 'Apelação/Remessa Necessária Cível',
    'AC': 'Ação Cautelar',
    'ACP': 'Ação Civil Pública',
    'AIJE': 'Ação de Investigação Judicial Eleitoral',
    'ADJ': 'Ação Declaratória de Inexistência de Débito',
    'ADIN': 'Ação Direta de Inconstitucionalidade',
    'AR': 'Ação Rescisória',
    'CT': 'Carta Testemunhável',
    'CIC': 'Cautelar Inominada Criminal',
    'CC': 'Conflito de Competência',
    'CCCiv': 'Conflito de Competência Cível',
    'Desafor': 'Desaforamento',
    'ED': 'Embargos de Declaração',
    'EDCrim': 'Embargos de Declaração Criminal',
    'ExecFiscal': 'Execução Fiscal',
    'IDC': 'Incidente de Deslocamento de Competência',
    'ISM': 'Incidente de Sanidade Mental',
    'LIM': 'Liminar',
    'MSCrim': 'Mandado de Segurança Criminal',
    'MSCiv': 'Mandado de Segurança Cível',
    'PESE': 'Pedido de Efeito Suspensivo à Apelação',
    'PetCrim': 'Petição Criminal',
    'Rcl': 'Reclamação',
    'Resp': 'Recurso Especial',
    'RE': 'Recurso Extraordinário',
    'ROC': 'Recurso Ordinário Constitucional',
    'RSE': 'Recurso em Sentido Estrito',
    'RINT': 'Representação por Interceptação Telefônica',
    'RQD': 'Representação por Quebra de Domicílio',
    'HCCrim': 'Habeas Corpus Criminal',
    'RECURSO': 'Recurso Ordinário',
    'RevCrim': 'Revisão Criminal',
}

# Mapeamento de tags para nomes de usuário
MAPEAMENTO_TAG_USUARIO = {
    'Ass-Priscilla': 'priscillalessi',
    'Ass-Thais': 'thaiscamila',
    'Ass-Caio': 'caiocesar',
    'Ass-Izabela': 'izabelaortiz',
    'ASS-IZABELA': 'izabelaortiz',
    'Ass-Juliana': 'julianalodi',
    'Ass-Jurandy': 'jurandysilva',
    'Ass-Karen': 'karenaquino',
    'Ass-Manoel': 'manoellima',
    'Ass-Marco Antônio': 'marcoantonio',
    'ASS-Marco Antônio': 'marcoantonio',
    'Ass-Mirelli': 'mirellisilva',
    'Ass-Viviane': 'vivianelima',
}

def importar_processos_view(request):
    if request.method == 'POST':
        if 'arquivo' not in request.FILES:
            messages.error(request, 'Nenhum arquivo selecionado.')
            return render(request, 'importar_processos.html')

        arquivo = request.FILES['arquivo']
        if not arquivo.name.endswith('.csv'):
            messages.error(request, 'O arquivo deve ser um CSV (.csv).')
            return render(request, 'importar_processos.html')

        try:
            # Forçar que a coluna 'prioridade' seja lida como string
            df = pd.read_csv(arquivo, sep=';', encoding='utf-8', dtype={'prioridade': str})

            #Marcar despacho como True
            despacho = False
            if pd.notna(row.get('nomeTarefa')) and 'Minutar despacho ou decisão' in row['nomeTarefa'].strip().lower():
                despacho = True

            # Verificar colunas esperadas
            colunas_esperadas = ['numeroProcesso', 'classeJudicial', 'assuntoPrincipal', 'tagsProcessoList', 'dataChegada', 'prioridade']
            colunas_faltando = [col for col in colunas_esperadas if col not in df.columns]
            if colunas_faltando:
                messages.error(request, f"Colunas faltando no CSV: {', '.join(colunas_faltando)}")
                return render(request, 'importar_processos.html')

            # Carregar usuários mapeados para evitar consultas repetidas
            usuarios = {u.username: u for u in User.objects.filter(username__in=MAPEAMENTO_TAG_USUARIO.values())}
            usuario_default = 'admin'
            if usuario_default not in usuarios and not User.objects.filter(username=usuario_default).exists():
                messages.error(request, f"Usuário padrão {usuario_default} não encontrado no banco de dados.")
                return render(request, 'importar_processos.html')

            processos_inseridos = 0
            processos_ignorados = 0

            for index, row in df.iterrows():
                try:
                    numero_processo = row['numeroProcesso']

                    # Ignorar processos já existentes e não concluídos
                    processo_existente = Processo.objects.filter(numero_processo=numero_processo, concluido=False).first()
                    if processo_existente:
                        processos_ignorados += 1
                        continue

                    # Processar espécie
                    especie = None
                    if pd.notna(row.get('classeJudicial')) and row['classeJudicial'].strip():
                        sigla = str(row['classeJudicial']).strip().upper()
                        nome_especie = MAPEAMENTO_ESPECIES.get(sigla, sigla)  # Usar sigla como fallback
                        especie, _ = Especie.objects.get_or_create(
                            sigla=sigla,
                            defaults={
                                'especie': nome_especie,
                                'dt_criacao': timezone.now(),
                                'dt_atualizacao': timezone.now(),
                            }
                        )
                    else:
                        print(f"Processo {numero_processo} sem classe judicial, ignorando espécie.")

                    # Processar tema
                    tema = None
                    if pd.notna(row.get('assuntoPrincipal')) and row['assuntoPrincipal'].strip():
                        tema, _ = Tema.objects.get_or_create(
                            nome=row['assuntoPrincipal'],
                            defaults={
                                'nome': row['assuntoPrincipal'],
                                'dt_criacao': timezone.now(),
                                'dt_atualizacao': timezone.now(),
                                'ativo': True
                            }
                        )

        

                    # Processar usuário a partir das tags
                    usuario = None
                    if pd.notna(row.get('tagsProcessoList')) and row['tagsProcessoList'].strip():
                        tags = [tag.strip() for tag in str(row['tagsProcessoList']).split(',') if tag.strip() and tag.strip().startswith('Ass-')]
                        usuario_encontrado = False
                        for tag in tags:
                            if not tag.startswith('Ass-'):
                                print(f"Tag ignorada (não começa com 'Ass-'): {tag} para processo {numero_processo}")
                                continue
                            username_mapeado = MAPEAMENTO_TAG_USUARIO.get(tag)
                            if username_mapeado:
                                usuario = usuarios.get(username_mapeado)
                                if usuario:
                                    usuario_encontrado = True
                                    break
                                else:
                                    print(f"Usuário mapeado {username_mapeado} não encontrado para tag {tag} no processo {numero_processo}")
                            else:
                                print(f"Tag não mapeada: {tag} para processo {numero_processo}")
                        if not usuario_encontrado:
                            usuario = None
                            print(f"Processo {numero_processo} sem usuário mapeado, nenhum usuário atribuído.")
                    else:
                        print(f"Processo {numero_processo} sem tags válidas ou tagsProcessoList vazio, usando usuário padrão {usuario_default}")
                        usuario = usuarios.get(usuario_default, User.objects.filter(username=usuario_default).first())

                    # Processar data de chegada
                    antigo = None
                    if pd.notna(row.get('dataChegada')) and row['dataChegada'].strip():
                        try:
                            data_str = str(row['dataChegada']).strip()
                            antigo = datetime.strptime(data_str, '%d/%m/%Y')
                            antigo = antigo.replace(hour=0, minute=0, second=0, microsecond=0)
                            antigo = timezone.make_aware(antigo)
                        except ValueError as e:
                            print(f"Erro ao converter data para {numero_processo}: {str(e)}")
                            messages.warning(request, f"Data inválida para processo {numero_processo}, ignorando data.")

                    # Processar prioridade
                    prioridade_str = str(row.get('prioridade', 'false')).strip().lower()
                    prioridade_urgente = prioridade_str == 'true'

                    # Criar ou atualizar processo
                    processo, created = Processo.objects.update_or_create(
                        numero_processo=numero_processo,
                        defaults={
                            'especie': especie,
                            'tema': tema,
                            'usuario': usuario,
                            'antigo': antigo,
                            'prioridade_urgente': prioridade_urgente,
                            'dt_criacao': timezone.now(),
                            'dt_atualizacao': timezone.now(),
                            'data_dist': timezone.now(),
                            'concluido': False,
                            'despacho': despacho,  # Marcar despacho como True se necessário
                        }
                    )
                    processos_inseridos += 1

                except Exception as e:  # Linha 236 - Garantindo indentação correta
                    print(f"Erro ao importar processo {row.get('numeroProcesso', 'Desconhecido')}: {str(e)}")
                    messages.warning(request, f"Erro ao importar processo {row.get('numeroProcesso', 'Desconhecido')}: {str(e)}")
                    continue

            messages.success(
                request,
                f"Importação concluída: {processos_inseridos} processos inseridos, {processos_ignorados} processos ignorados."
            )
            return HttpResponseRedirect(request.path)

        except pd.errors.ParserError as e:
            messages.error(request, f"Erro ao ler o arquivo CSV: {str(e)}")
            return render(request, 'importar_processos.html')
        except DatabaseError as e:
            messages.error(request, f"Erro ao salvar no banco de dados: {str(e)}")
            return render(request, 'importar_processos.html')
        except Exception as e:
            messages.error(request, f"Erro ao processar o arquivo: {str(e)}")
            return render(request, 'importar_processos.html')

    return render(request, 'importar_processos.html')

locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')


@login_required
def definir_tema(request, pk):
    """Processa o formulário do modal e define/atualiza o Tema do Processo."""
    processo = get_object_or_404(Processo, pk=pk)
    
    if request.method == 'POST':
        tema_id = request.POST.get('tema_id')
        if tema_id:
            tema = get_object_or_404(Tema, pk=tema_id)
            processo.tema = tema
            processo.save()
            # Verificar se a requisição é AJAX
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Tema atualizado com sucesso!',
                    'tema_nome': tema.nome,
                })
            else:
                messages.success(request, "Tema atualizado com sucesso!")
                return redirect('processo_list')
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Selecione um tema válido.',
                }, status=400)
            else:
                messages.error(request, "Selecione um tema válido.")
                return redirect('processo_list')
    
    return redirect('processo_list')

class ProcessoListView(LoginRequiredMixin, ListView):
    model = Processo
    template_name = 'processo_list.html'
    context_object_name = 'processos'
    paginate_by = 20

    def get_queryset(self):
        """
        Filtra os processos com base nos parâmetros fornecidos na URL.
        Garante que processos na fase "Processo Concluído" apareçam quando o filtro de status for "Concluído".
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

        # 🔹 Obtém a última fase do processo (incluindo todas as fases, independentemente do status)
        latest_fase = Subquery(
            ProcessoAndamento.objects.filter(
                processo=OuterRef('id')
            ).order_by('-dt_criacao').values('fase__fase')[:1]
        )

        # 🔹 Anota a fase atual (sem excluir "Processo Concluído")
        queryset = queryset.annotate(fase_atual=latest_fase)

        # 🔹 Filtra pelo status (pendente ou concluído)
        if status == "concluído":
            queryset = queryset.filter(concluido=True)
        else:
            queryset = queryset.filter(concluido=False)

        # 🔹 Aplica filtros adicionais
        if numero_processo:
            numero_processo = numero_processo.strip()[:10]
        filtros = {
            'fase_atual': fase_atual,
            'camara__camara': camara,
            'tipo__tipo': tipo,
            'especie__especie': especie,
            'numero_processo__icontains': numero_processo,
        }
        if tema:
            filtros['tema__nome'] = tema

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

        # Obtém os dados do POST e remove espaços em branco
        tipo_id = request.POST.get("tipo", "").strip()
        resultado_id = request.POST.get("resultado", "").strip()  # opcional
        despacho_val = request.POST.get("despacho")  # vem como "on" se marcado

        # Valida se o campo 'tipo' foi preenchido
        if not tipo_id:
            return JsonResponse(
                {'error': 'Por favor, selecione o Tipo antes de salvar.'},
                status=400
            )

        # Converte o id do tipo para instância do modelo
        tipo = get_object_or_404(Tipo, id=tipo_id)

        # Converte o id do resultado, se enviado; caso contrário, mantém como None
        if resultado_id:
            resultado = get_object_or_404(Resultado, id=resultado_id)
        else:
            resultado = None

        # Atualiza os valores no objeto processo
        processo.tipo = tipo
        processo.resultado = resultado
        processo.despacho = despacho_val == "on"  # Checkbox: True se marcado, False caso contrário
        processo.save()

        print(f"✅ Processo atualizado - Tipo: {processo.tipo}, Resultado: {processo.resultado}, Despacho: {processo.despacho}")

        # Redireciona para a página desejada com o objeto atualizado
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
        # Obtém o parâmetro 'origem' do formulário
        origem = self.request.POST.get('origem', 'andamento_list')
        # Obtém o processo associado ao andamento
        processo_id = self.object.processo.id

        if origem == 'home':
            base_url = reverse('home')
        else:
            base_url = f"{reverse('andamento_list')}?processo={processo_id}"

        # Se houver a query string dos filtros, adicione-a
        next_query = self.request.POST.get('next')
        if next_query:
            if '?' in base_url:
                return f"{base_url}&{next_query}"
            else:
                return f"{base_url}?{next_query}"
        return base_url

    def get_context_data(self, **kwargs):
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

        # Verifica se o usuário logado é o atribuído ao andamento
        if request.user != andamento.usuario:
            return HttpResponseForbidden("Você não tem permissão para movimentar este andamento.")

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
        
        # Verificar se o processo está na fase "L. PJE"
        if andamento.fase.fase != "L. PJE":
            messages.error(request, "Processo só pode ser concluído na fase L. PJE.")
            origem = request.POST.get("origem", "andamento_list")
            return redirect("home" if origem == "home" else f"andamento_list?processo={andamento.processo.pk}")

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

        # Remover o processo do "Meu Dia" (deletar o registro em TarefaDoDia)
        TarefaDoDia.objects.filter(usuario=request.user, processo=processo).delete()

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

from django.http import HttpResponse
from django.db.models.functions import Left
import openpyxl
from openpyxl.styles import Font, Alignment

def export_processos_xlsx(request):
    """Exporta os processos para um arquivo Excel (.xlsx) com base nos filtros aplicados na ProcessoListView"""
    
    # Instancia a ProcessoListView para reutilizar a lógica de filtros
    view = ProcessoListView()
    view.request = request  # Passa a requisição para a view
    processos = view.get_queryset()

    # 🔹 Obtém o link_doc do andamento com fase "L. PJE" (o mais recente, se houver múltiplos)
    l_pje_link_doc = Subquery(
        ProcessoAndamento.objects.filter(
            processo=OuterRef('id'),
            fase__fase="L. PJE"  # Filtra pela fase "L. PJE"
        ).order_by('-dt_criacao').values('link_doc')[:1]
    )

    # 🔹 Otimiza a query com select_related e anota o link_doc
    processos = processos.select_related('especie', 'usuario', 'resultado', 'tipo', 'camara', 'tema').annotate(
        l_pje_link_doc=l_pje_link_doc
    )

    # Criar um novo workbook (arquivo Excel)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Processos"

    # Definir os cabeçalhos da planilha, incluindo as novas colunas
    headers = [
        "Número do Processo", "Data de Distribuição", "Espécie", "Resultado", "Tipo",
        "Câmara", "Usuário Responsável", "Data de Julgamento", "Prazo",
        "Data de Criação", "Última Atualização", "Concluído", "Data de Conclusão",
        "Tema", "Despacho", "Link do Documento"
    ]
    ws.append(headers)

    # Verifica se há processos; se não, adiciona uma mensagem
    if not processos:
        ws.append(["Nenhum processo encontrado com os filtros aplicados."])
    else:
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
                processo.dt_conclusao.strftime('%d/%m/%Y %H:%M') if processo.dt_conclusao else "",
                processo.tema.nome if processo.tema else "",  # Novo campo: Tema
                "Sim" if processo.despacho else "Não",        # Novo campo: Despacho
                processo.l_pje_link_doc or ""                 # Novo campo: Link do Documento (fase L. PJE)
            ])

    # Estilizar cabeçalhos
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')

    # Ajustar largura das colunas automaticamente
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column].width = adjusted_width

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


class ProcessosCreateListAPIView(generics.ListCreateAPIView):
    queryset = models.Processo.objects.all()
    serializer_class = serializers.ProcessoSerializer

def get_queryset(self):
        queryset = models.Processo.objects.all()
        request = self.request

        numero = request.GET.get('numero_processo')
        concluido = request.GET.get('concluido')

        if numero:
            queryset = queryset.filter(numero_processo=numero)

        if concluido is not None:
            concluido_bool = concluido.lower() == 'true'
            queryset = queryset.filter(concluido=concluido_bool)

        return queryset

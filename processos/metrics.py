from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField, Subquery, OuterRef,Q
from processos.models import Processo, ProcessoAndamento

def get_advanced_metrics(assessor=None, mes_distribuicao=None, data_inicio=None, data_fim=None):
    """
    Calcula métricas avançadas sobre processos e andamentos.
    """
    queryset = Processo.objects.all()



    # Aplica filtros opcionais
    if assessor:
        queryset = queryset.filter(usuario_id=assessor)
    if mes_distribuicao:
        queryset = queryset.filter(data_dist__month=mes_distribuicao)

        # Filtro por data inicial e final
    if data_inicio:
        queryset = queryset.filter(data_dist__gte=data_inicio)
    if data_fim:
        queryset = queryset.filter(data_dist__lte=data_fim)

    # 🔹 Calcula o total de processos para o cálculo da porcentagem
    total_processos = queryset.count()

    # Função para calcular porcentagem e evitar divisão por zero
    def calculate_percentage(value):
        return round((value / total_processos) * 100, 1) if total_processos > 0 else 0
    
        # Criar lista detalhada de processos
    detalhes_processos = list(
        queryset.values(
            "id",
            "numero_processo",
            "usuario__first_name",
            "usuario__last_name",
            "especie__sigla",
            "tipo__tipo",
            "camara__camara",
            "data_dist",
            "dt_prazo",
            "dt_conclusao",
            "concluido",
        ).order_by("-data_dist")
    )

    # 🔹 Processos por Espécie
    species_counts = queryset.values('especie__sigla').annotate(total=Count('id')).order_by('especie__sigla')
    
    # 🔹 Processos por Tipo
    type_counts = queryset.values('tipo__tipo').annotate(total=Count('id')).order_by('tipo__tipo')

    # 🔹 Processos por Câmara
    camara_counts = queryset.values('camara__camara').annotate(total=Count('id')).order_by('camara__camara')

    # 🔹 Processos por Resultado
    resultado_counts = queryset.values('resultado__resultado').annotate(total=Count('id')).order_by('resultado__resultado')

    # 🔹 Processos por Assessor
    assessor_counts = queryset.values('usuario__first_name', 'usuario__last_name').annotate(total=Count('id')).order_by('usuario__first_name')

    # 🔹 Contagem de Processos
    total_processos = queryset.count()
    total_concluidos = queryset.filter(concluido=True).count()
    total_pendentes = queryset.filter(concluido=False).count()

    # Evita divisão por zero
    def calculate_percentage(value):
        return round((value / total_processos) * 100, 1) if total_processos > 0 else 0

    # 🔹 Processos por Andamento (Somente NÃO Concluídos)
    andamento_queryset = ProcessoAndamento.objects.filter(~Q(status__status="Concluído")) \
        .values('andamento').annotate(total=Count('id')).order_by('andamento')

    andamento_data = {
        "labels": [item["andamento"] for item in andamento_queryset],
        "data": [item["total"] for item in andamento_queryset],
    }

 # 🔹 Tempo Médio de Processos (Data de Distribuição até Conclusão)
    average_process_time = queryset.filter(
        data_dist__isnull=False,
        dt_conclusao__isnull=False,
        dt_conclusao__gte=F('data_dist')  
    ).annotate(
        process_duration=ExpressionWrapper(
            F('dt_conclusao') - F('data_dist'),
            output_field=DurationField()
        )
    ).aggregate(avg_duration=Avg('process_duration'))['avg_duration']

    # 🔹 Tempo Médio por Tipo de Andamento (Duração do andamento)
    andamento_queryset = ProcessoAndamento.objects.filter(
        dt_inicio__isnull=False,
        dt_conclusao__isnull=False,
        dt_conclusao__gte=F('dt_inicio')
    )

    andamento_durations = {}
    for tipo in ["Elaboração", "Correção", "Revisão", "L. PJE"]:
        duration = andamento_queryset.filter(
            andamento__icontains=tipo
        ).annotate(
            andamento_duration=ExpressionWrapper(
                F('dt_conclusao') - F('dt_inicio'),
                output_field=DurationField()
            )
        ).aggregate(avg_duration=Avg('andamento_duration'))['avg_duration']
        
        andamento_durations[tipo] = duration

    # 🔹 Cálculo do tempo aguardando início do andamento
    andamento_queryset_waiting = ProcessoAndamento.objects.filter(
        dt_inicio__isnull=False
    )

    # Subquery para obter a conclusão do andamento anterior
    subquery_andamento_anterior = ProcessoAndamento.objects.filter(
        processo=OuterRef('processo'),
        dt_conclusao__lt=OuterRef('dt_inicio')  # Pegamos o andamento anterior
    ).order_by('-dt_conclusao').values('dt_conclusao')[:1]

    # Tempo médio aguardando início dos andamentos
    andamento_queryset_waiting = andamento_queryset_waiting.annotate(
        andamento_anterior_dt_conclusao=Subquery(subquery_andamento_anterior),
        waiting_duration=ExpressionWrapper(
            F('dt_inicio') - F('andamento_anterior_dt_conclusao'),
            output_field=DurationField()
        )
    )

    andamento_waiting_times = {}

    for tipo in ["Elaboração", "Correção", "Revisão", "L. PJE"]:
        waiting_time = andamento_queryset_waiting.filter(
            andamento__icontains=tipo
        ).aggregate(avg_waiting_time=Avg('waiting_duration'))['avg_waiting_time']

        andamento_waiting_times[tipo] = waiting_time

    # 🔹 Ajuste para garantir que o tempo médio aguardando a **Elaboração** seja calculado corretamente
    elaboracao_waiting_time = ProcessoAndamento.objects.filter(
        andamento__icontains="Elaboração",
        dt_inicio__isnull=False,
        processo__data_dist__isnull=False
    ).annotate(
        waiting_duration=ExpressionWrapper(
            F('dt_inicio') - F('processo__data_dist'),  # Correção: tempo de espera da Elaboração
            output_field=DurationField()
        )
    ).aggregate(avg_waiting_time=Avg('waiting_duration'))['avg_waiting_time']

    andamento_waiting_times["Elaboração"] = elaboracao_waiting_time

    # 🔹 Função para formatar duração corretamente
    def format_duration(duration):
        if duration:
            days = duration.days
            total_seconds = duration.total_seconds()
            hours, remainder = divmod(int(total_seconds), 3600)
            minutes, seconds = divmod(remainder, 60)

            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            return f"{seconds}s"

        return "N/A"
    # 🔹 Função para formatar duração corretamente
    def format_duration(duration, include_seconds=False):
        if isinstance(duration, str):  # Se já for "N/A", retorna direto
            return duration
        if duration:
            days = duration.days  # Obtém os dias corretamente
            total_seconds = duration.total_seconds() - (days * 86400)  # Remove os dias da contagem de segundos
            hours, remainder = divmod(int(total_seconds), 3600)  # Obtém as horas restantes
            minutes, seconds = divmod(remainder, 60)  # Obtém minutos e segundos restantes

            if include_seconds:
                if days > 0:
                    return f"{days}d {hours}h {minutes}m {seconds}s"
                elif hours > 0:
                    return f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    return f"{minutes}m {seconds}s"
                return f"{seconds}s"

            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"

        return "N/A"

    
    assessor_process_data = Processo.objects.values(
        'usuario__id', 'usuario__first_name', 'usuario__last_name'
    ).annotate(
        total=Count('id'),
        total_concluidos=Count('id', filter=Q(concluido=True)),
        total_pendentes=Count('id', filter=Q(concluido=False))
    ).order_by('usuario__first_name')

    return {
        "species_data": {
            "labels": [item['especie__sigla'] or 'Sem Sigla' for item in species_counts],
            "data": [item['total'] for item in species_counts],
            "percentages": [calculate_percentage(item['total']) for item in species_counts],
        },
        "type_data": {
            "labels": [item['tipo__tipo'] or 'Sem Tipo' for item in type_counts],
            "data": [item['total'] for item in type_counts],
            "percentages": [calculate_percentage(item['total']) for item in type_counts],
        },
        "camara_data": {
            "labels": [item['camara__camara'] or 'Sem Câmara' for item in camara_counts],
            "data": [item['total'] for item in camara_counts],
            "percentages": [calculate_percentage(item['total']) for item in camara_counts],
        },
        "resultado_data": {
            "labels": [item['resultado__resultado'] or 'Sem Resultado' for item in resultado_counts],
            "data": [item['total'] for item in resultado_counts],
            "percentages": [calculate_percentage(item['total']) for item in resultado_counts],
        },
        "assessor_data": {
            "labels": [f"{item['usuario__first_name']} {item['usuario__last_name']}" if item['usuario__first_name'] else 'Sem Assessor' for item in assessor_counts],
            "data": [item['total'] for item in assessor_counts],
            "percentages": [calculate_percentage(item['total']) for item in assessor_counts],
        },
        "average_process_time": format_duration(average_process_time, include_seconds=True),
        "andamento_durations": {
            tipo: format_duration(andamento_durations[tipo], include_seconds=True) if andamento_durations[tipo] else "N/A"
            for tipo in andamento_durations
        },
        "andamento_waiting_times": {
            tipo: format_duration(andamento_waiting_times[tipo], include_seconds=True) if andamento_waiting_times[tipo] else "N/A"
            for tipo in andamento_waiting_times
        },
        "detalhes_processos": detalhes_processos,
        "total_processos": total_processos,
        "total_concluidos": total_concluidos,
        "total_pendentes": total_pendentes,
        "andamento_data": andamento_data,
        "porcentagem_concluidos": calculate_percentage(total_concluidos),
        "porcentagem_pendentes": calculate_percentage(total_pendentes),
        "assessor_process_data": [
                    {
                        "id": item['usuario__id'],
                        "name": f"{item['usuario__first_name']} {item['usuario__last_name']}",
                        "total": item['total'],
                        "concluidos": item['total_concluidos'],
                        "pendentes": item['total_pendentes']
                    }
                    for item in assessor_process_data
                ],
}
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db.models import Count
from django.utils import timezone
from processos.models import Processo, ProcessoAndamento
from django.contrib.auth.models import User
import locale

class Command(BaseCommand):
    help = 'Aquece o cache para os gráficos pesados do dashboard'

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando warmup do cache...")

        # ----------------------------------------------------
        # 1. FASES DATA GRAFICO
        # ----------------------------------------------------
        self.stdout.write("Calculando fases_data_grafico...")
        try:
            total_pendentes = Processo.objects.filter(concluido=False).count()
            
            # OTIMIZAÇÃO SUPREMA: SQL em tabela única sem usar "JOIN".
            # O JOIN obriga o PostgreSQL a cruzar tabelas e estoura a CPU/Disco.
            # Vamos buscar os IDs das fases e contar tudo de forma simples.
            from django.db import connection
            from processos.models import Status, Fase
            
            # 1. Descobrir os IDs dos status alvo rapidamente
            status_ids = list(Status.objects.filter(status__in=['Não iniciado', 'Em andamento']).values_list('id', flat=True))
            
            if status_ids:
                status_ids_str = ','.join(map(str, status_ids))
                # 2. Fazer a conta diretão na tabela, sem JOIN nenhum!
                query = f"""
                    SELECT fase_id, COUNT(id)
                    FROM processos_processoandamento
                    WHERE status_id IN ({status_ids_str})
                    GROUP BY fase_id
                """
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    resultados_brutos = cursor.fetchall()
            else:
                resultados_brutos = []
                
            # 3. Converter os IDs para os nomes das Fases na memória do Python
            mapa_fases = dict(Fase.objects.values_list('id', 'fase'))
            
            fases_nomes = []
            fases_quantidades = []
            
            for fase_id, qtd in resultados_brutos:
                nome_fase = mapa_fases.get(fase_id, 'Desconhecida')
                if nome_fase in ['Processo Concluído', 'Processo Concluido']:
                    continue
                fases_nomes.append(nome_fase)
                fases_quantidades.append(qtd)

            # Ordenar para ficar bonito no gráfico
            dados_ordenados = sorted(zip(fases_nomes, fases_quantidades), key=lambda x: x[0])
            fases_nomes = [x[0] for x in dados_ordenados]
            fases_quantidades = [x[1] for x in dados_ordenados]

            data_fases = {
                'labels': fases_nomes + ['Total Pendentes'],
                'datasets': [
                    {
                        'label': 'Por Fase',
                        'data': fases_quantidades + [total_pendentes],
                        'backgroundColor': ['#3B82F6'] * len(fases_nomes) + ['#EF4444']
                    }
                ]
            }
            # Salva no cache por 24 horas (86400 segundos)
            cache.set('fases_data_grafico', data_fases, 86400)
            self.stdout.write(self.style.SUCCESS('fases_data_grafico aquecido com sucesso.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao calcular fases_data_grafico: {str(e)}'))

        # ----------------------------------------------------
        # 2. RANKING MES DATA GRAFICO
        # ----------------------------------------------------
        self.stdout.write("Calculando ranking_mes_data_grafico...")
        try:
            try:
                locale.setlocale(locale.LC_TIME, 'pt_BR.utf8')
            except:
                pass
            
            hoje = timezone.now().date()
            inicio_mes = hoje.replace(day=1)
            
            assessores_ids = User.objects.filter(profile__funcao="Assessor(a)").values_list('id', flat=True)

            # ULTRA-LEVE: Busca apenas os processos concluídos no mês e faz a contagem em Python, sem GROUP BY no banco
            concluidos_mes_queryset = Processo.objects.filter(
                dt_conclusao__gte=inicio_mes,
                concluido=True,
                usuario_id__in=assessores_ids
            ).values('usuario__first_name', 'usuario__last_name')
            
            from collections import Counter
            contagem = Counter([f"{p['usuario__first_name']} {p['usuario__last_name']}".strip() for p in concluidos_mes_queryset])
            
            # Ordenar por quantidade decrescente
            ranking = sorted(contagem.items(), key=lambda x: x[1], reverse=True)
            
            labels = [r[0] for r in ranking]
            data_vals = [r[1] for r in ranking]

            background_colors = []
            for i in range(len(labels)):
                if i == 0:
                    background_colors.append('#F59E0B') # Ouro
                elif i == 1:
                    background_colors.append('#9CA3AF') # Prata
                elif i == 2:
                    background_colors.append('#B45309') # Bronze
                else:
                    background_colors.append('#3B82F6') # Azul

            nome_mes = hoje.strftime("%B").capitalize()
            
            data_ranking = {
                'labels': labels,
                'datasets': [
                    {
                        'label': f'Processos Concluídos em {nome_mes}',
                        'data': data_vals,
                        'backgroundColor': background_colors
                    }
                ]
            }
            # Salva no cache por 24 horas (86400 segundos)
            cache.set('ranking_mes_data_grafico', data_ranking, 86400)
            self.stdout.write(self.style.SUCCESS('ranking_mes_data_grafico aquecido com sucesso.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao calcular ranking_mes_data_grafico: {str(e)}'))

        # ----------------------------------------------------
        # 3. ENTRADAS E SAÍDAS DE HOJE
        # ----------------------------------------------------
        self.stdout.write("Calculando es_assessor_hoje_data_grafico...")
        try:
            hoje = timezone.now().date()
            entradas_hoje = (
                Processo.objects.filter(data_dist__date=hoje, usuario__isnull=False)
                .values('usuario__first_name', 'usuario__last_name')
                .annotate(quantidade=Count('id'))
            )
            saidas_hoje = (
                Processo.objects.filter(dt_conclusao__date=hoje, concluido=True, usuario__isnull=False)
                .values('usuario__first_name', 'usuario__last_name')
                .annotate(quantidade=Count('id'))
            )

            assessores_nomes = list(set(
                [f"{e['usuario__first_name']} {e['usuario__last_name']}".strip() for e in entradas_hoje] +
                [f"{s['usuario__first_name']} {s['usuario__last_name']}".strip() for s in saidas_hoje]
            ))

            entradas_dict = {f"{e['usuario__first_name']} {e['usuario__last_name']}".strip(): e['quantidade'] for e in entradas_hoje}
            saidas_dict = {f"{s['usuario__first_name']} {s['usuario__last_name']}".strip(): s['quantidade'] for s in saidas_hoje}
            entradas_vals = [entradas_dict.get(nome, 0) for nome in assessores_nomes]
            saidas_vals = [saidas_dict.get(nome, 0) for nome in assessores_nomes]

            data_es = {
                'labels': assessores_nomes,
                'datasets': [
                    {'label': 'Entradas', 'data': entradas_vals, 'backgroundColor': '#3B82F6'},
                    {'label': 'Saídas', 'data': saidas_vals, 'backgroundColor': '#F59E0B'}
                ]
            }
            cache.set('es_assessor_hoje_data_grafico', data_es, 86400)
            self.stdout.write(self.style.SUCCESS('es_assessor_hoje_data_grafico aquecido com sucesso.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao calcular es_assessor_hoje_data_grafico: {str(e)}'))

        # ----------------------------------------------------
        # 4. PROCESSOS POR ESPÉCIE
        # ----------------------------------------------------
        self.stdout.write("Calculando processos_por_especie...")
        try:
            processos_por_especie = (
                Processo.objects.filter(concluido=False)
                .values('especie__especie')
                .annotate(quantidade=Count('id'))
                .order_by('especie__especie')
            )
            especies_nomes = [e['especie__especie'] if e['especie__especie'] else "Sem Espécie" for e in processos_por_especie]
            especies_quantidades = [e['quantidade'] for e in processos_por_especie]

            data_especies = {
                'labels': especies_nomes,
                'datasets': [{
                    'label': 'Processos por Espécie',
                    'data': especies_quantidades,
                    'backgroundColor': '#10B981'
                }]
            }
            cache.set('processos_por_especie', data_especies, 86400)
            self.stdout.write(self.style.SUCCESS('processos_por_especie aquecido com sucesso.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao calcular processos_por_especie: {str(e)}'))

        self.stdout.write(self.style.SUCCESS("Warmup concluído!"))

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
            
            # OTIMIZAÇÃO EXTREMA: Sem nenhum JOIN. Busca apenas strings e conta no Python
            from processos.models import Status
            from collections import Counter

            # 1. Pega os IDs dos status alvo
            status_alvo_ids = Status.objects.filter(
                status__in=["Não iniciado", "Em andamento"]
            ).values_list('id', flat=True)

            # 2. Busca apenas o nome da fase diretamente (faz 1 único join simples ou retorna nulo se não otimizado, mas evita o GROUP BY e ORDER BY pesado do banco)
            fases_raw = ProcessoAndamento.objects.filter(
                status_id__in=status_alvo_ids
            ).values_list('fase__fase', flat=True)

            # 3. Conta na RAM do servidor usando C puro do Python (extremamente rápido)
            contagem = Counter([f if f else "Sem Fase" for f in fases_raw])
            
            # 4. Ordena alfabeticamente
            fases_ordenadas = sorted(contagem.items(), key=lambda x: x[0])
            
            fases_nomes = [item[0] for item in fases_ordenadas]
            fases_quantidades = [item[1] for item in fases_ordenadas]

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

        self.stdout.write(self.style.SUCCESS("Warmup concluído!"))

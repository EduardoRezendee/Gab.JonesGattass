from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from .models import Processo, Fase, ProcessoAndamento, Status
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
import threading
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Processo)
def criar_andamento_inicial(sender, instance, created, **kwargs):
    if created:
        try:
            fase_elaboracao = Fase.objects.get(fase="Elaboração")
            status_nao_iniciado = Status.objects.get(status="Não iniciado")
            ProcessoAndamento.objects.create(
                processo=instance,
                andamento="Início da Elaboração",
                fase=fase_elaboracao,
                usuario=instance.usuario,
                status=status_nao_iniciado
            )
        except Fase.DoesNotExist:
            print("A fase 'Elaboração' não foi encontrada.")
        except Status.DoesNotExist:
            print("O status 'Não iniciado' não foi encontrado.")


# Lista de fases que NÃO devem ser notificadas nos andamentos
EXCLUDED_PHASES = ["Processo Concluído", "Elaboração"]


# ══════════════════════════════════════════════════════════════════
#  SIGNAL: Notificação ao criar Plantão com status Pendente
# ══════════════════════════════════════════════════════════════════

@receiver(post_save, sender='processos.Ferias')
def notificar_assessor_ferias(sender, instance, created, **kwargs):
    """
    Ao criar Férias com status 'pendente', gera NotificacaoInterna
    para o assessor, pedindo confirmação de ciência.
    """
    if not created or instance.status != 'pendente':
        return
    try:
        from .models import NotificacaoInterna
        NotificacaoInterna.objects.create(
            destinatario=instance.usuario,
            tipo='ferias',
            titulo='Férias Registradas — Confirme Ciência',
            mensagem=(
                f'Suas férias foram registradas de '
                f'{instance.data_inicio.strftime("%d/%m/%Y")} a '
                f'{instance.data_fim.strftime("%d/%m/%Y")}. '
                f'Por favor, confirme sua ciência.'
            ),
            link='/gestao/ferias-plantoes/',
        )
        logger.info(f"[Signal] Notificação de férias criada para {instance.usuario.get_full_name()}")
    except Exception as e:
        logger.error(f"[Signal] Erro ao criar notificação de férias: {e}")


@receiver(post_save, sender='processos.Plantao')
def notificar_assessor_plantao(sender, instance, created, **kwargs):
    """
    Ao criar um Plantão com status 'pendente', gera uma NotificacaoInterna
    para o assessor escalado, informando sobre o novo plantão.
    """
    if not created:
        return
    if instance.status != 'pendente':
        return

    try:
        from .models import NotificacaoInterna
        NotificacaoInterna.objects.create(
            destinatario=instance.usuario,
            tipo='plantao',
            titulo='Novo Plantão Escalado',
            mensagem=(
                f'Você foi escalado para plantão de '
                f'{instance.data_inicio.strftime("%d/%m/%Y")} a '
                f'{instance.data_fim.strftime("%d/%m/%Y")}. '
                f'Por favor, confirme sua ciência.'
            ),
            link='/gestao/ferias-plantoes/',
        )
        logger.info(
            f"[Signal] Notificação de plantão criada para {instance.usuario.get_full_name()}"
        )
    except Exception as e:
        logger.error(f"[Signal] Erro ao criar notificação de plantão: {e}")

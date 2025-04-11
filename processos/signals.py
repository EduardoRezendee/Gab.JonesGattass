from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from .models import Processo, Fase, ProcessoAndamento, Status
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
import threading
import logging

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


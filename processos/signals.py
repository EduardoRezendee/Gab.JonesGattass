from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from .models import Processo, Fase, Andamento, Status
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
import threading

@receiver(post_save, sender=Processo)
def criar_andamento_inicial(sender, instance, created, **kwargs):
    if created:
        try:
            fase_elaboracao = Fase.objects.get(fase="Elaboração")
            status_nao_iniciado = Status.objects.get(status="Não iniciado")
            Andamento.objects.create(
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


@receiver(post_save, sender=Processo)
def send_process_email_notification(sender, instance, created, **kwargs):
    if not created:  # O e-mail será enviado apenas na criação do processo
        return

    email_subject = f"Novo Processo Atribuído: {instance.numero_processo}"

    # URL para os andamentos do processo
    andamento_url = f"http://127.0.0.1:8000{reverse('andamento_list')}?processo={instance.id}"

    # Renderiza a mensagem do e-mail usando o template atualizado
    email_message = render_to_string('process_notification.html', {
        'numero_processo': instance.numero_processo,
        'data_dist': instance.data_dist,
        'especie': instance.especie,
        'dt_prazo': instance.dt_prazo,
        'andamento_url': andamento_url,
        'message_action': "Um novo processo foi atribuído a você.",
        'year': 2025,  # Ajustar automaticamente com datetime se necessário
    })

    # Envio do e-mail de forma assíncrona
    if instance.usuario and instance.usuario.email:
        def send_email():
            try:
                send_mail(
                    email_subject,
                    '',  # Corpo vazio porque estamos enviando HTML
                    settings.EMAIL_HOST_USER,
                    [instance.usuario.email],
                    fail_silently=False,
                    html_message=email_message,  # Envia o e-mail como HTML
                )
            except Exception as e:
                print(f"Erro ao enviar e-mail: {e}")

        threading.Thread(target=send_email).start()
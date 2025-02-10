from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from .models import Processo, Fase, Andamento, Status
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
import threading
from .whatsapp_notifications import send_whatsapp_message
import logging

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



# Lista de fases que NÃO devem ser notificadas nos andamentos
EXCLUDED_PHASES = ["Processo Concluído", "Elaboração"]

@receiver(post_save, sender=Processo)
def send_process_email_notification(sender, instance, created, **kwargs):
    """
    Envia notificação sempre que um novo processo for criado.
    """
    if created:  # Só envia e-mail na criação do processo
        email_subject = f"Novo Processo Atribuído: {instance.numero_processo}"
        
        # URL para os andamentos do processo
        andamento_url = f"https://gestaogabineteccs.com{reverse('andamento_list')}?processo={instance.id}"

        email_message = render_to_string('process_notification.html', {
            'message_action': "Um novo processo foi atribuído a você.",  # Primeira linha da mensagem
            'numero_processo': instance.numero_processo,
            'data_dist': instance.data_dist,
            'especie': instance.especie,
            'dt_prazo': instance.dt_prazo,
            'andamento_url': andamento_url,
            'year': 2025,
        })

        # Envio do e-mail de forma assíncrona
        if instance.usuario and instance.usuario.email:
            def send_email():
                try:
                    send_mail(
                        email_subject,
                        '',  # Corpo vazio pois estamos enviando HTML
                        settings.EMAIL_HOST_USER,
                        [instance.usuario.email],
                        fail_silently=False,
                        html_message=email_message,
                    )
                except Exception as e:
                    print(f"Erro ao enviar e-mail: {e}")

            threading.Thread(target=send_email).start()

@receiver(post_save, sender=Andamento)
def send_andamento_email_notification(sender, instance, created, **kwargs):
    """
    Envia notificação quando um andamento relevante é atribuído,
    excluindo "Processo Concluído" e "Elaboração".
    """
    if created and instance.fase.fase not in EXCLUDED_PHASES:
        # Nome do andamento (Correção, Revisão, etc.) - Aparece no início da mensagem
        nome_andamento = instance.fase.fase

        email_subject = f"Atualização no Processo: {instance.processo.numero_processo}"

        # URL para ver os detalhes do andamento
        andamento_url = f"https://gestaogabineteccs.com{reverse('andamento_list')}?processo={instance.processo.id}"

        email_message = render_to_string('process_notification.html', {
            'message_action': f"O processo teve um novo andamento: {nome_andamento}",  # Agora essa informação aparece primeiro
            'numero_processo': instance.processo.numero_processo,
            'data_dist': instance.processo.data_dist,
            'especie': instance.processo.especie,
            'dt_prazo': instance.processo.dt_prazo,
            'andamento_url': andamento_url,
            'year': 2025,
        })

        # Envio do e-mail de forma assíncrona
        if instance.usuario and instance.usuario.email:
            def send_email():
                try:
                    send_mail(
                        email_subject,
                        '',
                        settings.EMAIL_HOST_USER,
                        [instance.usuario.email],
                        fail_silently=False,
                        html_message=email_message,
                    )
                except Exception as e:
                    print(f"Erro ao enviar e-mail: {e}")

            threading.Thread(target=send_email).start()

# Lista de fases que NÃO devem ser notificadas nos andamentos
EXCLUDED_PHASES = ["Processo Concluído", "Elaboração"]

# Configuração de logging
logger = logging.getLogger(__name__)

@receiver(post_save, sender=Processo)
def send_process_whatsapp_notification(sender, instance, created, **kwargs):
    """
    Envia uma notificação via WhatsApp quando um novo processo é criado.
    """
    try:
        if created and instance.usuario:
            # Construir URL do andamento do processo
            andamento_url = f"https://gestaogabineteccs.com{reverse('andamento_list')}?processo={instance.id}"

            message = (
                f"📌 *Novo Processo Atribuído*\n"
                f"🔹 *Número:* {instance.numero_processo}\n"
                f"📅 *Data:* {instance.data_dist.strftime('%d/%m/%Y') if instance.data_dist else 'Não informada'}\n"
                f"📄 *Espécie:* {instance.especie if instance.especie else 'Não informada'}\n"
                f"⏳ *Prazo:* {instance.dt_prazo.strftime('%d/%m/%Y') if instance.dt_prazo else 'Não informado'}\n"
                f"🔗 [Ver detalhes]({andamento_url})"
            )

            # Verifica se o usuário tem um perfil com número de telefone
            user_phone = getattr(instance.usuario, 'profile', None)
            if user_phone and getattr(user_phone, 'telefone', None):
                phone_number = user_phone.telefone
                send_whatsapp_message(phone_number, message)
                logger.info(f"✅ WhatsApp enviado para {phone_number} sobre o processo {instance.numero_processo}.")
            else:
                logger.warning(f"⚠️ Nenhum número de telefone encontrado para o usuário {instance.usuario}. WhatsApp não enviado.")
    except Exception as e:
        logger.error(f"❌ Erro ao enviar WhatsApp para processo {instance.numero_processo}: {e}")
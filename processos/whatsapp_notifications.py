import logging
from twilio.rest import Client
from django.conf import settings

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Verifica se as credenciais do Twilio estão configuradas
if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_WHATSAPP_NUMBER]):
    logger.error("❌ ERRO: Credenciais do Twilio não configuradas corretamente.")
    raise ValueError("As credenciais do Twilio estão ausentes. Verifique as configurações.")

# Inicializa o cliente Twilio
client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

def send_whatsapp_message(to_number, message):
    """
    Envia uma mensagem via WhatsApp usando Twilio.
    :param to_number: Número do destinatário no formato internacional (ex: +5511999999999)
    :param message: Conteúdo da mensagem
    """
    try:
        # Garante que o número tenha o prefixo correto do Twilio
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"

        twilio_number = settings.TWILIO_WHATSAPP_NUMBER

        message_obj = client.messages.create(
            from_=twilio_number,
            body=message,
            to=to_number
        )

        logger.info(f"✅ WhatsApp enviado para {to_number}. SID: {message_obj.sid}")
        return message_obj.sid  # Retorna o SID da mensagem enviada

    except Exception as e:
        logger.error(f"❌ Erro ao enviar WhatsApp para {to_number}: {e}")
        return None  # Retorna None em caso de erro

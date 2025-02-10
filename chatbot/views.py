import os
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from decouple import config
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from django.utils.timezone import now

# Configuração da API OpenAI
os.environ["OPENAI_API_KEY"] = config("OPENAI_API_KEY")

# Configurar logs para depuração
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    # Conectar ao banco de dados PostgreSQL
    db = SQLDatabase.from_uri(
        f"postgresql://{config('DB_USER')}:{config('DB_PASSWORD')}@{config('DB_HOST')}:{config('DB_PORT')}/{config('DB_NAME')}"
    )
except Exception as e:
    logger.error(f"Erro ao conectar ao banco de dados PostgreSQL: {e}")

# Utilizando GPT-4o Mini (mais barato e eficiente)
llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

# Criar o agente SQL
agent_executor = create_sql_agent(
    llm=llm,
    db=db,
    verbose=True,
)

# Lista de saudações para respostas amigáveis
SAUDACOES = ["olá", "oi", "bom dia", "boa tarde", "boa noite", "e aí"]

def chatbot(request):
    """ Renderiza a interface do Chatbot """
    return render(request, 'chat.html')

@login_required
def ask_chatbot(request):
    """ Processa perguntas enviadas pelo usuário e retorna respostas formatadas """
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido."}, status=405)

    question = request.GET.get("question", "").strip().lower()
    
    if not question:
        return JsonResponse({"response": "Por favor, faça uma pergunta válida."})

    user = request.user  # Obtém o usuário logado
    username = f"{user.first_name} {user.last_name}".strip() or user.username  # Nome formatado

    # Substituir "eu" pelo nome do usuário
    question = question.replace("eu", username)

    # Responder a saudações diretamente
    if question in SAUDACOES:
        return JsonResponse({"response": f"Olá, {username}! Como posso ajudar você hoje?"})

    try:
        queries = {
            f"quantos processos {username} tem": {
                "query": """
                    SELECT COUNT(*) 
                    FROM processos_processo 
                    WHERE usuario_id = (SELECT id FROM auth_user WHERE username = ?);
                """,
                "params": [user.username],  # Evita SQL Injection
                "custom_response": lambda result: f"Você, {username}, tem {result[0][0]} processos."
            },
            "quantos processos entraram hoje": {
                "query": """
                    SELECT COUNT(*) 
                    FROM processos_processo 
                    WHERE DATE(dt_criacao) = DATE(?);
                """,
                "params": [now().date()],  # Usa a data atual corretamente
                "custom_response": lambda result: f"Hoje entraram {result[0][0]} processos."
            },
            "processos em revisão": {
                "query": """
                    SELECT 
                        p.numero_processo, 
                        COALESCE(u.first_name || ' ' || u.last_name, 'Não atribuído') AS usuario, 
                        COALESCE(NULLIF(a.link_doc, ''), 'Sem documento disponível') AS link_doc
                    FROM processos_processo p
                    JOIN processos_andamento a ON a.processo_id = p.id
                    LEFT JOIN auth_user u ON p.usuario_id = u.id
                    WHERE a.status_id = (SELECT id FROM processos_status WHERE status = 'Em Revisão')
                    ORDER BY p.id DESC
                    LIMIT 10;
                """,
                "params": [],
                "custom_response": lambda result: (
                    "**📌 Processos em Revisão:**\n\n" +
                    "\n".join([
                        f"- **Número:** {row[0]}\n"
                        f"- **Responsável:** {row[1]}\n"
                        f"- **Documento:** {'[🔗 Acessar Documento](' + row[2] + ')' if row[2] and 'http' in row[2] else '🔗 Sem documento disponível'}\n"
                        for row in result
                    ])
                    if result else "Nenhum processo em revisão encontrado."
                )
            }
        }

        # Verifica se a pergunta do usuário corresponde a alguma consulta SQL definida
        for key, value in queries.items():
            if key in question:
                try:
                    result = db.run(value["query"], value["params"]) or []

                    # Resposta personalizada
                    if "custom_response" in value and result:
                        response = value["custom_response"](result)
                        return JsonResponse({"response": response})

                    return JsonResponse({"response": "Nenhum registro encontrado."})

                except Exception as sql_error:
                    logger.error(f"Erro ao executar consulta SQL: {sql_error}")
                    return JsonResponse({"response": "Erro ao acessar os dados do banco. Verifique a conexão e tente novamente."})

        # Se não for uma saudação e não corresponder a uma consulta SQL, passa para o GPT responder
        prompt = f"""
        Você é um assistente especializado em consultas SQL para um sistema de gabinete jurídico.
        Sempre responda em **português brasileiro**, de forma clara e objetiva.

        Se a pergunta for irrelevante ou o banco não tiver resposta, avise educadamente.

        📌 **Pergunta do usuário:** {question}
        """

        try:
            response = agent_executor.invoke({"input": prompt})
            resposta_final = response.get("output", "").strip()

            if not resposta_final:
                return JsonResponse({"response": "Não encontrei informações relevantes para essa pergunta."})

            return JsonResponse({"response": resposta_final})
        except Exception as gpt_error:
            logger.error(f"Erro na API OpenAI: {gpt_error}")
            return JsonResponse({"response": "Erro ao processar sua pergunta. Tente novamente mais tarde."})

    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        return JsonResponse({"error": "Ocorreu um erro ao processar sua pergunta. Tente novamente mais tarde."})

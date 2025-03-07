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
from urllib.parse import quote_plus
from django.views.decorators.http import require_GET

# Configuração da API OpenAI
os.environ["OPENAI_API_KEY"] = config("OPENAI_API_KEY")

# Configurar logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Retorna uma conexão ao banco de dados PostgreSQL."""
    try:
        escaped_password = quote_plus(config("DB_PASSWORD"))
        db_uri = f"postgresql+psycopg2://{config('DB_USER')}:{escaped_password}@{config('DB_HOST')}:{config('DB_PORT')}/{config('DB_NAME')}"
        logger.info(f"Tentando conectar ao banco: {db_uri}")
        return SQLDatabase.from_uri(db_uri)
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao banco: {e}")
        return None

# Inicializa conexão e agente apenas quando necessário
db = get_db_connection()
llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0) if db else None
agent_executor = create_sql_agent(llm=llm, db=db, verbose=True) if db else None

SAUDACOES = ["olá", "oi", "bom dia", "boa tarde", "boa noite", "e aí"]

def chatbot(request):
    """Renderiza a interface do Chatbot."""
    return render(request, 'chat.html')

@require_GET
@login_required
def ask_chatbot(request):
    """Processa perguntas enviadas pelo usuário e retorna respostas formatadas."""
    if not db or not agent_executor:
        return JsonResponse({"response": "O chatbot está indisponível devido a problemas de conexão com o banco."})

    question = request.GET.get("question", "").strip().lower()
    if not question:
        return JsonResponse({"response": "Por favor, faça uma pergunta válida."})

    user = request.user
    username = f"{user.first_name} {user.last_name}".strip() or user.username
    question = question.replace("eu", username)

    if question in SAUDACOES:
        return JsonResponse({"response": f"Olá, {username}! Como posso ajudar você hoje?"})

    # Dicionário de consultas pré-definidas
    queries = {
        f"quantos processos {username} tem": {
            "query": "SELECT COUNT(*) FROM processos_processo WHERE usuario_id = (SELECT id FROM auth_user WHERE username = %s);",
            "params": [user.username],
            "custom_response": lambda result: f"Você, {username}, tem {result[0][0]} processos."
        },
        "quantos processos entraram hoje": {
            "query": "SELECT COUNT(*) FROM processos_processo WHERE DATE(data_dist) = DATE(%s);",
            "params": [now().date()],
            "custom_response": lambda result: f"Hoje entraram {result[0][0]} processos."
        },
        "processos em revisão": {
            "query": """
                SELECT p.numero_processo, COALESCE(u.first_name || ' ' || u.last_name, 'Não atribuído') AS usuario,
                       COALESCE(NULLIF(a.link_doc, ''), 'Sem documento disponível') AS link_doc
                FROM processos_processoandamento a
                JOIN processos_processo p ON a.processo_id = p.id
                LEFT JOIN auth_user u ON a.usuario_id = u.id
                JOIN processos_fase f ON a.fase_id = f.id
                WHERE f.fase = 'Revisão' AND p.concluido = FALSE
                ORDER BY p.id DESC LIMIT 10;
            """,
            "params": [],
            "custom_response": lambda result: (
                "**📌 Processos em Revisão:**\n\n" +
                "\n".join([f"- **Número:** {row[0]}\n- **Responsável:** {row[1]}\n- **Documento:** "
                          f"{'[🔗 Acessar Documento](' + row[2] + ')' if row[2] and 'http' in row[2] else '🔗 Sem documento disponível'}\n"
                          for row in result]) if result else "Nenhum processo em revisão encontrado."
            )
        },
        f"quantos processos {username} tem pendentes": {
            "query": "SELECT COUNT(*) FROM processos_processo WHERE usuario_id = (SELECT id FROM auth_user WHERE username = %s) AND concluido = FALSE;",
            "params": [user.username],
            "custom_response": lambda result: f"Você, {username}, tem {result[0][0]} processos pendentes."
        },
        # Adicione outros itens do dicionário 'queries' aqui...
    }

    for key, value in queries.items():
        if key in question:
            try:
                result = db.run(value["query"], value["params"]) or []
                return JsonResponse({"response": value.get("custom_response", lambda x: "Nenhum registro encontrado.")(result)})
            except Exception as sql_error:
                logger.error(f"Erro ao executar consulta SQL: {sql_error}")
                return JsonResponse({"response": "Erro ao acessar os dados. Tente novamente."})

    # Perguntas gerais para o agente
    prompt = f"""
    Você é um assistente especializado em consultas SQL para um sistema de gabinete jurídico.
    Ajude como assessor de gestão, fornecendo informações sobre produtividade e administração.

    📌 **Base de Dados**: Processos (número, data, status, responsáveis) e Andamentos (fases, documentos, responsáveis).
    📊 **Perguntas Possíveis**: Quantos processos no total? Quais estão em revisão? Produtividade dos assessores?
    ⚠️ **Regras**: Responda em português, claro e objetivo. Se não houver dados, informe educadamente.

    📌 **Pergunta:** {question}
    """

    try:
        response = agent_executor.invoke({"input": prompt})
        resposta_final = response.get("output", "").strip()
        return JsonResponse({"response": resposta_final or "Não encontrei informações relevantes."})
    except Exception as e:
        logger.error(f"Erro na API OpenAI: {e}")
        return JsonResponse({"response": "Erro ao processar. Tente novamente."})
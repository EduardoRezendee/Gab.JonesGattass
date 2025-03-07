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
        # Desembargador
        f"quantos processos estão aguardando meu julgamento {username}": {
            "query": """
                SELECT COUNT(*) 
                FROM processos_processo 
                WHERE usuario_id = (SELECT id FROM auth_user WHERE username = %s) 
                AND concluido = FALSE 
                AND dt_julgamento IS NULL;
            """,
            "params": [user.username],
            "custom_response": lambda result: f"Você, {username}, tem {result[0][0]} processos aguardando julgamento."
        },
        "quais processos têm prazo vencendo hoje": {
            "query": """
                SELECT numero_processo, especie_id 
                FROM processos_processo 
                WHERE dt_prazo = %s AND concluido = FALSE;
            """,
            "params": [now().date()],
            "custom_response": lambda result: (
                "**📅 Processos com Prazo Hoje:**\n\n" +
                "\n".join([f"- {row[0]} ({Especie.objects.get(id=row[1]).sigla})" for row in result]) 
                if result else "Nenhum processo com prazo vencendo hoje."
            )
        },

        # Assessor
        f"quantos processos {username} tem pendentes": {
            "query": """
                SELECT COUNT(*) 
                FROM processos_processo 
                WHERE usuario_id = (SELECT id FROM auth_user WHERE username = %s) 
                AND concluido = FALSE;
            """,
            "params": [user.username],
            "custom_response": lambda result: f"Você, {username}, tem {result[0][0]} processos pendentes."
        },
        f"quantos processos {username} concluiu esta semana": {
            "query": """
                SELECT COUNT(*) 
                FROM processos_processo 
                WHERE usuario_id = (SELECT id FROM auth_user WHERE username = %s) 
                AND concluido = TRUE 
                AND dt_conclusao >= %s;
            """,
            "params": [user.username, now() - timedelta(days=7)],
            "custom_response": lambda result: f"Você, {username}, concluiu {result[0][0]} processos esta semana."
        },

        # Revisor
        f"quantos processos estão em revisão comigo {username}": {
            "query": """
                SELECT COUNT(*) 
                FROM processos_processoandamento 
                WHERE usuario_id = (SELECT id FROM auth_user WHERE username = %s) 
                AND fase_id = (SELECT id FROM processos_fase WHERE fase = 'Revisão') 
                AND dt_conclusao IS NULL;
            """,
            "params": [user.username],
            "custom_response": lambda result: f"Você, {username}, tem {result[0][0]} processos em revisão."
        },
        "quais processos em revisão estão próximos do prazo": {
            "query": """
                SELECT p.numero_processo, p.dt_prazo 
                FROM processos_processoandamento a 
                JOIN processos_processo p ON a.processo_id = p.id 
                WHERE a.fase_id = (SELECT id FROM processos_fase WHERE fase = 'Revisão') 
                AND p.dt_prazo <= %s 
                AND a.dt_conclusao IS NULL;
            """,
            "params": [now().date() + timedelta(days=3)],
            "custom_response": lambda result: (
                "**📅 Processos em Revisão Próximos do Prazo:**\n\n" +
                "\n".join([f"- {row[0]} (Prazo: {row[1]})" for row in result]) 
                if result else "Nenhum processo em revisão próximo do prazo."
            )
        },

        # Chefe de Gabinete
        "qual é a produtividade dos assessores este mês": {
            "query": """
                SELECT COALESCE(u.first_name || ' ' || u.last_name, u.username), 
                       COUNT(p.id) FILTER (WHERE p.concluido = TRUE) as concluidos 
                FROM auth_user u 
                LEFT JOIN processos_processo p ON p.usuario_id = u.id 
                WHERE p.dt_conclusao >= %s 
                GROUP BY u.id, u.username, u.first_name, u.last_name 
                HAVING COUNT(p.id) FILTER (WHERE p.concluido = TRUE) > 0;
            """,
            "params": [now().replace(day=1)],
            "custom_response": lambda result: (
                "**📊 Produtividade dos Assessores Este Mês:**\n\n" +
                "\n".join([f"- {row[0]}: {row[1]} processos concluídos" for row in result])
            )
        },
        "quantos processos estão parados em cada fase": {
            "query": """
                SELECT f.fase, COUNT(p.id) 
                FROM processos_processoandamento a 
                JOIN processos_fase f ON a.fase_id = f.id 
                JOIN processos_processo p ON a.processo_id = p.id 
                WHERE a.dt_conclusao IS NULL 
                GROUP BY f.fase;
            """,
            "params": [],
            "custom_response": lambda result: (
                "**📌 Processos Parados por Fase:**\n\n" +
                "\n".join([f"- {row[0]}: {row[1]} processos" for row in result]) 
                if result else "Nenhum processo parado."
            )
        },
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
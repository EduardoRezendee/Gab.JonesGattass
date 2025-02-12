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

# Configuração da API OpenAI
os.environ["OPENAI_API_KEY"] = config("OPENAI_API_KEY")

# Configurar logs para depuração
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conectar ao banco de dados PostgreSQL
try:
    escaped_password = quote_plus(config("DB_PASSWORD"))
    db_uri = f"postgresql+psycopg2://{config('DB_USER')}:{escaped_password}@{config('DB_HOST')}:{config('DB_PORT')}/{config('DB_NAME')}"
    
    print(f"Tentando conectar ao banco: {db_uri}")  # DEBUG

    db = SQLDatabase.from_uri(db_uri)
    logger.info("✅ Conexão ao banco de dados PostgreSQL bem-sucedida!")
except Exception as e:
    logger.error(f"❌ Erro ao conectar ao banco de dados PostgreSQL: {e}")
    db = None  # Garante que a variável 'db' existe mesmo que a conexão falhe

if db:
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0)

    agent_executor = create_sql_agent(
        llm=llm,
        db=db,
        verbose=True,
    )
else:
    logger.error("A variável 'db' está vazia. O agente SQL não será inicializado.")
    agent_executor = None  

SAUDACOES = ["olá", "oi", "bom dia", "boa tarde", "boa noite", "e aí"]

def chatbot(request):
    """ Renderiza a interface do Chatbot """
    return render(request, 'chat.html')

@login_required
def ask_chatbot(request):
    """ Processa perguntas enviadas pelo usuário e retorna respostas formatadas """
    if request.method != "GET":
        return JsonResponse({"error": "Método não permitido."}, status=405)

    if not agent_executor:
        return JsonResponse({"response": "O chatbot está temporariamente indisponível devido a problemas de conexão com o banco de dados."})

    question = request.GET.get("question", "").strip().lower()
    
    if not question:
        return JsonResponse({"response": "Por favor, faça uma pergunta válida."})

    user = request.user
    username = f"{user.first_name} {user.last_name}".strip() or user.username 

    question = question.replace("eu", username)

    if question in SAUDACOES:
        return JsonResponse({"response": f"Olá, {username}! Como posso ajudar você hoje?"})

    try:
        queries = {
            f"quantos processos {username} tem": {
                "query": """
                    SELECT COUNT(*) 
                    FROM processos_processo 
                    WHERE usuario_id = (SELECT id FROM auth_user WHERE username = %s);
                """,
                "params": [user.username],  
                "custom_response": lambda result: f"Você, {username}, tem {result[0][0]} processos."
            },
            "quantos processos entraram hoje": {
                "query": """
                    SELECT COUNT(*) 
                    FROM processos_processo 
                    WHERE DATE(dt_criacao) = DATE(%s);
                """,
                "params": [now().date()],  
                "custom_response": lambda result: f"Hoje entraram {result[0][0]} processos."
            },
            "processos em revisão": {
                "query": """
                    SELECT 
                        p.numero_processo, 
                        COALESCE(u.first_name || ' ' || u.last_name, 'Não atribuído') AS usuario, 
                        COALESCE(NULLIF(a.link_doc, ''), 'Sem documento disponível') AS link_doc
                    FROM processos_processoandamento a  
                    JOIN processos_processo p ON a.processo_id = p.id  
                    LEFT JOIN auth_user u ON a.usuario_id = u.id  
                    JOIN processos_fase f ON a.fase_id = f.id  
                    WHERE 
                        f.fase = 'Revisão'  
                        AND p.concluido = FALSE  
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
            },
            "quantos processos a ": {
                "query": """
                    SELECT 
                        COUNT(*) FILTER (WHERE concluido = FALSE) AS pendentes, 
                        COUNT(*) FILTER (WHERE concluido = TRUE) AS concluidos
                    FROM processos_processo 
                    WHERE usuario_id IN (
                        SELECT id FROM auth_user WHERE first_name ILIKE %s
                    );
                """,
                "params": [f"{question.split('quantos processos a ')[1].split()[0]}%"],  
                "custom_response": lambda result: f"A {question.split('quantos processos a ')[1].split()[0]} tem {result[0][0]} processos pendentes e {result[0][1]} concluídos."
            },
            "quais processos estão no meu dia": {
                "query": """
                    SELECT 
                        p.numero_processo, 
                        p.data_dist,
                        COALESCE(NULLIF(p.dt_prazo::TEXT, ''), 'Sem prazo definido') AS prazo
                    FROM processos_processo p
                    JOIN tarefasdodia_tarefadiaria t ON t.processo_id = p.id
                    WHERE t.usuario_id = %s;
                """,
                "params": [user.id],
                "custom_response": lambda result: (
                    "**📌 Processos no seu dia:**\n\n" +
                    "\n".join([
                        f"- **Número:** {row[0]}\n"
                        f"- **Data Distribuição:** {row[1]}\n"
                        f"- **Prazo:** {row[2]}\n"
                        for row in result
                    ])
                    if result else "Nenhum processo no seu dia encontrado."
                )
            }
        }

        for key, value in queries.items():
            if key in question:
                try:
                    result = db.run(value["query"], value["params"]) or []

                    if "custom_response" in value and result:
                        response = value["custom_response"](result)
                        return JsonResponse({"response": response})

                    return JsonResponse({"response": "Nenhum registro encontrado."})

                except Exception as sql_error:
                    logger.error(f"Erro ao executar consulta SQL: {sql_error}")
                    return JsonResponse({"response": "Erro ao acessar os dados do banco. Verifique a conexão e tente novamente."})

    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        return JsonResponse({"error": "Ocorreu um erro ao processar sua pergunta. Tente novamente mais tarde."})

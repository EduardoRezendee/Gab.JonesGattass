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
                    FROM processos_processoandamento a  -- Agora a busca começa em ProcessoAndamento
                    JOIN processos_processo p ON a.processo_id = p.id  -- Relaciona cada andamento a um processo
                    LEFT JOIN auth_user u ON a.usuario_id = u.id  -- Responsável pelo andamento (se houver)
                    JOIN processos_fase f ON a.fase_id = f.id  -- Relaciona com a tabela de fases
                    WHERE 
                        f.fase = 'Revisão'  -- Filtra processos que estão na fase de revisão
                        AND p.concluido = FALSE  -- Garante que o processo ainda não foi concluído
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

        prompt = f"""
        Você é um assistente especializado em consultas SQL para um sistema de **gabinete de desembargador jurídico**.  
        Seu papel é atuar como um **assessor de gestão**, fornecendo informações detalhadas sobre a produtividade dos assessores e auxiliando na administração do gabinete.

        📌 **Base de Dados**:
        O banco de dados contém **duas tabelas principais**:
        1️⃣ **Processos** → Contém informações sobre os processos judiciais, incluindo número do processo, data de entrada, status atual e responsáveis.  
        2️⃣ **Andamentos** → Registra todas as movimentações dos processos, incluindo as fases *Elaboração, Revisão, Correção e L. PJE*, links de documentos e responsáveis.

        📊 **Tipos de Perguntas que você pode responder**:
        - Quantos processos estão no gabinete total?
        - Quantos processos entraram, saíram ou estão pendentes?
        - Quais processos estão **em elaboração, revisão, correção ou na fase L. PJE**?
        - Comparação da **produtividade dos assessores** com base no número de processos atribuídos/concluídos.
        - Qual é o **tempo médio de tramitação** dos processos?

        ⚠️ **Regras Específicas**:
        ✅ **Se não houver dados no banco para a pergunta**, informe educadamente que **não há registros disponíveis**.  
        ✅ Sempre responda em **português brasileiro**, de forma **clara e objetiva**.  

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

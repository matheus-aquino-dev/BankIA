"""
app.py  —  BankIQ Flask Server
Upload-driven: o Excel só é lido quando o usuário faz upload do arquivo.
"""

from flask import Flask, jsonify, render_template, request
from groq import Groq, AuthenticationError, RateLimitError
from dotenv import load_dotenv
import os, uuid, tempfile

load_dotenv()
from pathlib import Path
from data_processor import load_all, compute_kpis, build_agent_contexts, dataframes_to_json

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB

import mimetypes
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/javascript", ".js")

# Cache em memória — preenchido apenas após upload
_session: dict = {}

ALLOWED_EXT = {".xlsx", ".xlsm", ".xls"}


def allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXT


# ─────────────────────────────────────────────────────────────────────────────
# ROTAS PRINCIPAIS
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def api_upload():
    """Recebe o Excel, processa com pandas e retorna KPIs + dados."""
    if "file" not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado."}), 400

    f = request.files["file"]
    if not f.filename or not allowed(f.filename):
        return jsonify({"error": "Formato inválido. Envie um arquivo .xlsx"}), 400

    # Salva em temp e processa
    # No Windows o handle deve ser fechado antes de qualquer leitura/delete
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp.close()
    f.save(tmp.name)

    try:
        dfs  = load_all(tmp.name)
        kpis = compute_kpis(dfs)
        ctxs = build_agent_contexts(dfs, kpis)
        rows = dataframes_to_json(dfs)

        # Detecta quais abas foram encontradas
        abas_encontradas = list(dfs.keys())

        _session.clear()
        _session.update({
            "filename": f.filename,
            "dfs": dfs, "kpis": kpis, "ctxs": ctxs, "rows": rows,
            "abas": abas_encontradas,
        })

        return jsonify({
            "ok": True,
            "filename": f.filename,
            "abas": abas_encontradas,
            "kpis": kpis,
            "rows": rows,
        })

    except Exception as e:
        return jsonify({"error": f"Erro ao processar arquivo: {str(e)}"}), 500
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


@app.route("/api/agente/<nome>", methods=["POST"])
def api_agente(nome):
    if not _session:
        return jsonify({"error": "Nenhum arquivo carregado."}), 400

    valid = {"credito", "fraude", "invest", "gerente"}
    if nome not in valid:
        return jsonify({"error": "Agente inválido"}), 400

    ctxs = _session["ctxs"]
    kpis = _session["kpis"]

    # ── Configuração por agente: modelo + system prompt especializado ──────────
    AGENTES = {
        "credito": {
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.3,
            "system": (
                "Você é um Analista Sênior de Risco de Crédito com 20 anos de experiência "
                "em bancos brasileiros. Seu raciocínio é quantitativo, preciso e orientado "
                "a Basel III e regulamentação do Banco Central. "
                "Você interpreta indicadores como score médio, taxa de inadimplência, "
                "saldo devedor e modalidades de crédito para emitir diagnósticos executivos. "
                "Nunca especula — só conclui com base nos dados apresentados. "
                "Responda sempre em português do Brasil, de forma direta e estruturada."
            ),
            "user": (
                f"Analise os dados reais da carteira de crédito abaixo e produza um "
                f"DIAGNÓSTICO EXECUTIVO com:\n"
                f"1. Nível de risco geral da carteira (Baixo / Médio / Alto) com justificativa\n"
                f"2. Segmento mais crítico e por quê\n"
                f"3. Duas ações imediatas recomendadas\n\n"
                f"DADOS:\n{ctxs['credito']}"
            ),
        },
        "fraude": {
            "model": "qwen/qwen3-32b",
            "temperature": 0.2,
            "reasoning_effort": "none",
            "system": (
                "Você é um Especialista em Prevenção a Fraudes Financeiras com experiência "
                "em detecção de anomalias, análise comportamental e compliance anti-lavagem. "
                "Você domina padrões de fraude como account takeover, fraude de identidade, "
                "transações internacionais suspeitas e operações fracionadas. "
                "Sua análise é cirúrgica: identifica rapidamente o padrão mais perigoso "
                "e prioriza ações de contenção. "
                "OBRIGATÓRIO: responda SOMENTE em português do Brasil. "
                "Nunca use inglês. Seja direto e estruturado."
            ),
            "user": (
                f"Analise os dados de transações abaixo e produza um ALERTA DE FRAUDE em português do Brasil:\n"
                f"1. Nível de alerta atual (Verde / Amarelo / Vermelho) com justificativa\n"
                f"2. Padrão de fraude mais preocupante detectado\n"
                f"3. Duas ações de contenção imediatas\n\n"
                f"DADOS:\n{ctxs['fraude']}"
            ),
        },
        "invest": {
            "model": "meta-llama/llama-4-scout-17b-16e-instruct",
            "temperature": 0.5,
            "system": (
                "Você é um Assessor de Investimentos e Produtos Bancários especializado "
                "em segmentação de clientes e cross-sell. Você analisa perfil de risco, "
                "renda e comportamento para identificar oportunidades de oferta de produtos "
                "como CDB, LCI, fundos e seguros. "
                "Seu foco é maximizar receita por cliente com adequação ao perfil. "
                "Responda sempre em português do Brasil, de forma direta e estruturada."
            ),
            "user": (
                f"Analise a base de clientes abaixo e produza um RELATÓRIO DE OPORTUNIDADES com:\n"
                f"1. Principal oportunidade de negócio identificada\n"
                f"2. Perfil prioritário para oferta imediata e produto recomendado\n"
                f"3. Duas ações comerciais recomendadas\n\n"
                f"DADOS:\n{ctxs['invest']}"
            ),
        },
    }

    if nome == "gerente":
        body = request.get_json(silent=True) or {}
        res_credito = body.get("credito", f"(não executado — dados: {ctxs['credito']})")
        res_fraude  = body.get("fraude",  f"(não executado — dados: {ctxs['fraude']})")
        res_invest  = body.get("invest",  f"(não executado — dados: {ctxs['invest']})")

        config = {
            "model": "llama-3.3-70b-versatile",
            "temperature": 0.4,
            "system": (
                "Você é o CEO de um banco digital brasileiro. Você recebe relatórios dos seus "
                "agentes especializados (Crédito, Fraude, Investimentos) e sintetiza tudo em "
                "decisões estratégicas claras. Você pensa como um executivo C-level: "
                "prioriza, decide e age. Nunca delega indefinidamente. "
                "Responda sempre em português do Brasil, de forma executiva e objetiva."
            ),
            "user": (
                f"Seus agentes concluíram as análises. Produza um RELATÓRIO EXECUTIVO CONSOLIDADO:\n\n"
                f"1. Situação geral do banco (2-3 linhas)\n"
                f"2. Top 3 prioridades estratégicas imediatas\n"
                f"3. Decisões a tomar agora\n"
                f"4. Perspectiva de 90 dias\n\n"
                f"INDICADORES CONSOLIDADOS:\n"
                f"- Clientes: {kpis['total_clientes']} | Score médio: {kpis['score_medio']}\n"
                f"- Carteira: R$ {kpis['carteira_total']:,.2f} | Inadimplência: {kpis['taxa_inad_pct']}%\n"
                f"- Fraudes: {kpis['n_fraudes']} confirmadas + {kpis['n_revisar']} p/ revisar\n"
                f"- Valor em aberto (inad.): R$ {kpis['valor_inad']:,.2f}\n\n"
                f"RELATÓRIO AGENTE CRÉDITO:\n{res_credito}\n\n"
                f"RELATÓRIO AGENTE FRAUDE:\n{res_fraude}\n\n"
                f"RELATÓRIO AGENTE INVESTIMENTOS:\n{res_invest}"
            ),
        }
    else:
        config = AGENTES[nome]

    try:
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        extra = {}
        if "reasoning_effort" in config:
            extra["reasoning_effort"] = config["reasoning_effort"]
        completion = client.chat.completions.create(
            model=config["model"],
            temperature=config["temperature"],
            max_tokens=1024,
            messages=[
                {"role": "system", "content": config["system"]},
                {"role": "user",   "content": config["user"]},
            ],
            **extra,
        )
        return jsonify({"resultado": completion.choices[0].message.content})
    except AuthenticationError:
        return jsonify({"error": "GROQ_API_KEY inválida ou não configurada."}), 500
    except RateLimitError:
        return jsonify({"error": "Limite de requisições Groq atingido. Aguarde e tente novamente."}), 429
    except Exception as e:
        return jsonify({"error": f"Erro ao chamar a IA: {str(e)}"}), 500


@app.route("/api/reset", methods=["POST"])
def api_reset():
    _session.clear()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    print("=" * 40)
    print("  BankIQ - Upload-Driven Mode")
    print(f"  Acesse: http://localhost:{port}")
    print("=" * 40)
    app.run(host="0.0.0.0", debug=debug, port=port)

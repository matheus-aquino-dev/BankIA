"""
data_processor.py
Leitura e tratamento de dados — recebe o caminho do Excel como argumento.
Toda lógica de negócio e cálculo de KPIs fica aqui.
"""

import pandas as pd
from pathlib import Path

EXPECTED_SHEETS = ["clientes", "transacoes", "emprestimos", "inadimplencia"]


# ─────────────────────────────────────────────────────────────────────────────
# LEITURA BRUTA
# ─────────────────────────────────────────────────────────────────────────────

def load_raw(excel_path: str) -> dict[str, pd.DataFrame]:
    """Lê todas as abas do Excel. Aceita subset das 4 abas esperadas."""
    xl = pd.ExcelFile(excel_path)
    found = [s for s in EXPECTED_SHEETS if s in xl.sheet_names]
    if not found:
        raise ValueError(
            f"Nenhuma aba reconhecida. Esperado: {EXPECTED_SHEETS}. "
            f"Encontrado: {xl.sheet_names}"
        )
    return pd.read_excel(excel_path, sheet_name=found, dtype=str)


# ─────────────────────────────────────────────────────────────────────────────
# TRATAMENTO / TIPAGEM
# ─────────────────────────────────────────────────────────────────────────────

def process_clientes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["score_credito"] = pd.to_numeric(df["score_credito"], errors="coerce")
    df["renda_mensal"]  = pd.to_numeric(df["renda_mensal"],  errors="coerce")
    df["data_cadastro"] = pd.to_datetime(df["data_cadastro"], errors="coerce")
    df["perfil"]  = df["perfil"].str.strip()
    df["status"]  = df["status"].str.strip()
    df["estado"]  = df["estado"].str.strip().str.upper()
    return df


def process_transacoes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["valor"]      = pd.to_numeric(df["valor"], errors="coerce")
    df["data_hora"]  = pd.to_datetime(df["data_hora"], errors="coerce")
    df["flag"]       = df["flag"].str.strip()
    df["tipo"]       = df["tipo"].str.strip()
    df["pais"]       = df["pais"].str.strip().str.upper()
    df["is_fraude"]  = df["flag"] == "Fraude"
    df["is_revisar"] = df["flag"] == "Revisar"
    df["is_inter"]   = df["pais"] != "BR"
    return df


def process_emprestimos(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ["valor_principal", "taxa_mensal", "saldo_devedor"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["parcelas_total", "parcelas_pagas"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    df["data_concessao"] = pd.to_datetime(df["data_concessao"], errors="coerce")
    df["status"]     = df["status"].str.strip()
    df["modalidade"] = df["modalidade"].str.strip()
    df["parcelas_restantes"] = df["parcelas_total"] - df["parcelas_pagas"]
    df["pct_pago"] = (df["parcelas_pagas"] / df["parcelas_total"] * 100).round(1)
    return df


def process_inadimplencia(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["valor_em_aberto"]    = pd.to_numeric(df["valor_em_aberto"],    errors="coerce")
    df["dias_atraso"]        = pd.to_numeric(df["dias_atraso"],        errors="coerce")
    df["parcelas_em_atraso"] = pd.to_numeric(df["parcelas_em_atraso"], errors="coerce").astype("Int64")
    df["ultima_negociacao"]  = pd.to_datetime(df["ultima_negociacao"], errors="coerce")
    df["risco"] = df["risco"].str.strip()
    return df


PROCESSORS = {
    "clientes":      process_clientes,
    "transacoes":    process_transacoes,
    "emprestimos":   process_emprestimos,
    "inadimplencia": process_inadimplencia,
}


def load_all(excel_path: str) -> dict[str, pd.DataFrame]:
    """Ponto de entrada: lê e trata todos os DataFrames encontrados no Excel."""
    raw = load_raw(excel_path)
    return {name: PROCESSORS[name](df) for name, df in raw.items()}


# ─────────────────────────────────────────────────────────────────────────────
# KPIs
# ─────────────────────────────────────────────────────────────────────────────

def compute_kpis(dfs: dict[str, pd.DataFrame]) -> dict:
    cli  = dfs.get("clientes",      pd.DataFrame())
    tra  = dfs.get("transacoes",    pd.DataFrame())
    emp  = dfs.get("emprestimos",   pd.DataFrame())
    inad = dfs.get("inadimplencia", pd.DataFrame())

    def safe_mean(s):  return float(round(s.mean(), 1)) if not s.empty else 0
    def safe_sum(s):   return float(round(s.sum(),  2)) if not s.empty else 0
    def safe_len(df):  return int(len(df))

    total_clientes  = safe_len(cli)
    score_medio     = safe_mean(cli["score_credito"]) if "score_credito" in cli else 0
    renda_media     = float(round(cli["renda_mensal"].mean(), 2)) if "renda_mensal" in cli else 0
    por_perfil      = cli["perfil"].value_counts().to_dict()  if "perfil"  in cli else {}
    por_status_cli  = cli["status"].value_counts().to_dict()  if "status"  in cli else {}

    total_trans     = safe_len(tra)
    volume_total    = safe_sum(tra["valor"]) if "valor" in tra else 0
    ticket_medio    = float(round(tra["valor"].mean(), 2)) if "valor" in tra and not tra.empty else 0
    n_fraudes       = int(tra["is_fraude"].sum())  if "is_fraude"  in tra else 0
    n_revisar       = int(tra["is_revisar"].sum()) if "is_revisar" in tra else 0
    n_inter         = int(tra["is_inter"].sum())   if "is_inter"   in tra else 0
    por_flag        = tra["flag"].value_counts().to_dict() if "flag" in tra else {}
    por_tipo_trans  = tra["tipo"].value_counts().to_dict() if "tipo" in tra else {}

    total_contratos = safe_len(emp)
    carteira_total  = safe_sum(emp["saldo_devedor"])    if "saldo_devedor"    in emp else 0
    principal_total = safe_sum(emp["valor_principal"])  if "valor_principal"  in emp else 0
    taxa_media      = float(round(emp["taxa_mensal"].mean(), 2)) if "taxa_mensal" in emp and not emp.empty else 0
    por_status_emp  = emp["status"].value_counts().to_dict()     if "status"     in emp else {}
    por_modalidade  = []
    if "modalidade" in emp and not emp.empty:
        por_modalidade = emp.groupby("modalidade").agg(
            qtd=("id", "count"),
            saldo=("saldo_devedor", "sum"),
            taxa_media=("taxa_mensal", "mean"),
        ).round(2).reset_index().to_dict(orient="records")

    total_inad      = safe_len(inad)
    valor_inad      = safe_sum(inad["valor_em_aberto"]) if "valor_em_aberto" in inad else 0
    media_dias      = float(round(inad["dias_atraso"].mean(), 1)) if "dias_atraso" in inad and not inad.empty else 0
    por_risco       = inad["risco"].value_counts().to_dict() if "risco" in inad else {}
    taxa_inad_pct   = round(total_inad / total_contratos * 100, 2) if total_contratos else 0

    return {
        "total_clientes": total_clientes, "score_medio": score_medio,
        "renda_media": renda_media, "por_perfil": por_perfil, "por_status_cli": por_status_cli,
        "total_trans": total_trans, "volume_total": volume_total, "ticket_medio": ticket_medio,
        "n_fraudes": n_fraudes, "n_revisar": n_revisar, "n_inter": n_inter,
        "por_flag": por_flag, "por_tipo_trans": por_tipo_trans,
        "total_contratos": total_contratos, "carteira_total": carteira_total,
        "principal_total": principal_total, "taxa_media": taxa_media,
        "por_status_emp": por_status_emp, "por_modalidade": por_modalidade,
        "total_inad": total_inad, "valor_inad": valor_inad,
        "media_dias": media_dias, "por_risco": por_risco, "taxa_inad_pct": taxa_inad_pct,
    }


def build_agent_contexts(dfs: dict, kpis: dict) -> dict[str, str]:
    emp  = dfs.get("emprestimos",   pd.DataFrame())
    inad = dfs.get("inadimplencia", pd.DataFrame())
    tra  = dfs.get("transacoes",    pd.DataFrame())
    cli  = dfs.get("clientes",      pd.DataFrame())

    inad_pf = 0
    maior_dev_str = "N/D"
    if not emp.empty and not inad.empty:
        inad_pf = len(emp[(emp["status"] == "Inadimplente") & (emp["modalidade"] == "PF")])
        row = inad.loc[inad["valor_em_aberto"].idxmax()]
        maior_dev_str = f"{row['cliente_id']} com R$ {row['valor_em_aberto']:,.2f} ({row['dias_atraso']} dias)"

    ctx_credito = (
        f"Dados extraídos do Excel (emprestimos + inadimplencia):\n"
        f"- {kpis['total_contratos']} contratos | Carteira: R$ {kpis['carteira_total']:,.2f}\n"
        f"- Score médio: {kpis['score_medio']} pts (meta: 700+)\n"
        f"- Inadimplência: {kpis['taxa_inad_pct']}% | {kpis['total_inad']} casos ativos\n"
        f"- Alto risco: {kpis['por_risco'].get('Alto', 0)} casos | PF inadimplente: {inad_pf}\n"
        f"- Maior devedor: {maior_dev_str}\n"
        f"- Modalidades: { {r['modalidade']: r['qtd'] for r in kpis['por_modalidade']} }"
    )

    max_sus = 0
    if not tra.empty and "valor" in tra and "flag" in tra:
        susp = tra[tra["flag"] != "Normal"]["valor"]
        max_sus = susp.max() if not susp.empty else 0

    ctx_fraude = (
        f"Dados extraídos do Excel (transacoes):\n"
        f"- {kpis['total_trans']} transações | Volume: R$ {kpis['volume_total']:,.2f}\n"
        f"- Fraudes confirmadas: {kpis['n_fraudes']} | Para revisar: {kpis['n_revisar']}\n"
        f"- Transações internacionais: {kpis['n_inter']}\n"
        f"- Maior valor suspeito: R$ {max_sus:,.2f}\n"
        f"- Por tipo: {kpis['por_tipo_trans']}\n"
        f"- Flags: {kpis['por_flag']}"
    )

    score_arr = renda_arr = 0
    if not cli.empty and "perfil" in cli:
        arr = cli[cli["perfil"] == "Arrojado"]
        if not arr.empty:
            score_arr = round(arr["score_credito"].mean(), 0)
            renda_arr = round(arr["renda_mensal"].mean(), 2)

    ctx_invest = (
        f"Dados extraídos do Excel (clientes):\n"
        f"- {kpis['total_clientes']} clientes | Renda média: R$ {kpis['renda_media']:,.2f}/mês\n"
        f"- Conservador: {kpis['por_perfil'].get('Conservador', 0)}\n"
        f"- Moderado: {kpis['por_perfil'].get('Moderado', 0)}\n"
        f"- Arrojado: {kpis['por_perfil'].get('Arrojado', 0)} (score: {score_arr}, renda: R$ {renda_arr:,.2f})\n"
        f"- Status: {kpis['por_status_cli']}"
    )

    return {"credito": ctx_credito, "fraude": ctx_fraude, "invest": ctx_invest}


def dataframes_to_json(dfs: dict) -> dict:
    result = {}
    for name, df in dfs.items():
        tmp = df.copy()
        for col in tmp.select_dtypes(include=["datetime64[ns]", "datetimetz"]):
            tmp[col] = tmp[col].dt.strftime("%Y-%m-%d")
        bool_cols = [c for c in tmp.columns if c.startswith("is_")]
        tmp = tmp.drop(columns=bool_cols, errors="ignore")
        for col in tmp.select_dtypes(include=["Int64"]):
            tmp[col] = tmp[col].astype(object).where(tmp[col].notna(), None)
        result[name] = tmp.to_dict(orient="records")
    return result

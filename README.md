# BankIQ — Sistema Bancário Inteligente

Arquitetura multiagente para BI bancário.  
**Dados** no Excel · **Tratamento** em Python · **Dashboard** no navegador via Flask.

## Estrutura do Projeto

```
bankiq/
├── data/
│   └── bankiq_dados.xlsx      ← Base de dados (4 abas)
├── static/
│   ├── css/style.css
│   └── js/app.js
├── templates/
│   └── index.html
├── data_processor.py          ← Leitura e tratamento dos dados (pandas)
├── app.py                     ← Servidor Flask + rotas da API
├── requirements.txt
└── README.md
```

## Instalação

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar chave da API Anthropic (para os Agentes IA)
export ANTHROPIC_API_KEY="sk-ant-..."   # Linux/Mac
set ANTHROPIC_API_KEY=sk-ant-...        # Windows

# 3. Iniciar o servidor
python app.py
```

Acesse: **http://localhost:5000**

## Fluxo de Dados

```
bankiq_dados.xlsx
      ↓
data_processor.py   (pandas: leitura, tipagem, limpeza, KPIs)
      ↓
app.py / Flask      (API JSON em /api/kpis e /api/tabelas)
      ↓
static/js/app.js    (consome a API e renderiza o dashboard)
```

## API Endpoints

| Método | Rota                    | Descrição                              |
|--------|-------------------------|----------------------------------------|
| GET    | `/`                     | Dashboard principal                    |
| GET    | `/api/kpis`             | KPIs calculados pelo Python            |
| GET    | `/api/tabelas`          | Dados das 4 abas do Excel              |
| POST   | `/api/agente/credito`   | Análise de crédito via IA              |
| POST   | `/api/agente/fraude`    | Análise de fraudes via IA              |
| POST   | `/api/agente/invest`    | Análise de investimentos via IA        |
| POST   | `/api/agente/gerente`   | Relatório executivo consolidado        |
| POST   | `/api/reload`           | Recarrega os dados do Excel            |

## Abas do Excel (apenas dados brutos)

| Aba            | Colunas principais                                          |
|----------------|-------------------------------------------------------------|
| clientes       | id, nome, perfil, score_credito, renda_mensal, status       |
| transacoes     | id, cliente_id, valor, tipo, flag, pais                     |
| emprestimos    | id, cliente_id, valor_principal, taxa_mensal, status        |
| inadimplencia  | cliente_id, valor_em_aberto, dias_atraso, risco             |

> Para atualizar os dados, edite o Excel e clique em **↺ Recarregar Excel** no dashboard.

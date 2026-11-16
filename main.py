from datetime import date, datetime, timedelta
from enum import Enum
import sqlite3
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="Cozinha Comunitária Esperança — Sistema PEPS/FIFO",
    description="Gestão de perecíveis e combate ao desperdício alinhada ao ODS 2.",
    version="1.0.0",
)

DB_PATH = "cozinha_esperanca.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alimento TEXT NOT NULL,
            peso_kg REAL NOT NULL,
            codigo_lote TEXT NOT NULL,
            data_validade TEXT NOT NULL,
            criado_em TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS movimentacoes_estoque (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lote_id INTEGER NOT NULL,
            alimento TEXT NOT NULL,
            peso_kg REAL NOT NULL,
            motivo_saida TEXT NOT NULL,
            data_movimentacao TEXT NOT NULL
        )
        """
    )

    # Popula dados iniciais caso o banco esteja vazio (ideal para demonstração e deploy)
    cur.execute("SELECT COUNT(*) FROM lotes")
    if cur.fetchone()[0] == 0:
        hoje = date.today()
        lotes_iniciais = [
            ("Tomate Italiano Fresco", 12.5, "LOT-2026-01", hoje.isoformat()),
            ("Peito de Frango Resfriado", 18.0, "LOT-2026-02", (hoje + timedelta(days=1)).isoformat()),
            ("Leite Integral UHT (Caixa)", 24.0, "LOT-2026-03", (hoje + timedelta(days=2)).isoformat()),
            ("Cenoura Selecionada", 15.0, "LOT-2026-04", (hoje + timedelta(days=6)).isoformat()),
            ("Arroz Branco Tipo 1", 50.0, "LOT-2026-05", (hoje + timedelta(days=25)).isoformat()),
        ]
        agora = datetime.now().isoformat()
        for alimento, peso, codigo, validade in lotes_iniciais:
            cur.execute(
                "INSERT INTO lotes (alimento, peso_kg, codigo_lote, data_validade, criado_em) VALUES (?, ?, ?, ?, ?)",
                (alimento, peso, codigo, validade, agora),
            )

    cur.execute("SELECT COUNT(*) FROM movimentacoes_estoque")
    if cur.fetchone()[0] == 0:
        agora = datetime.now().isoformat()
        cur.execute(
            "INSERT INTO movimentacoes_estoque (lote_id, alimento, peso_kg, motivo_saida, data_movimentacao) VALUES (?, ?, ?, ?, ?)",
            (0, "Hortaliças Mistas (Histórico)", 42.5, "CONSUMO_DIARIO", agora),
        )

    conn.commit()
    conn.close()


@app.on_event("startup")
def startup_event():
    init_db()


class MotivoSaida(str, Enum):
    CONSUMO_DIARIO = "CONSUMO_DIARIO"
    DESCARTE = "DESCARTE"


class LoteCreate(BaseModel):
    alimento: str = Field(..., min_length=2, max_length=100)
    peso_kg: float = Field(..., gt=0, description="Peso deve ser maior que zero")
    codigo_lote: str = Field(..., min_length=2, max_length=40)
    data_validade: date


class BaixaRequest(BaseModel):
    peso_baixa: float = Field(..., gt=0)
    motivo_saida: MotivoSaida


def calcular_urgencia(data_validade_str: str):
    validade = date.fromisoformat(data_validade_str)
    dias_restantes = (validade - date.today()).days
    if dias_restantes <= 0:
        return dias_restantes, "CRITICO", "VENCE HOJE / VENCIDO"
    elif dias_restantes <= 2:
        return dias_restantes, "ATENCAO", f"VENCE EM {dias_restantes} DIA(S)"
    return dias_restantes, "NORMAL", f"VENCE EM {dias_restantes} DIAS"


@app.get("/health")
def health_check():
    return {"status": "online", "service": "cozinha-comunitaria-esperanca", "timestamp": datetime.now().isoformat()}


@app.get("/api/v1/lotes")
def listar_lotes():
    conn = get_db()
    rows = conn.execute(
        "SELECT id, alimento, peso_kg, codigo_lote, data_validade FROM lotes WHERE peso_kg > 0 ORDER BY data_validade ASC"
    ).fetchall()
    conn.close()

    resultado = []
    for r in rows:
        dias, nivel, rotulo = calcular_urgencia(r["data_validade"])
        resultado.append(
            {
                "id": r["id"],
                "alimento": r["alimento"],
                "peso_kg": round(r["peso_kg"], 2),
                "codigo_lote": r["codigo_lote"],
                "data_validade": r["data_validade"],
                "dias_restantes": dias,
                "nivel_urgencia": nivel,
                "rotulo_urgencia": rotulo,
            }
        )
    return resultado


@app.post("/api/v1/lotes", status_code=201)
def criar_lote(payload: LoteCreate):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO lotes (alimento, peso_kg, codigo_lote, data_validade, criado_em) VALUES (?, ?, ?, ?, ?)",
        (
            payload.alimento.strip(),
            round(payload.peso_kg, 2),
            payload.codigo_lote.strip().upper(),
            payload.data_validade.isoformat(),
            datetime.now().isoformat(),
        ),
    )
    novo_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"id": novo_id, "mensagem": "Doação registrada com sucesso no fluxo PEPS/FIFO."}


@app.patch("/api/v1/lotes/{lote_id}/baixa")
def registrar_baixa(lote_id: int, payload: BaixaRequest):
    conn = get_db()
    cur = conn.cursor()
    lote = cur.execute("SELECT * FROM lotes WHERE id = ?", (lote_id,)).fetchone()
    if not lote:
        conn.close()
        raise HTTPException(status_code=404, detail="Lote não encontrado.")

    if payload.peso_baixa > lote["peso_kg"]:
        conn.close()
        raise HTTPException(status_code=422, detail="Peso de baixa superior ao saldo disponível no lote.")

    novo_saldo = round(lote["peso_kg"] - payload.peso_baixa, 2)
    cur.execute("UPDATE lotes SET peso_kg = ? WHERE id = ?", (novo_saldo, lote_id))
    cur.execute(
        "INSERT INTO movimentacoes_estoque (lote_id, alimento, peso_kg, motivo_saida, data_movimentacao) VALUES (?, ?, ?, ?, ?)",
        (lote_id, lote["alimento"], round(payload.peso_baixa, 2), payload.motivo_saida.value, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    return {"mensagem": "Baixa registrada com sucesso.", "saldo_restante": novo_saldo}


@app.get("/api/v1/indicadores-ods")
def obter_indicadores():
    conn = get_db()
    total_estoque = conn.execute("SELECT COALESCE(SUM(peso_kg), 0) FROM lotes WHERE peso_kg > 0").fetchone()[0]
    quilos_salvos = conn.execute(
        "SELECT COALESCE(SUM(peso_kg), 0) FROM movimentacoes_estoque WHERE motivo_saida = 'CONSUMO_DIARIO'"
    ).fetchone()[0]
    quilos_descartados = conn.execute(
        "SELECT COALESCE(SUM(peso_kg), 0) FROM movimentacoes_estoque WHERE motivo_saida = 'DESCARTE'"
    ).fetchone()[0]
    conn.close()

    refeicoes_estimadas = int(quilos_salvos / 0.5)
    return {
        "estoque_ativo_kg": round(total_estoque, 2),
        "quilos_salvos_kg": round(quilos_salvos, 2),
        "quilos_descartados_kg": round(quilos_descartados, 2),
        "refeicoes_estimadas": refeicoes_estimadas,
    }


HTML_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Cozinha Comunitária Esperança — Painel PEPS/FIFO</title>
  <style>
    :root {
      --bg: #f4f7f6;
      --surface: #ffffff;
      --text: #1b262c;
      --muted: #4f5d66;
      --primary: #1b5e20;
      --primary-text: #ffffff;
      --border: #cfd8dc;
      --critico-bg: #ffebee;
      --critico-border: #c62828;
      --critico-text: #b71c1c;
      --atencao-bg: #fff8e1;
      --atencao-border: #ef6c00;
      --atencao-text: #e65100;
      --normal-bg: #e8f5e9;
      --normal-border: #2e7d32;
      --normal-text: #1b5e20;
    }

    [data-theme="high-contrast"] {
      --bg: #000000;
      --surface: #0a0a0a;
      --text: #ffffff;
      --muted: #ffff00;
      --primary: #ffff00;
      --primary-text: #000000;
      --border: #ffffff;
      --critico-bg: #2b0000;
      --critico-border: #ff5252;
      --critico-text: #ff8a80;
      --atencao-bg: #2b1d00;
      --atencao-border: #ffd740;
      --atencao-text: #ffe57f;
      --normal-bg: #002607;
      --normal-border: #69f0ae;
      --normal-text: #b9f6ca;
    }

    html { font-size: 16px; }
    body {
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding-bottom: 110px;
    }

    header {
      background: var(--surface);
      border-bottom: 2px solid var(--border);
      padding: 1rem 1.25rem;
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 10;
    }

    .brand h1 { margin: 0; font-size: 1.25rem; }
    .brand p { margin: 0.2rem 0 0; font-size: 0.875rem; color: var(--muted); }

    .actions { display: flex; flex-wrap: wrap; gap: 0.5rem; }

    button {
      min-height: 48px;
      padding: 0.65rem 1rem;
      font-size: 1rem;
      font-weight: 700;
      border-radius: 8px;
      cursor: pointer;
      border: 2px solid var(--border);
      background: var(--surface);
      color: var(--text);
    }

    button.primary {
      background: var(--primary);
      color: var(--primary-text);
      border-color: var(--primary);
    }

    main { max-width: 960px; margin: 1.25rem auto; padding: 0 1rem; }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
      gap: 1rem;
    }

    .card {
      background: var(--surface);
      border: 2px solid var(--border);
      border-left-width: 8px;
      border-radius: 10px;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      gap: 0.75rem;
    }

    .card.CRITICO { border-left-color: var(--critico-border); background: var(--critico-bg); }
    .card.ATENCAO { border-left-color: var(--atencao-border); background: var(--atencao-bg); }
    .card.NORMAL  { border-left-color: var(--normal-border);  background: var(--normal-bg); }

    .badge {
      display: inline-block;
      padding: 0.25rem 0.6rem;
      border-radius: 6px;
      font-size: 0.82rem;
      font-weight: 800;
      border: 1px solid currentColor;
    }

    .CRITICO .badge { color: var(--critico-text); }
    .ATENCAO .badge { color: var(--atencao-text); }
    .NORMAL .badge  { color: var(--normal-text); }

    .card h2 { margin: 0.4rem 0 0.2rem; font-size: 1.2rem; }
    .meta { font-size: 0.95rem; margin: 0.15rem 0; }

    footer {
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: var(--surface);
      border-top: 2px solid var(--border);
      padding: 0.75rem 1rem;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-around;
      gap: 0.75rem;
      font-weight: 700;
    }

    dialog {
      border: 2px solid var(--border);
      border-radius: 12px;
      background: var(--surface);
      color: var(--text);
      max-width: 440px;
      width: 92%;
      padding: 1.25rem;
    }

    .field { display: flex; flex-direction: column; gap: 0.35rem; margin-bottom: 0.9rem; }
    input, select {
      min-height: 46px;
      padding: 0.5rem 0.75rem;
      font-size: 1rem;
      border-radius: 6px;
      border: 2px solid var(--border);
      background: var(--surface);
      color: var(--text);
    }

    .modal-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1rem; }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <h1>🍲 Cozinha Comunitária Esperança</h1>
      <p>Painel Inteligente PEPS/FIFO • Prioridade por Validade (ODS 2)</p>
    </div>
    <div class="actions" role="toolbar" aria-label="Controles de acessibilidade e cadastro">
      <button type="button" onclick="alternarContraste()" aria-label="Alternar modo de alto contraste">🌓 Alto Contraste</button>
      <button type="button" onclick="aumentarFonte()" aria-label="Aumentar tamanho da fonte">A+ Fonte</button>
      <button type="button" class="primary" onclick="document.getElementById('modalCadastro').showModal()">+ Cadastrar Doação</button>
    </div>
  </header>

  <main>
    <section id="listaLotes" class="grid" aria-live="polite"></section>
  </main>

  <footer>
    <span>📦 Estoque Ativo: <strong id="indEstoque">0 kg</strong></span>
    <span>♻️ Alimentos Salvos (ODS 2): <strong id="indSalvos">0 kg</strong></span>
    <span>🍽️ Refeições Estimadas: <strong id="indRefeicoes">0</strong></span>
  </footer>

  <!-- Modal Cadastro -->
  <dialog id="modalCadastro">
    <form method="dialog" onsubmit="salvarLote(event)">
      <h2>Registrar Nova Doação (PEPS)</h2>
      <div class="field">
        <label for="alimento">Alimento / Insumo</label>
        <input id="alimento" required placeholder="Ex: Tomate Italiano" />
      </div>
      <div class="field">
        <label for="peso">Peso (kg)</label>
        <input id="peso" type="number" step="0.1" min="0.1" required placeholder="Ex: 10.5" />
      </div>
      <div class="field">
        <label for="codigo">Identificação do Lote</label>
        <input id="codigo" required placeholder="Ex: LOT-2026-09" />
      </div>
      <div class="field">
        <label for="validade">Data de Validade</label>
        <input id="validade" type="date" required />
      </div>
      <div class="modal-actions">
        <button type="button" onclick="document.getElementById('modalCadastro').close()">Cancelar</button>
        <button type="submit" class="primary">Salvar no Estoque</button>
      </div>
    </form>
  </dialog>

  <!-- Modal Baixa Rastreável -->
  <dialog id="modalBaixa">
    <form method="dialog" onsubmit="confirmarBaixa(event)">
      <h2>Dar Baixa no Lote</h2>
      <p id="baixaDescricao"></p>
      <input type="hidden" id="baixaLoteId" />
      <div class="field">
        <label for="pesoBaixa">Quantidade utilizada/retirada (kg)</label>
        <input id="pesoBaixa" type="number" step="0.1" min="0.1" required />
      </div>
      <div class="field">
        <label for="motivoSaida">Destinação do Alimento (Rastreabilidade ODS 2)</label>
        <select id="motivoSaida" required>
          <option value="CONSUMO_DIARIO">🍲 Consumo Diário (Preparo de Refeições)</option>
          <option value="DESCARTE">⚠️ Descarte por Desperdício / Impróprio</option>
        </select>
      </div>
      <div class="modal-actions">
        <button type="button" onclick="document.getElementById('modalBaixa').close()">Cancelar</button>
        <button type="submit" class="primary">Confirmar Baixa</button>
      </div>
    </form>
  </dialog>

  <script>
    let escalaFonte = parseFloat(localStorage.getItem("escalaFonte") || "1");
    document.documentElement.style.fontSize = (16 * escalaFonte) + "px";

    if (localStorage.getItem("tema") === "high-contrast") {
      document.documentElement.setAttribute("data-theme", "high-contrast");
    }

    function alternarContraste() {
      const atual = document.documentElement.getAttribute("data-theme");
      const novo = atual === "high-contrast" ? "default" : "high-contrast";
      if (novo === "high-contrast") {
        document.documentElement.setAttribute("data-theme", "high-contrast");
      } else {
        document.documentElement.removeAttribute("data-theme");
      }
      localStorage.setItem("tema", novo);
    }

    function aumentarFonte() {
      escalaFonte = escalaFonte >= 1.25 ? 1 : +(escalaFonte + 0.125).toFixed(3);
      document.documentElement.style.fontSize = (16 * escalaFonte) + "px";
      localStorage.setItem("escalaFonte", escalaFonte);
    }

    async function carregarPainel() {
      const [resLotes, resInd] = await Promise.all([
        fetch("/api/v1/lotes"),
        fetch("/api/v1/indicadores-ods")
      ]);
      const lotes = await resLotes.json();
      const ind = await resInd.json();

      document.getElementById("indEstoque").textContent = ind.estoque_ativo_kg + " kg";
      document.getElementById("indSalvos").textContent = ind.quilos_salvos_kg + " kg";
      document.getElementById("indRefeicoes").textContent = ind.refeicoes_estimadas + " refeições";

      const container = document.getElementById("listaLotes");
      container.innerHTML = lotes.map(l => `
        <article class="card ${l.nivel_urgencia}">
          <div>
            <span class="badge">${l.nivel_urgencia === "CRITICO" ? "🚨" : l.nivel_urgencia === "ATENCAO" ? "⚠️" : "✅"} ${l.rotulo_urgencia}</span>
            <h2>${l.alimento}</h2>
            <p class="meta"><strong>Saldo:</strong> ${l.peso_kg} kg • <strong>Lote:</strong> ${l.codigo_lote}</p>
            <p class="meta"><strong>Validade:</strong> ${l.data_validade.split("-").reverse().join("/")}</p>
          </div>
          <button type="button" class="primary" onclick="abrirModalBaixa(${l.id}, '${l.alimento.replace(/'/g, "")}', ${l.peso_kg})">
            Dar Baixa
          </button>
        </article>
      `).join("");
    }

    async function salvarLote(e) {
      e.preventDefault();
      const body = {
        alimento: document.getElementById("alimento").value,
        peso_kg: parseFloat(document.getElementById("peso").value),
        codigo_lote: document.getElementById("codigo").value,
        data_validade: document.getElementById("validade").value
      };
      const res = await fetch("/api/v1/lotes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      if (res.ok) {
        e.target.reset();
        document.getElementById("modalCadastro").close();
        carregarPainel();
      }
    }

    function abrirModalBaixa(id, alimento, saldo) {
      document.getElementById("baixaLoteId").value = id;
      document.getElementById("baixaDescricao").textContent = `${alimento} (Disponível: ${saldo} kg)`;
      const inputPeso = document.getElementById("pesoBaixa");
      inputPeso.max = saldo;
      inputPeso.value = saldo;
      document.getElementById("modalBaixa").showModal();
    }

    async function confirmarBaixa(e) {
      e.preventDefault();
      const id = document.getElementById("baixaLoteId").value;
      const body = {
        peso_baixa: parseFloat(document.getElementById("pesoBaixa").value),
        motivo_saida: document.getElementById("motivoSaida").value
      };
      const res = await fetch(`/api/v1/lotes/${id}/baixa`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
      if (res.ok) {
        document.getElementById("modalBaixa").close();
        carregarPainel();
      } else {
        const err = await res.json();
        alert(err.detail || "Erro ao registrar baixa.");
      }
    }

    carregarPainel();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home():
    return HTML_PAGE

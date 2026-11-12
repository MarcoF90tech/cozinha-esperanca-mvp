# cozinha-esperanca-mvp
MVP de Gestão de Estoque Perecível (PEPS/FIFO) com foco em acessibilidade e combate ao desperdício de alimentos (ODS 2) para a Cozinha Comunitária Esperança.
# 🍲 Cozinha Comunitária Esperança — MVP de Gestão de Estoque (PEPS/FIFO)

Aplicação Web Responsiva (*Mobile-First*) desenvolvida para automatizar o controle de insumos perecíveis doados, priorizando o consumo pelo método **PEPS (Primeiro que Entra, Primeiro que Sai)** e reduzindo o desperdício de alimentos em organizações sociais.

---

## 🎯 Propósito e Alinhamento ao ODS 2
O projeto atende à **Associação Solidária Cozinha Comunitária Esperança**, mitigando a perda involuntária de hortifrútis perecíveis causada pelo controle manual. A solução contribui diretamente para a **Meta 2.1 dos Objetivos de Desenvolvimento Sustentável (ODS 2 — Fome Zero e Agricultura Sustentável)**, otimizando o aproveitamento seguro das doações destinadas a cerca de 250 beneficiários diários.

---

## ⚙️ Funcionalidades do MVP
* **RF01 — Cadastro de Insumos Perecíveis:** Registro rápido de nome, quantidade (kg) e data de validade estimada.
* **RF02 — Painel PEPS/FIFO:** Listagem ordenada automaticamente por urgência de vencimento (`CRÍTICO`, `ATENÇÃO`, `NORMAL`).
* **RF03 — Baixa de Estoque:** Registro de consumo para o cardápio diário ou descarte com atualização em tempo real.
* **RF04 — Relatório Socioambiental (PDF):** Emissão de prestação de contas com total de quilos salvos do desperdício e estimativa de refeições garantidas (exclusivo para perfil *Gestor*).

---

## ♿ Acessibilidade e Inclusão Digital (RNF04)
Projetado para voluntários com baixo ou intermediário letramento digital em ambientes dinâmicos:
* **Sinalização Multimodal:** Identificação de urgência combinando **Cor + Ícone + Texto** (sem depender apenas de diferenciação cromática).
* **Ergonomia Mobile:** Áreas de toque $\ge 48 \times 48\text{px}$, tipografia $\ge 16\text{px}$ e contraste $\ge 4,5:1$.

---

## 🛠️ Stack Tecnológica Planejada
* **Front-end:** HTML5, CSS3 (Mobile-First), JavaScript
* **Back-end:** Python 3 + FastAPI + Pydantic (validação de dados)
* **Banco de Dados:** PostgreSQL
* **Relatórios:** Jinja2 + WeasyPrint (geração de PDF)
* **Infraestrutura:** Docker

---

---

## 🔒 Regras de Integridade, Segurança e Qualidade (Revisão Técnica)
Para garantir a confiabilidade dos dados operacionais e a inclusão dos voluntários na rotina da cozinha comunitária, o sistema implementa as seguintes travas arquiteturais:

* **Validação de Entrada (RNF02):** Uso de esquemas Pydantic no back-end para bloquear quantidades negativas ou nulas (`quantidade > 0 kg`), datas retroativas inválidas e baixas superiores ao saldo disponível no lote.
* **Controle de Acesso por Perfil (RNF01):** Segregação de rotas entre *Operador* (cadastro e baixa diária) e *Gestor* (acesso exclusivo à emissão de relatórios PDF de prestação de contas).
* **Diretrizes de Acessibilidade (RNF04):** Validação estrita de contraste mínimo de `4.5:1`, tipografia base de `16px`, áreas de clique `>= 48x48px` e redundância visual obrigatória (**Cor + Ícone + Texto**) em todos os alertas de vencimento.

## 📁 Estrutura Inicial do Projeto
```text
cozinha-esperanca-mvp/
├── backend/          # API REST FastAPI, modelos e schemas Pydantic
├── frontend/         # Interfaces responsivas (Cadastro, Dashboard PEPS, Alertas)
├── docs/             # Protótipo de alta fidelidade e roteiro de validação prática
├── .gitignore
└── README.md

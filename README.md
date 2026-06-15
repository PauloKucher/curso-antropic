# Claude Architect · Exam Trainer

App de estudo offline para a certificação **Claude Certified Architect — Foundations**.

## Como usar
Abra **`index.html`** no navegador (duplo clique). Não precisa de servidor — os dados ficam embutidos no próprio arquivo.

Modos disponíveis:
- **Simulado ponderado** (15 / 30 / 45 / 60) — amostra distribuída pelos pesos do exame.
- **Prova completa** — todas as 75 questões.
- **Treino por domínio** — só D1, D2, D3, D4 ou D5.
- Opções: embaralhar questões, embaralhar alternativas, feedback imediato.

No fim: **nota na escala 100–1000** (corte 720), desempenho por domínio e **gabarito comentado**. O histórico de notas fica salvo no `localStorage` do navegador (aba HISTÓRICO).

## Pesos / domínios
| Domínio | Peso | Questões no banco |
|---|---|---|
| D1 · Agentic Architecture & Orchestration | 27% | 20 |
| D2 · Tool Design & MCP Integration | 18% | 14 |
| D3 · Claude Code Configuration & Workflows | 20% | 15 |
| D4 · Prompt Engineering & Structured Output | 20% | 15 |
| D5 · Context Management & Reliability | 15% | 11 |
| **Total** | | **75** |

> A nota é ponderada: para cada domínio presente no simulado, `acerto% × peso`, normalizado pelos pesos presentes, mapeado para 100–1000.

## Arquivos
- `index.html` — o app (autocontido, abre offline).
- `questions.json` — banco de questões + metadados (fonte da verdade / backup).
- `raw/` — bancos por domínio (`d1..d5.json`) e o conjunto inicial (`v1.json`).
- `build.py` — regenera `questions.json` e `index.html` a partir de `raw/`.

## Adicionar / editar questões
1. Edite ou crie um arquivo em `raw/` (mesmo formato: `domain, q, options{A,B,C,D}, answer, explanation`).
2. Rode `python3 build.py` para regenerar `questions.json` e `index.html`.
# curso-antropic

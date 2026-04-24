# Changelog

Todas as mudanças notáveis neste projeto serão documentadas aqui.
Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

---

## [Unreleased]

---

## [2026-04-23d]

### Corrigido
- **`load_dotenv` com caminho absoluto**: substituído `os.path.dirname(__file__)` por `Path(__file__).resolve().parent` em `app.py` para evitar falha no subprocess do Flask reloader que não resolvia caminhos relativos corretamente.
- **Timeout do study plan**: aumentado de 30s para 90s em `llm_explainer.py`; chamadas ao Claude Haiku para geração de plano com 400+ decisões podem ultrapassar 30s.

### Resultado
- Study plan com LLM funcional localmente: 6 cards gerados, resumo personalizado, `error: null`.

---

## [2026-04-23c]

### Adicionado
- **`backend/.env`** (gitignored): variáveis de ambiente para dev local (`ANTHROPIC_API_KEY`, `JWT_SECRET_KEY`).
- **`python-dotenv`** adicionado a `requirements_dev.txt`; `app.py` carrega `.env` automaticamente via `load_dotenv()` na inicialização.

---

## [2026-04-23b]

### Adicionado
- **`backend/requirements_dev.txt`**: dependências para desenvolvimento local sem `psycopg2-binary` (incompatível com Python 3.13/Windows); ambiente local usa SQLite.

### Ambiente local
- Backend: `cd backend && python api/app.py` → `http://localhost:5000`
- Frontend: abrir `frontend/index.html` no browser (detecta `localhost` automaticamente e aponta para porta 5000)

---

## [2026-04-23]

### Corrigido
- **Imports `gaphunter` → `leaklab`**: 7 arquivos de teste importavam o nome antigo do pacote (`gaphunter`), causando `ModuleNotFoundError` em toda a suite `engine` e `regression`.
- **Coluna `raw_text` ausente no schema SQLite**: a coluna existia apenas na migração PostgreSQL; adicionada ao `CREATE TABLE` e à lista de migrações SQLite em `database/schema.py`, corrigindo 8 falhas na suite `database`.

### Adicionado
- **`CLAUDE.md`**: documentação para Claude Code com comandos de build/teste, arquitetura e stack.
- **`CHANGELOG.md`**: este arquivo.
- **`.gitignore`**: entradas para `backend/torneio_ingles.txt` (fixture local com dados pessoais) e `.claude/` (configuração do Claude Code).

### Resultado
- Testes: **227/227 passando** (todas as suites: engine, database, llm, api, regression).

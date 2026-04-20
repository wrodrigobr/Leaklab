# Como rodar os testes localmente

## 1. Instalar dependências de teste

```bash
pip install -r requirements_test.txt
```

> **Nota Windows:** se `pip install PyJWT` der conflito com um pacote `jwt` já instalado,
> rode primeiro: `pip uninstall jwt` e depois `pip install PyJWT`

## 2. Rodar todos os testes

```bash
# No diretório leaklab/backend/
python tests/run_all_tests.py

# Ou uma suite específica:
python tests/run_all_tests.py --suite engine
python tests/run_all_tests.py --suite api
python tests/run_all_tests.py --suite llm
```

## 3. Rodar um arquivo específico

```bash
python tests/test_api_endpoints.py
python tests/test_decision_engine.py
```

## Suites disponíveis

| Suite       | O que testa                                      |
|-------------|--------------------------------------------------|
| `engine`    | Engine de decisão, pipeline, MTT context         |
| `database`  | Schema, auth, repositórios, coach system         |
| `llm`       | Explainer, plano de estudos, coach IA            |
| `api`       | Todos os endpoints Flask (auth, analyze, replay) |
| `regression`| Torneio real completo, multi-decisão             |

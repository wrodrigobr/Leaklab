# LeakLab

Plataforma de coaching MTT — análise de decisões de poker com IA.

## Stack

- **Backend:** Python / Flask / SQLite
- **Frontend:** HTML + JS (estático)
- **IA:** Claude Haiku (explicações e resumos)
- **CI/CD:** GitHub Actions → Render + Vercel

## Deploy automático

Todo push para `main` dispara:
1. Suite completa de testes (184 casos)
2. Se aprovado → deploy backend no Render
3. Deploy frontend no Vercel

## Secrets necessários no GitHub

| Secret | Onde obter |
|---|---|
| `RENDER_API_KEY` | Render → Account Settings → API Keys |
| `RENDER_SERVICE_ID` | Render → seu serviço → Settings → Service ID |
| `VERCEL_TOKEN` | Vercel → Settings → Tokens |
| `VERCEL_ORG_ID` | Vercel → Settings → General → Your ID |
| `VERCEL_PROJECT_ID` | Vercel → seu projeto → Settings → General → Project ID |

## Primeiro deploy (manual)

### Backend (Render)
1. Acesse render.com → New → Web Service
2. Conecte o repositório GitHub
3. Root Directory: `backend`
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn api.app:app --bind 0.0.0.0:$PORT --workers 2`
6. Adicione o disco `/data` (1GB) em Settings → Disks
7. Copie o Service ID e adicione como secret `RENDER_SERVICE_ID`
8. Copie a URL gerada (ex: `https://leaklab-api.onrender.com`)

### Frontend (Vercel)
1. Acesse vercel.com → New Project
2. Conecte o repositório GitHub
3. Framework: Other
4. Root Directory: `frontend`
5. Após deploy, copie `VERCEL_ORG_ID` e `VERCEL_PROJECT_ID` de Settings

### Atualizar URL do backend no frontend
Em `frontend/index.html`, atualize a linha:
```js
return 'https://leaklab-api.onrender.com';
```
com a URL real do seu serviço Render.

## Desenvolvimento local

```bash
cd backend
pip install -r requirements.txt
python api/app.py
```

Frontend: abrir `frontend/index.html` diretamente no browser.

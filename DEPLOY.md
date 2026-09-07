# Deploy — visionOps AI (AIOps SLA Monitor)

Três formas de rodar, da mais simples à de produção:

| Alvo | Frontend | Backend | Quando |
|---|---|---|---|
| **Vercel + Render** | Vercel (estático) | Render (Docker, free) | link ao vivo do dia a dia |
| **Azure** | servido pelo container | Azure Container Instance | banca / apresentação final |
| **Local** | `npm run build` | `uvicorn` | desenvolvimento |

O frontend fala com o backend pela variável `VITE_API_BASE_URL` (vazia = mesma origem, usada
no container combinado e no dev com proxy do Vite). O backend libera CORS para
`localhost:5173`, para qualquer `*.vercel.app` e para o que estiver em `CORS_ORIGINS`.

---

## A) Vercel (frontend) + Render (backend)

### 1. Backend no Render

1. [dashboard.render.com](https://dashboard.render.com) → **New +** → **Blueprint** →
   conectar `PedroTresmondi/aiops-locaweb-dashboard`. O Render lê o `render.yaml`
   (web service Docker, plano free, health check `/health`).
2. Primeiro deploy leva ~5–8 min (build do `Dockerfile`). A URL fica tipo
   `https://visionops-ai.onrender.com`.
3. Testar: `https://visionops-ai.onrender.com/health` → `{"status":"ok",...}`.
4. Guardar essa URL para o passo 2.

O backend usa ~320 MB de RAM e treina os modelos em ~12 s na primeira chamada — cabe no
free tier (512 MB). **O free tier dorme após 15 min sem tráfego** (acorda em ~50 s): ver o
passo 3 (ping).

### 2. Frontend na Vercel

1. [vercel.com/new](https://vercel.com/new) → importar `PedroTresmondi/aiops-locaweb-dashboard`.
2. **Root Directory**: `frontend`. O `frontend/vercel.json` já define framework Vite,
   `npm ci`, `dist` e o rewrite de SPA.
3. **Environment Variables** → adicionar:
   `VITE_API_BASE_URL` = `https://visionops-ai.onrender.com` (a URL do passo 1, sem `/` no fim).
4. Deploy. A URL fica tipo `https://visionops-ai.vercel.app`.
5. Voltar ao Render → serviço → **Environment** → `CORS_ORIGINS` = `https://visionops-ai.vercel.app`
   → salvar (redeploy automático). *(O regex `*.vercel.app` já cobre isso, mas deixar explícito
   evita surpresa se o domínio mudar.)*

### 3. Manter o Render acordado (grátis)

[cron-job.org](https://cron-job.org) (grátis, sem cartão) → novo cronjob:
- URL: `https://visionops-ai.onrender.com/health`
- Intervalo: a cada 10 minutos
- Só isso. Enquanto o cron rodar, o backend não dorme.

Alternativa: UptimeRobot (monitor HTTP a cada 5 min).

---

## B) Azure (apresentação final)

Arquitetura definida na Sprint 3:

```
dataset ──► Azure Container Registry ──► Azure Container Instance (FastAPI) ──► Azure Database for MySQL
 (LW-DATASET)  acraiopsvisionopsai        aci-aiops-sla-monitor                  mysql-aiops-visionopsai
                                                 │                               aiopsdb (Chile Central)
                                   Managed Identity id-aiops-visionopsai (sem senha)
                                                 │
                                   Application Insights ──► Log Analytics Workspace
```

Resource Group `rg-aiops-sprint3-visionopsai` (East US). Rodar tudo no **Azure Cloud Shell**
(a VM local não tem Azure CLI).

```bash
# religar
az mysql flexible-server start -g rg-aiops-sprint3-visionopsai -n mysql-aiops-visionopsai
az container start          -g rg-aiops-sprint3-visionopsai -n aci-aiops-sla-monitor

# rebuild da imagem (a partir da raiz do repo, no Cloud Shell)
az acr build --registry acraiopsvisionopsai --image aiops-sla-monitor:v3 --build-arg INSTALL_AZURE=true .

# recriar o container com a nova imagem
az container create \
  --resource-group rg-aiops-sprint3-visionopsai --name aci-aiops-sla-monitor \
  --image acraiopsvisionopsai.azurecr.io/aiops-sla-monitor:v3 \
  --acr-identity  <resource-id-da-identidade> \
  --assign-identity <resource-id-da-identidade> \
  --dns-name-label aiops-sla-monitor-visionopsai --ports 8000 \
  --environment-variables \
      VISIONOPS_DATASOURCE=mysql \
      MYSQL_HOST=mysql-aiops-visionopsai.mysql.database.azure.com \
      MYSQL_USER=id-aiops-visionopsai MYSQL_DATABASE=aiopsdb \
      AZURE_CLIENT_ID=<client-id> \
      APPLICATIONINSIGHTS_CONNECTION_STRING="<connection-string>"
```

Sem `VISIONOPS_DATASOURCE=mysql` o container usa o Parquet embutido (demo sem depender do MySQL).

Contrato conferido no vídeo:

```bash
BASE=http://aiops-sla-monitor-visionopsai.eastus.azurecontainer.io:8000
curl $BASE/health
curl $BASE/incidentes/total      # {"total_incidentes_no_banco": 122543}
curl $BASE/previsao
```

Pausar depois: `az container stop ...` + `az mysql flexible-server stop ...`.

---

## C) Local

```bash
pip install -r backend/requirements.txt
cd frontend && npm ci && npm run build && cd ..
uvicorn backend.main:app --port 8000
# http://localhost:8000  (o FastAPI serve o React e a API juntos)
```

Dev com hot-reload: `uvicorn backend.main:app --reload --port 8000` num terminal e
`cd frontend && npm run dev` noutro (o Vite faz proxy de `/api` para `:8000`).

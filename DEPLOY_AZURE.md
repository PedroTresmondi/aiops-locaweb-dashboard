# Deploy no Azure — visionOps AI (AIOps SLA Monitor)

Arquitetura da Sprint 4 (mesma infraestrutura provisionada e evidenciada na Sprint 3):

```
dataset real ──► Azure Container Registry ──► Azure Container Instance (FastAPI) ──► Azure Database for MySQL
 (LW-DATASET)     acraiopsvisionopsai            aci-aiops-sla-monitor                 mysql-aiops-visionopsai
                                                 :8000 público                         aiopsdb (Chile Central)
                                                        │
                                         Managed Identity (id-aiops-visionopsai, sem senha)
                                                        │
                                          Application Insights ──► Log Analytics Workspace
                                          appi-aiops-visionopsai    law-aiops-visionopsai
```

Resource Group: `rg-aiops-sprint3-visionopsai` (East US). O MySQL fica em Chile Central
(única região aceita pela assinatura Azure for Students para o Flexible Server).

## Pré-requisitos

- Rodar os comandos no **Azure Cloud Shell** (`portal.azure.com`), autenticado — a VM local
  não tem Azure CLI.
- Recursos religados (ver `Diagnostico_Sprint4_visionOpsAi.md`, seção 5):

```bash
az mysql flexible-server start --resource-group rg-aiops-sprint3-visionopsai --name mysql-aiops-visionopsai
az container start --resource-group rg-aiops-sprint3-visionopsai --name aci-aiops-sla-monitor
```

## 1. Build e push da imagem

```bash
# a partir da raiz deste repositório, no Cloud Shell
az acr build --registry acraiopsvisionopsai --image aiops-sla-monitor:v3 .
```

O `Dockerfile` compila o frontend React, instala `backend/requirements-azure.txt` e serve
o build estático pelo próprio FastAPI.

## 2. Recriar o Container Instance com a nova imagem

```bash
az container create \
  --resource-group rg-aiops-sprint3-visionopsai \
  --name aci-aiops-sla-monitor \
  --image acraiopsvisionopsai.azurecr.io/aiops-sla-monitor:v3 \
  --acr-identity /subscriptions/<sub>/resourceGroups/rg-aiops-sprint3-visionopsai/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-aiops-visionopsai \
  --assign-identity /subscriptions/<sub>/resourceGroups/rg-aiops-sprint3-visionopsai/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-aiops-visionopsai \
  --dns-name-label aiops-sla-monitor-visionopsai \
  --ports 8000 \
  --environment-variables \
      VISIONOPS_DATASOURCE=mysql \
      MYSQL_HOST=mysql-aiops-visionopsai.mysql.database.azure.com \
      MYSQL_USER=id-aiops-visionopsai \
      MYSQL_DATABASE=aiopsdb \
      AZURE_CLIENT_ID=<client-id-da-identidade> \
      APPLICATIONINSIGHTS_CONNECTION_STRING="<connection-string-do-appi>"
```

Sem `VISIONOPS_DATASOURCE=mysql` o container usa o snapshot Parquet embutido na imagem
(útil para uma demo sem depender do MySQL religado).

## 3. Conferir (contrato usado no vídeo pitch)

```bash
BASE=http://aiops-sla-monitor-visionopsai.eastus.azurecontainer.io:8000
curl $BASE/health
curl $BASE/incidentes/total          # {"total_incidentes_no_banco": 122543}
curl $BASE/previsao                  # previsão real D+1/D+7 dos 4 alvos
curl $BASE/previsao/historico
```

A interface completa (fila operacional, triagem, diagnóstico, alocação preventiva, monitor
de dados) fica em `$BASE/`.

## 4. Pausar depois de gravar (evitar custo)

```bash
az container stop --resource-group rg-aiops-sprint3-visionopsai --name aci-aiops-sla-monitor
az mysql flexible-server stop --resource-group rg-aiops-sprint3-visionopsai --name mysql-aiops-visionopsai
```

## Rodar local (sem Azure)

```bash
pip install -r backend/requirements.txt
cd frontend && npm install && npm run build && cd ..
uvicorn backend.main:app --port 8000
# abrir http://localhost:8000
```

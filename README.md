# Photo Lab — Retoque com IA

Aplicação web para **análise automática de pele** e **laudo técnico de retoque fotográfico**. O usuário envia uma foto, e o sistema gera um relatório estruturado (itens essenciais e recomendados), localiza pontos na imagem com IA (Moondream/Fal AI) e exibe marcadores interativos com tooltips.

![Photo Lab — Studio](https://img.shields.io/badge/Photo%20Lab-Studio-teal?style=flat-square)

---

## Índice

- [Funcionalidades](#funcionalidades)
- [Stack tecnológica](#stack-tecnológica)
- [Pré-requisitos](#pré-requisitos)
- [Configuração](#configuração)
- [Execução](#execução)
- [Arquitetura](#arquitetura)
- [API](#api)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Licença](#licença)

---

## Funcionalidades

- **Upload de foto** — Arraste ou selecione uma imagem (JPG, PNG, WebP).
- **Laudo técnico** — Análise de pele por zonas (testa, olhos, maçãs do rosto, boca, pescoço) com priorização em **essencial** e **recomendado**.
- **Marcadores na imagem** — Pontos localizados por IA (Moondream) com descrição e técnica sugerida; tooltips ao passar o mouse.
- **Processamento assíncrono** — Upload imediato + job em background (Redis/RQ); o frontend faz polling do status até concluir.
- **Histórico** — Listagem de análises anteriores com thumbnail, data e preview; reabertura de laudos salvos.

---

## Stack tecnológica

| Camada        | Tecnologia |
|---------------|------------|
| **Backend**   | Python 3.12, FastAPI, Uvicorn |
| **Frontend**  | HTML, CSS (Tailwind), JavaScript vanilla |
| **IA – Agente** | Agno + OpenRouter (modelo com visão, ex.: Gemini 2.0 Flash) |
| **IA – Pontos/Detecção** | Fal AI (Moondream 3 – point/detect) |
| **Fila**      | Redis, RQ (Redis Queue) |
| **Servir UI** | Nginx (Alpine) |
| **Orquestração** | Docker Compose |

---

## Pré-requisitos

- **Docker** e **Docker Compose** (recomendado), ou
- **Python 3.12+**, **Redis** e **Node** (opcional, só para rodar frontend em dev).

---

## Configuração

1. **Clone o repositório**

   ```bash
   git clone git@github.com:williamreis/photo-lab.git
   cd photo-lab
   ```

2. **Crie o arquivo de ambiente**

   ```bash
   cp .env.example .env
   ```

3. **Defina as chaves obrigatórias no `.env`**

   - **FAL_KEY** — API key da [Fal AI](https://fal.ai) (obrigatória para localização de pontos e detecção).
   - **OPENROUTER_API_KEY** — API key do [OpenRouter](https://openrouter.ai) (obrigatória para o agente de análise de pele).

   Opcionalmente:

   - **AGENT_MODEL** — Modelo com visão no OpenRouter (padrão: `google/gemini-2.0-flash`).
   - **REDIS_URL** — URL do Redis (padrão em Docker: `redis://redis:6379/0`).
   - **PORT** / **FRONTEND_PORT** — Portas da API (8000) e do frontend (8101).

   Exemplo mínimo:

   ```env
   FAL_KEY=sua-chave-fal
   OPENROUTER_API_KEY=sua-chave-openrouter
   ```

---

## Execução

### Com Docker Compose (recomendado)

Na raiz do projeto:

```bash
docker compose up --build
```

- **API:** http://localhost:8000  
- **Documentação da API:** http://localhost:8000/docs  
- **Frontend (Photo Lab):** http://localhost:8101  

Serviços: `redis`, `api`, `worker`, `frontend`. O worker processa os jobs de análise em background.

### Sem Docker (desenvolvimento)

1. **Redis em execução** (ex.: `redis-server` na porta 6379).

2. **Backend:**

   ```bash
   cd backend
   pip install -r ../requirements.txt
   export $(grep -v '^#' ../.env | xargs)
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Worker** (em outro terminal):

   ```bash
   cd backend
   export $(grep -v '^#' ../.env | xargs)
   python worker.py
   ```

4. **Frontend:** sirva a pasta `frontend/` (ex.: com um servidor estático ou apontando o Nginx para ela). Em produção com Docker, o Nginx faz proxy para a API; em dev local, ajuste a base URL no frontend se a API estiver em outra origem.

---

## Arquitetura

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Nginx     │────▶│   FastAPI   │────▶│   Redis     │
│  (frontend) │     │   (API)     │     │   (fila)    │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       │                   │                   ▼
       │                   │            ┌─────────────┐
       │                   │            │   Worker    │
       │                   │            │   (RQ)      │
       │                   │            └──────┬──────┘
       │                   │                   │
       │                   │                   ▼
       │                   │            Fal AI + OpenRouter
       │                   │            (point, detect, agent)
       ▼                   ▼
   Uploads estáticos   /api/v1/*  (agent, history, jobs, point, detect)
```

- O **frontend** envia a imagem para `/api/v1/agent/analyze/persist_async`.
- A **API** persiste o arquivo, enfileira um job no Redis e devolve `job_id` e `history_id`.
- O **worker** executa o job: chama o agente (OpenRouter) para o laudo e o Fal AI (Moondream) para os pontos; grava o resultado no histórico.
- O **frontend** faz polling em `/api/v1/jobs/{job_id}` e, ao concluir, carrega o laudo e os marcadores a partir do histórico.

---

## API

Base URL: `/api/v1`.

| Recurso | Método | Descrição |
|--------|--------|-----------|
| **Agent** | | |
| `/agent/analyze` | POST | Analisa imagem e retorna laudo + pontos (síncrono). |
| `/agent/analyze/image` | POST | Como acima, mas retorna também a imagem com pontos em base64. |
| `/agent/analyze/persist` | POST | Salva upload, analisa e retorna URL da foto + laudo + marcadores. |
| `/agent/analyze/persist_async` | POST | Salva upload e enfileira análise; retorna `job_id` e `history_id`. |
| **Jobs** | | |
| `/jobs/{job_id}` | GET | Status do job: `queued` \| `processing` \| `done` \| `failed`; se `done`, inclui resultado. |
| **Histórico** | | |
| `/history` | GET | Lista resumos das análises (id, data, preview, status, etc.). |
| `/history/{entry_id}` | GET | Detalhe de uma análise (laudo, marcadores, pontos, imagem). |
| **Point** | | |
| `/point/upload` | POST | Localiza pontos na imagem (upload + query). |
| `/point/upload/image` | POST | Idem, retorna imagem com pontos desenhados (PNG). |
| `/point/path` | POST | Localiza pontos em imagem por caminho local (ex.: `images/foto.jpg`). |
| **Detect** | | |
| `/detect/upload` | POST | Detecção de objetos por upload + prompt. |
| `/detect/url` | POST | Detecção por URL da imagem. |

- **Health check:** `GET /health` → `{"status": "healthy"}`.
- **Metadados da API:** `GET /api` → mensagem e link para a UI.

Documentação interativa: **http://localhost:8000/docs** (Swagger UI).

---

## Estrutura do projeto

```
photo-lab/
├── backend/
│   ├── main.py              # App FastAPI, montagem de rotas e /uploads
│   ├── config.py            # Variáveis de ambiente e paths
│   ├── worker.py            # Worker RQ (processa jobs)
│   ├── routes/              # Rotas da API (agent, jobs, history, point, detect)
│   ├── services/            # Lógica de negócio (agent, point, detect, history, queue)
│   ├── schemas/             # Modelos Pydantic (request/response)
│   ├── jobs/                # Definição dos jobs RQ (ex.: analyze_persist_job)
│   ├── prompts/             # Prompts do agente (ex.: skin.md)
│   ├── uploads/             # Imagens enviadas (persistidas)
│   ├── history/             # Histórico de análises (JSON)
│   └── output/              # Saídas auxiliares (agent, point, detect)
├── frontend/
│   ├── index.html           # Página única (upload, resultado, histórico)
│   ├── assets/
│   │   ├── app.js           # Lógica: upload, polling, laudo, marcadores
│   │   └── styles.css       # Estilos (Tailwind + custom)
│   └── nginx/
│       └── nginx-frontend.conf
├── docker-compose.yml       # redis, api, worker, frontend
├── Dockerfile               # Imagem Python para api/worker
├── requirements.txt
├── .env.example
└── README.md
```

---

## Variáveis de ambiente

| Variável | Obrigatória | Descrição |
|----------|-------------|-----------|
| `FAL_KEY` | Sim | Chave da API Fal AI (point/detect). |
| `OPENROUTER_API_KEY` | Sim | Chave OpenRouter para o agente de análise. |
| `AGENT_MODEL` | Não | Modelo com visão (padrão: `google/gemini-2.0-flash`). |
| `REDIS_URL` | Não | URL do Redis (padrão: `redis://localhost:6379/0`). |
| `PORT` | Não | Porta da API (padrão: 8000). |
| `FRONTEND_PORT` | Não | Porta do Nginx/frontend (padrão: 8101). |

---

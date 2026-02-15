# 🤖 Bot Telegram SMM — SaaS White-Label

Sistema completo de bot Telegram para revenda automatizada de serviços SMM via API.

---

## ⚡ Quick Start Local

```bash
pip install -r requirements.txt
cp .env.example .env       # Edite e coloque seu BOT_TOKEN
python run.py
```

---

## 🚨 ANTES DE TUDO: Estrutura do Repositório

Quando subir no GitHub, os arquivos devem estar **NA RAIZ do repositório**, não dentro de uma pasta.

### ❌ ERRADO (arquivos dentro de subpasta):
```
meu-repo/
└── SMM PAINEL/        ← subpasta!
    ├── Dockerfile
    ├── run.py
    └── bot/
```

### ✅ CORRETO (arquivos na raiz):
```
meu-repo/
├── Dockerfile
├── Procfile
├── requirements.txt
├── runtime.txt
├── run.py
└── bot/
```

> **Se seus arquivos já estão dentro de uma subpasta**, você precisa configurar o **Root Directory** no painel da hospedagem (ex: `SMM PAINEL`). Veja as instruções de cada plataforma abaixo.

---

## 🟢 RENDER (Gratuito — Web Service)

### Passo a passo manual:

1. Acesse [render.com](https://render.com) e faça login
2. Clique em **New +** → **Web Service**
3. Conecte seu repositório do GitHub
4. Configure:

| Campo | Valor |
|-------|-------|
| **Name** | `smm-bot` (ou qualquer nome) |
| **Region** | Qualquer (ex: Oregon) |
| **Root Directory** | `SMM PAINEL` ⚠️ (só se seus arquivos estão dentro desta pasta no repo. Se estão na raiz, deixe em branco) |
| **Environment** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python run.py` |

5. Vá em **Environment** → Adicione as variáveis:

| Variável | Valor |
|----------|-------|
| `BOT_TOKEN` | Seu token do BotFather |
| `PYTHON_VERSION` | `3.11.9` |
| `PORT` | (NÃO ADICIONE — Render define automaticamente) |

6. Clique **Create Web Service**
7. Aguarde o deploy (3-5 minutos)

### Se der erro de Python:
- Adicione a variável `PYTHON_VERSION` = `3.11.9`
- E tenha o arquivo `runtime.txt` com `python-3.11.9` dentro

### Se der erro de Dockerfile:
- No painel, mude **Environment** de "Docker" para **"Python 3"**
- Ou se quiser usar Docker: garanta que o **Root Directory** está apontando para onde o Dockerfile está

---

## 🟣 RAILWAY (Gratuito — $5 crédito/mês)

### Passo a passo manual:

1. Acesse [railway.app](https://railway.app) e faça login com GitHub
2. Clique em **New Project** → **Deploy from GitHub Repo**
3. Selecione seu repositório
4. Railway detecta automaticamente o Procfile ou Dockerfile
5. Se seus arquivos estão em subpasta:
   - Vá em **Settings** → **Root Directory** → digite `SMM PAINEL`
6. Configure as variáveis:
   - Clique em **Variables** → **New Variable**

| Variável | Valor |
|----------|-------|
| `BOT_TOKEN` | Seu token do BotFather |

7. Railway faz deploy automático!

### Se Railway não detectar:
- Ele lê o `Procfile` → `web: python run.py`
- Build: detecta `requirements.txt` automaticamente
- Se não funcionar, vá em Settings e configure:
  - **Build Command**: `pip install -r requirements.txt`
  - **Start Command**: `python run.py`

---

## 🔵 KOYEB (Gratuito — Starter)

### Passo a passo manual:

1. Acesse [koyeb.com](https://www.koyeb.com) e faça login
2. Clique em **Create App** → **GitHub**
3. Conecte o repositório
4. Configure:

| Campo | Valor |
|-------|-------|
| **Builder** | `Dockerfile` ou `Buildpack` |
| **Dockerfile location** | `SMM PAINEL/Dockerfile` (se subpasta) ou `Dockerfile` (se raiz) |
| **Instance type** | `Free` (nano) |

5. Se usar Buildpack:
   - **Build Command**: `pip install -r requirements.txt`
   - **Run Command**: `python run.py`
6. Em **Environment variables**:

| Variável | Valor |
|----------|-------|
| `BOT_TOKEN` | Seu token do BotFather |
| `PORT` | `8000` |

7. Clique **Deploy**

---

## 🟠 FLY.IO (Gratuito — 3 máquinas)

### Passo a passo manual:

1. Instale o CLI: [fly.io/docs/getting-started/installing-flyctl](https://fly.io/docs/getting-started/installing-flyctl/)
2. No terminal, na pasta do projeto:

```bash
fly auth login
fly launch               # Detecta Dockerfile automaticamente
fly secrets set BOT_TOKEN=seu_token_aqui
fly deploy
```

3. Se seus arquivos estão em subpasta:
```bash
cd "SMM PAINEL"
fly launch
```

---

## 🖥️ VPS (Ubuntu/Debian — Manual)

### Passo a passo completo:

```bash
# 1. Instalar Python 3.11
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip git

# 2. Clonar repositório
git clone https://github.com/SEU_USUARIO/SEU_REPO.git
cd SEU_REPO
# Se subpasta: cd "SMM PAINEL"

# 3. Criar ambiente virtual
python3.11 -m venv .venv
source .venv/bin/activate

# 4. Instalar dependências
pip install -r requirements.txt

# 5. Configurar .env
cp .env.example .env
nano .env
# Coloque: BOT_TOKEN=seu_token_aqui

# 6. Rodar (teste)
python run.py

# 7. Rodar em background (persistente)
nohup python run.py > bot.log 2>&1 &

# 8. OU com systemd (reinicia automaticamente):
```

### Systemd (recomendado para VPS):

Crie o arquivo `/etc/systemd/system/smm-bot.service`:

```ini
[Unit]
Description=SMM Bot Telegram
After=network.target

[Service]
Type=simple
User=seu_usuario
WorkingDirectory=/caminho/para/projeto
ExecStart=/caminho/para/projeto/.venv/bin/python run.py
Restart=always
RestartSec=5
Environment=BOT_TOKEN=seu_token_aqui

[Install]
WantedBy=multi-user.target
```

Depois:
```bash
sudo systemctl daemon-reload
sudo systemctl enable smm-bot
sudo systemctl start smm-bot
sudo systemctl status smm-bot    # Verificar se está rodando
sudo journalctl -u smm-bot -f   # Ver logs em tempo real
```

---

## 🐳 Docker (Manual)

```bash
cd "SMM PAINEL"    # Se subpasta
docker build -t smm-bot .
docker run -d --name smm-bot -e BOT_TOKEN=seu_token_aqui --restart unless-stopped smm-bot
```

### Docker Compose (opcional):

Crie `docker-compose.yml`:
```yaml
version: "3.8"
services:
  bot:
    build: .
    environment:
      - BOT_TOKEN=seu_token_aqui
    restart: unless-stopped
```

Depois: `docker-compose up -d`

---

## 🔧 Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|----------|:-----------:|-----------|
| `BOT_TOKEN` | ✅ | Token do BotFather (Telegram) |
| `PYTHON_VERSION` | ❌ | Forçar versão do Python no Render (`3.11.9`) |
| `PORT` | ❌ | Auto-definida pelo PaaS. Se existir, sobe health server HTTP |

---

## 🧠 Como Funciona a Detecção Automática

| Condição | Comportamento |
|----------|---------------|
| `PORT` definida | Sobe health server HTTP + Polling (Web Service) |
| `PORT` não definida | Polling puro (Worker / VPS) |
| Render detectado | Log mostra "Ambiente: Render" |
| Railway detectado | Log mostra "Ambiente: Railway" |
| Docker detectado | Log mostra "Ambiente: Docker" |

---

## 📁 Estrutura do Projeto

```
├── run.py                  # Entry point (auto-detect ambiente)
├── Procfile                # PaaS: web + worker
├── Dockerfile              # Container (Python 3.11.9)
├── render.yaml             # Render Blueprint
├── runtime.txt             # Python version (Render/Railway)
├── requirements.txt        # Dependências
├── .env.example            # Template de variáveis
├── bot/
│   ├── main.py             # Boot: handlers, middlewares, scheduler
│   ├── config.py           # Config (DB > .env > defaults)
│   ├── database/
│   │   ├── connection.py   # SQLite + schema + backup
│   │   ├── queries.py      # CRUD
│   │   └── queries_owner.py
│   ├── services/
│   │   ├── smm_api.py      # API SMM (retry + cache)
│   │   ├── scheduler.py    # Tarefas periódicas
│   │   ├── license.py      # Licença SHA256
│   │   ├── plan_manager.py # Vencimento de planos
│   │   ├── pricing.py      # Preços (Decimal)
│   │   ├── mercadopago.py  # PIX Mercado Pago
│   │   └── hoopay.py       # PIX Hoopay
│   ├── handlers/           # Comandos Telegram
│   ├── keyboards/          # Teclados inline
│   ├── middlewares/        # Antiflood, auth, permissões
│   └── utils/              # Helpers, logger
└── data/                   # (criado automaticamente)
    ├── bot.db
    ├── backups/
    └── logs/
```

---

## 🛡️ Funcionalidades

- ✅ Compra automatizada via API SMM
- ✅ Pagamento PIX (Mercado Pago + Hoopay)
- ✅ Hierarquia Owner → Admin → Usuário
- ✅ Planos com vencimento automático
- ✅ Sincronização automática (60min) + manual
- ✅ Antiflood + rate limiting
- ✅ Backup automático diário
- ✅ Shutdown gracioso (SIGTERM)
- ✅ Health check HTTP (quando PORT definida)
- ✅ Watchdog com auto-restart (até 10x)
- ✅ Token nunca exposto em logs

---

## 📋 Primeiro Uso

1. Abra o bot no Telegram
2. Envie `/definir_dono` para se tornar dono
3. Use `/dono` para gerenciar admins e planos
4. Use `/admin` para configurar API e pagamentos

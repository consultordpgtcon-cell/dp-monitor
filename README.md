# Monitor Legislativo — Departamento Pessoal

Painel automático de monitoramento de atualizações da **Receita Federal**, **Ministério do Trabalho** e **eSocial**, com análise de impacto via IA.

---

## Como funciona

```
Todo dia às 06h → GitHub Actions roda o coletor Python
                → Filtra por relevância para o DP
                → Analisa com IA (Claude)
                → Atualiza o painel online (GitHub Pages)
                → Envia e-mail com resumo
```

---

## Configuração — Passo a Passo Completo

### PASSO 1 — Criar conta no GitHub

1. Acesse [github.com](https://github.com) e clique em **Sign up**
2. Escolha um nome de usuário (ex: `dp-suaempresa`)
3. Confirme o e-mail

---

### PASSO 2 — Criar o repositório

1. Após login, clique no **+** (canto superior direito) → **New repository**
2. Preencha:
   - **Repository name:** `dp-monitor`
   - **Visibility:** Public *(necessário para GitHub Pages gratuito)*
   - Marque **Add a README file**
3. Clique em **Create repository**

---

### PASSO 3 — Fazer upload dos arquivos

1. Na página do repositório, clique em **Add file** → **Upload files**
2. Faça upload de **todos os arquivos e pastas** deste projeto:
   - `main.py`
   - `requirements.txt`
   - `.gitignore`
   - pasta `scripts/` (com todos os `.py` dentro)
   - pasta `data/` (com `atualizacoes.json`)
   - pasta `docs/` (com `index.html`)
   - pasta `.github/workflows/` (com `coleta_diaria.yml`)
3. Clique em **Commit changes**

> **Dica:** Se o upload de pastas não funcionar, use o botão **Create new file** para criar cada arquivo manualmente, colando o conteúdo.

---

### PASSO 4 — Configurar as variáveis secretas

As senhas e chaves nunca ficam no código — ficam nos **Secrets** do GitHub.

1. Na página do repositório, clique em **Settings** (aba superior)
2. No menu lateral, clique em **Secrets and variables** → **Actions**
3. Clique em **New repository secret** para cada uma abaixo:

| Nome do Secret | O que colocar |
|---|---|
| `ANTHROPIC_API_KEY` | Chave da API Claude (obter em console.anthropic.com) |
| `EMAIL_REMETENTE` | Seu e-mail Gmail |
| `EMAIL_SENHA_APP` | Senha de app do Gmail (ver PASSO 4.1) |
| `EMAIL_DESTINATARIOS` | E-mails separados por vírgula |

#### PASSO 4.1 — Criar senha de app no Gmail

1. Acesse [myaccount.google.com](https://myaccount.google.com)
2. Clique em **Segurança** → **Verificação em duas etapas** (ative se necessário)
3. Volte em **Segurança** → **Senhas de app**
4. Escolha **Outro (nome personalizado)** → digite `Monitor DP`
5. Copie a senha de 16 caracteres gerada → cole no Secret `EMAIL_SENHA_APP`

---

### PASSO 5 — Ativar o GitHub Pages

1. Em **Settings** → **Pages** (menu lateral)
2. Em **Source**, selecione **Deploy from a branch**
3. Em **Branch**, selecione `main` e pasta `/docs`
4. Clique em **Save**
5. Aguarde ~2 minutos — seu painel estará em:
   ```
   https://SEU-USUARIO.github.io/dp-monitor
   ```

---

### PASSO 6 — Testar o sistema manualmente

1. Vá na aba **Actions** do repositório
2. Clique em **Monitor Legislativo — Coleta Diária**
3. Clique em **Run workflow** → **Run workflow**
4. Acompanhe a execução em tempo real (dura ~3 minutos)
5. Acesse seu painel para ver as atualizações

---

### PASSO 7 — Obter chave da API Claude (Anthropic)

1. Acesse [console.anthropic.com](https://console.anthropic.com)
2. Crie uma conta gratuita
3. Vá em **API Keys** → **Create Key**
4. Copie a chave (começa com `sk-ant-...`)
5. Cole no Secret `ANTHROPIC_API_KEY`

> **Custo estimado:** Para ~20 análises/dia, o custo é de aproximadamente R$ 2–5/mês.

---

## Estrutura do projeto

```
dp-monitor/
├── .github/
│   └── workflows/
│       └── coleta_diaria.yml   ← agendamento automático
├── scripts/
│   ├── coletor.py              ← faz o scraping dos sites
│   ├── analisador.py           ← análise com IA (Claude)
│   ├── alertas.py              ← envia e-mail
│   └── gerar_painel.py         ← gera o HTML do painel
├── data/
│   └── atualizacoes.json       ← banco de dados (JSON)
├── docs/
│   └── index.html              ← painel público (GitHub Pages)
├── main.py                     ← orquestrador principal
├── requirements.txt
└── .gitignore
```

---

## Personalizações

### Adicionar/remover fontes monitoradas

Edite `scripts/coletor.py`, seção `FONTES`.

### Alterar horário da coleta

Edite `.github/workflows/coleta_diaria.yml`, linha `cron`.
Use [crontab.guru](https://crontab.guru) para gerar expressões cron.

### Adicionar palavras-chave relevantes

Edite `scripts/coletor.py`, listas `PALAVRAS_ALTA` e `PALAVRAS_MEDIA`.

---

## Suporte

Em caso de dúvidas, abra uma **Issue** neste repositório.

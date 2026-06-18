# 💼 Project-Emprego

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.0%2B-5865F2?logo=discord&logoColor=white)](https://discordpy.readthedocs.io/en/stable/)
[![aiosqlite](https://img.shields.io/badge/aiosqlite-SQLite--Async-orange?logo=sqlite&logoColor=white)](https://github.com/omnilib/aiosqlite)
[![python-jobspy](https://img.shields.io/badge/JobSpy-Scraper-success?logo=pandas&logoColor=white)](https://github.com/speedyapply/JobSpy)

O **Project-Emprego** é um bot para Discord assíncrono e pronto para produção projetado para automatizar o monitoramento e envio de alertas de vagas de emprego. O bot utiliza a biblioteca **JobSpy** para agregar vagas do **LinkedIn**, **Indeed**, **Glassdoor**, **ZipRecruiter** e **Google Jobs**, salvando as configurações do servidor e rastreando vagas já enviadas em um banco de dados local **SQLite** gerenciado de forma assíncrona com **aiosqlite**.

---

## ✨ Funcionalidades Principais

*   **Interface Baseada em Slash Commands (`/`)**: Todos os comandos do bot utilizam a API moderna de interações do Discord.
*   **Configuração Dinâmica (`/setup`)**: Interface UI com formulário Modal para digitação de cidades e Menu Suspenso (`discord.ui.Select`) de escolha múltipla para os sites/motores de busca a monitorar.
*   **Monitoramento Periódico**: Loop periódico executado a cada 10 minutos para pesquisar novas vagas sem bloquear a execução geral do bot (`run_in_executor`).
*   **Prevenção de Duplicados**: Banco de dados registra cada vaga enviada por servidor (`sent_jobs`) garantindo que as mesmas vagas nunca sejam repetidas.
*   **Robustez e Resiliência**: Tratamento de erros completo em todo o ciclo de raspagem. Se a API do JobSpy falhar ou sofrer timeout, o bot apenas ignora o ciclo e tenta novamente após 10 minutos sem crashar.
*   **Visual Premium**: Envio das novas vagas formatadas como `discord.Embed` modernos com links diretos, informações de empresa, localização e fonte original da vaga.

---

## 📂 Estrutura de Diretórios

```text
V2-BOT_EMPREGO/
├── cogs/
│   ├── monitor.py       # Loop de monitoramento de 10 min, comandos /start e /stop
│   └── setup.py         # Slash command /setup, Modal e Select Menu UI
├── .env                 # Arquivo privado contendo o token do bot (não commitar)
├── .gitignore           # Lista de arquivos ignorados pelo Git
├── database.py          # Gerenciamento assíncrono do SQLite (aiosqlite)
├── main.py              # Ponto de entrada do Bot (inicialização e sincronização)
├── requirements.txt     # Dependências do Python
└── README.md            # Documentação do projeto
```

---

## 🛠️ Banco de Dados (SQLite Assíncrono)

O bot cria automaticamente o arquivo `antigravity.db` na raiz com o seguinte esquema:

### 1. Tabela `guild_configs`
Configurações de monitoramento de cada servidor:
*   `guild_id` (INTEGER PRIMARY KEY) — ID único do servidor Discord.
*   `channel_id` (INTEGER) — Canal de texto escolhido para alertas.
*   `cities` (TEXT) — Cidades monitoradas (ex: `"Lisboa, Porto"`).
*   `search_engines` (TEXT) — Sites monitorados (ex: `"linkedin,indeed"`).
*   `status` (TEXT) — Status do monitoramento (`'ON'` ou `'OFF'`).

### 2. Tabela `sent_jobs`
Registra as chaves únicas das vagas já notificadas por servidor:
*   `guild_id` (INTEGER) — ID do servidor correspondente.
*   `job_id` (TEXT) — Identificador único da vaga.
*   *Chave Primária Composta:* `(guild_id, job_id)`.

---

## 🚀 Como Executar o Projeto

### Pré-requisitos
*   **Python 3.10** ou superior instalado.
*   Uma conta de desenvolvedor no Discord com um Bot criado no [Discord Developer Portal](https://discord.com/developers/applications).
*   Permissões de **Bot** e **Application.Commands** ativadas no escopo do link de convite.

### Passos para Instalação

1.  **Clone o Repositório:**
    ```bash
    git clone https://github.com/seu-usuario/project-emprego.git
    cd project-emprego
    ```

2.  **Instale as Dependências:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configurar Variáveis de Ambiente:**
    *   Crie um arquivo `.env` baseado no arquivo de template `.env` gerado na raiz:
    ```ini
    DISCORD_TOKEN=SEU_TOKEN_DO_BOT_AQUI
    ```

4.  **Iniciar o Bot:**
    ```bash
    python main.py
    ```

---

## 🤖 Comandos Disponíveis

> ⚠️ **Nota:** Todos os comandos abaixo são exclusivos para usuários que possuem a permissão de **Administrador** no servidor.

*   `/setup <canal_de_texto>`: Inicia a configuração guiada do bot.
    1. Abre um **Modal** para inserir as cidades a monitorar (separadas por vírgula).
    2. Envia uma mensagem efémera com um **Menu Suspenso** (`Select`) para selecionar as plataformas (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs).
    3. Salva a configuração no banco de dados e ativa o monitoramento (`status = 'ON'`).
*   `/start`: Retoma o loop de monitoramento automático e altera o status para ativo (`ON`).
*   `/stop`: Pausa o loop de monitoramento automático e altera o status para inativo (`OFF`).

---

## 🔧 Personalização do País de Busca

Como o Indeed e o Glassdoor exigem a definição exata de país no JobSpy para filtrar as vagas, você pode ajustar o país padrão no início do arquivo `cogs/monitor.py`:

```python
# Altere para o seu país padrão (ex: 'portugal', 'brazil', 'usa')
DEFAULT_COUNTRY = "portugal"
```

---

## 📝 Licença

Este projeto é de código aberto e está disponível sob a licença MIT. Sinta-se livre para clonar, modificar e expandir de acordo com as suas necessidades!

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
*   **Monitoramento Periódico**: Loop periódico executado a cada 1 hora para pesquisar novas vagas de forma assíncrona, sem bloquear a execução geral do bot (`run_in_executor`).
*   **Busca Multitermo (Vagas + Emprego)**: O bot realiza pesquisas independentes e sequenciais para os termos `"vagas"` e `"emprego"` (uma requisição para cada palavra) por cidade e combina os resultados removendo duplicados de forma inteligente, aumentando a cobertura das vagas encontradas.
*   **Variações de Consulta e Fallback de Geolocalização (Google Jobs)**: Para contornar erros `400 Bad Request` em cidades menores ou não catalogadas pelas APIs de busca (como Mirandela), o monitor executa tanto buscas geolocalizadas específicas quanto buscas alargadas a nível nacional com a cidade embutida na pesquisa (ex: `"emprego em Mirandela"` com localização `"Portugal"`), fundindo os resultados sem duplicados.
*   **Filtro Geográfico de 15km**: Utiliza a API pública de mapas **Nominatim (OpenStreetMap)** e a **Fórmula de Haversine** para calcular a distância física entre a vaga e a cidade configurada. Vagas fora do raio de 15km são descartadas automaticamente. Contém otimizações de texto para evitar chamadas de API desnecessárias.
*   **Relatório de Varredura (Embed)**: Envia um relatório detalhado em formato de embed após cada ciclo de monitoramento (automático ou manual), contendo o total de vagas encontradas, enviadas, descartadas por motor (motivos de descarte: duplicadas, sem URL, distância fora do raio de 15km, ou falha de coordenadas), qual API do Google foi utilizada e as estatísticas cumulativas de consumo de API.
*   **Prevenção de Duplicados**: Banco de dados registra cada vaga enviada por servidor (`sent_jobs`) garantindo que as mesmas vagas nunca sejam repetidas.
*   **Controle de Rate Limit (6 Horas)**: As buscas no Google Jobs (motor `google`) são limitadas a rodar no máximo uma vez a cada 6 horas por cidade nos ciclos automáticos para preservar as cotas gratuitas das APIs. Esse limite é ignorado em varreduras manuais via `/varrer`.
*   **Fila de Fallbacks Resiliente para Google Jobs**: Se a API principal falhar ou tiver a chave expirada, o bot tenta automaticamente os outros provedores configurados (`SearchApi` ➔ `JSearch` ➔ `SerpApi`). Se todas falharem, usa a raspagem local do JobSpy como último recurso.
*   **Visual Premium**: Envio das novas vagas formatadas como `discord.Embed` modernos com cores personalizadas, links diretos, informações de empresa, localização e fonte original da vaga.
*   **Painel Web Integrado**: Dashboard web moderno (Flask) com tema escuro e detalhes em azul neon:
    *   **Autenticação**: Registo e Login de utilizadores associando-os aos seus servidores Discord configurados (lidos dinamicamente da base de dados).
    *   **Gestão de Fluxo Completo**: Visualizações separadas para *Vagas Disponíveis*, *Vagas Submetidas*, *Respostas Positivas*, *Respostas Negativas* e *Vagas Descartadas*.
    *   **Feedback de Candidatura**: Na visualização de *Submetidas*, cada vaga possui um seletor dinâmico para marcar a resposta como recebida, abrindo um modal pop-out para classificar o feedback como **Positivo** (enviado à página de Positivas) ou **Negativo** (enviado à página de Negativas).
    *   **Atualização em Tempo Real (AJAX)**: Botões de ação rápida e atualizações de feedback atualizam as vagas instantaneamente no painel com animações de fade-out e notificam no Discord com embeds personalizados (azul para submetidas, verde brilhante para positivas, cinza para negativas, vermelho para descartadas e esmeralda para disponíveis).
    *   **Estatísticas Avançadas com Gráficos**: Resumo analítico completo do fluxo com 8 KPI Cards (incluindo Taxa de Candidatura e Taxa de Sucesso baseada em respostas positivas) e gráficos interativos (Chart.js) cobrindo a distribuição de status de vagas, evolução diária temporal (últimos 14 dias), fontes de vagas e rankings das cidades.
    *   **Varredura Manual com Logs em Tempo Real (SSE)**: Botão "Varrer Empregos" na página principal que dispara imediatamente a busca completa (bypasseando o limite de 6h do Google Jobs e injetando automaticamente o motor do Google para máxima cobertura) e exibe os logs de execução do monitor passo a passo num console estilo terminal hacker, atualizando a listagem de vagas sem duplicações.

---

## 📂 Estrutura de Diretórios

```text
V2-BOT_EMPREGO/
├── cogs/
│   ├── monitor.py       # Loop de monitoramento, fallback de APIs, limite de 6h, embed de estatísticas e filtro de 15km
│   └── setup.py         # Slash command /setup, Modal e Select Menu UI
├── static/
│   └── style.css        # Folha de estilos premium (tema escuro com azul neon, responsivo e glassmorphism)
├── templates/
│   ├── base.html        # Layout base com menu de navegação vertical
│   ├── login.html       # Tela de login estilizada
│   ├── register.html    # Tela de registo com dropdown de servidores configurados
│   ├── jobs.html        # Grid interativo de vagas com descrição expandível
│   └── stats.html       # Página de estatísticas e gráficos interativos (Chart.js)
├── .env                 # Arquivo privado contendo o token do bot (não commitar)
├── .gitignore           # Lista de arquivos ignorados pelo Git
├── database.py          # Gerenciamento assíncrono do SQLite (aiosqlite) e hashing de passwords
├── limpar_db.bat        # Script executável para redefinir o banco de dados
├── main.py              # Ponto de entrada do Bot (inicializa o bot e o servidor web em background)
├── web_server.py        # Servidor Flask assíncrono integrado com rotas e envio de alertas no Discord
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
*   `search_engines` (TEXT) — Sites monitorados (ex: `"linkedin,indeed,google"`).
*   `status` (TEXT) — Status do monitoramento (`'ON'` ou `'OFF'`).
*   `daily_channel_id` (INTEGER) — Canal de texto escolhido para resumos diários (configurado via `/canaldiario`).

### 2. Tabela `sent_jobs`
Registra as chaves únicas das vagas já notificadas por servidor:
*   `guild_id` (INTEGER) — ID do servidor correspondente.
*   `job_id` (TEXT) — Identificador único da vaga.
*   *Chave Primária Composta:* `(guild_id, job_id)`.

### 3. Tabela `engine_last_run`
Armazena o timestamp de última execução por servidor, cidade e motor para fins de rate limit:
*   `guild_id` (INTEGER) — ID do servidor.
*   `city` (TEXT) — Nome da cidade.
*   `engine` (TEXT) — Motor de busca (ex: `"google"`).
*   `last_run_timestamp` (REAL) — Unix timestamp do último ciclo executado.
*   *Chave Primária Composta:* `(guild_id, city, engine)`.

### 4. Tabela `api_usage_counts`
Controle cumulativo de consumo das APIs do Google Jobs:
*   `provider` (TEXT PRIMARY KEY) — Nome do provedor da API (`"SerpApi"`, `"JSearch"`, `"SearchApi"`).
*   `count` (INTEGER) — Quantidade acumulada de requisições enviadas ao provedor.

### 5. Tabela `users`
Utilizadores autorizados a aceder ao Painel Web:
*   `username` (TEXT PRIMARY KEY) — Nome de utilizador limpo (em minúsculas).
*   `password_hash` (TEXT) — Hash seguro gerado via PBKDF2-SHA256 (com salt aleatório).
*   `guild_id` (INTEGER) — ID do servidor Discord associado ao utilizador para visualização de vagas.

### 6. Tabela `jobs`
Armazena os detalhes completos de todas as vagas coletadas para exibição no painel:
*   `id` (TEXT PRIMARY KEY) — Identificador único da vaga.
*   `guild_id` (INTEGER) — Servidor que recolheu a vaga.
*   `title` (TEXT) — Título da vaga.
*   `company` (TEXT) — Nome da empresa.
*   `job_url` (TEXT) — Link direto para candidatura.
*   `location` (TEXT) — Localização da vaga.
*   `site` (TEXT) — Fonte/Plataforma de busca.
*   `description` (TEXT) — Descrição completa da oportunidade.
*   `timestamp` (REAL) — Timestamp de inserção.

### 7. Tabela `user_job_status`
Rastreamento do estado das candidaturas por utilizador:
*   `username` (TEXT) — Utilizador do painel.
*   `job_id` (TEXT) — Identificador da vaga.
*   `status` (TEXT) — Estado da vaga (`'submetida'`, `'descartada'`, `'positiva'` ou `'negativa'`).
*   `timestamp` (REAL) — Timestamp da última atualização do estado da vaga.
*   *Chave Primária Composta:* `(username, job_id)`.


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

    # Opcionais - Para ativar buscas confiáveis no Google Jobs (recomendado)
    RAPIDAPI_KEY=SUA_CHAVE_JSEARCH_RAPIDAPI_AQUI
    # OU
    SERPAPI_API_KEY=SUA_CHAVE_SERPAPI_AQUI
    # OU
    SEARCHAPI_API_KEY=SUA_CHAVE_SEARCHAPI_AQUI
    ```
    > 💡 **Nota:** Se você deseja monitorar vagas do **Google Jobs**, recomendamos obter uma chave gratuita no **RapidAPI (JSearch API)** que disponibiliza 200 requisições gratuitas por mês, no **SerpApi** (100 buscas grátis/mês) ou no **SearchApi.io** (100 buscas grátis). O bot deteta automaticamente se a chave que introduziu no `RAPIDAPI_KEY` começa por `ak_` e redireciona-a para o SearchApi.io automaticamente. Caso nenhuma chave seja fornecida, a busca no Google Jobs será ignorada para evitar que o bot falhe, mantendo os outros motores ativos.

4.  **Iniciar o Bot:**
    ```bash
    python main.py
    ```

---

## 🤖 Comandos Disponíveis

> ⚠️ **Nota:** Todos os comandos abaixo são exclusivos para usuários que possuem a permissão de **Administrador** no servidor.

*   `/setup <canal_de_texto>`: Inicia a configuração guiada do bot por perguntas interativas.
    1. Solicita que o utilizador digite as cidades a monitorizar diretamente no chat do canal (separadas por vírgula, ex: `Lisboa, Porto`). O bot lê o conteúdo e apaga a mensagem de seguida para manter o canal limpo.
    2. Pergunta sequencialmente se deseja monitorizar cada uma das plataformas de busca (LinkedIn, Indeed, Glassdoor, ZipRecruiter, Google Jobs) através de botões efémeros interativos (**Sim ✅** / **Não ❌**).
    3. Salva a configuração no banco de dados e ativa a rotina automática (`status = 'ON'`).
*   `/canaldiario <canal_de_texto>`: Configura o canal de texto onde o resumo diário consolidado das últimas 24 horas será enviado automaticamente todos os dias às **00:00** (contendo vagas encontradas, descartadas, submetidas e sucessos positivos).
*   `/varrer`: Força uma varredura imediata de novas vagas de emprego para o servidor utilizando as configurações atuais, sem esperar pelo ciclo de 1 hora (injetando temporariamente o Google Jobs para garantir cobertura completa).
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

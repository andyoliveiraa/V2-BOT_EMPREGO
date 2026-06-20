from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
import asyncio
import threading
import os
import sys
import logging
import queue
from datetime import datetime, timezone
from functools import partial
import discord
import database

# Configurar Logging para o servidor web
logger = logging.getLogger("project_emprego.web")

class LogCaptureHandler(logging.Handler):
    """Handler customizado do logging para capturar mensagens e colocá-las em fila thread-safe."""
    def __init__(self):
        super().__init__()
        self.log_queue = queue.Queue()
        self.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))

    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.log_queue.put(log_entry)
        except Exception:
            pass

app = Flask(__name__)
app.secret_key = os.urandom(24) # Chave para gerir sessões de forma segura

@app.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)

def dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(app.static_folder, filename)
            if os.path.exists(file_path):
                values['v'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)

# Variável global para armazenar a instância do bot Discord
bot = None

def run_flask():
    """Inicia o servidor Flask na porta 8023 (ou configurada via WEB_PORT)."""
    port = int(os.getenv("WEB_PORT", 8023))
    logger.info(f"Iniciando servidor Flask na porta {port}...")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def start_web_server(bot_instance):
    """Inicializa o servidor web em uma thread de background vinculada ao bot."""
    global bot
    bot = bot_instance
    thread = threading.Thread(target=run_flask, daemon=True)
    thread.start()
    logger.info("Thread do servidor Flask iniciada com sucesso.")

@app.route('/login', methods=['GET', 'POST'])
async def login():
    if 'username' in session:
        return redirect(url_for('dashboard'))
        
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_data = await database.authenticate_user(username, password)
        if user_data:
            session['username'] = user_data['username']
            session['guild_id'] = user_data['guild_id']
            return redirect(url_for('dashboard'))
        else:
            error = "Utilizador ou palavra-passe incorretos."
            
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
async def register():
    if 'username' in session:
        return redirect(url_for('dashboard'))
        
    error = None
    success = None
    
    # Obter os servidores configurados para o dropdown
    guilds = await database.get_configured_guilds()
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        guild_id_str = request.form.get('guild_id')
        
        if not username or not password or not guild_id_str:
            error = "Por favor, preencha todos os campos."
        else:
            try:
                guild_id = int(guild_id_str)
                created = await database.create_user(username, password, guild_id)
                if created:
                    success = "Utilizador registado com sucesso! Efetue login."
                else:
                    error = "O utilizador já existe."
            except ValueError:
                error = "Servidor inválido selecionado."
                
    return render_template('register.html', guilds=guilds, error=error, success=success)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
async def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session['username']
    guild_id = session['guild_id']
    
    # Vagas Disponíveis (sem status específico)
    jobs = await database.get_jobs_by_status(username, guild_id, 'disponivel')
    return render_template('jobs.html', jobs=jobs, current_page='disponiveis', username=username, guild_id=guild_id)

@app.route('/submetidas')
async def submetidas():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session['username']
    guild_id = session['guild_id']
    
    jobs = await database.get_jobs_by_status(username, guild_id, 'submetida')
    return render_template('jobs.html', jobs=jobs, current_page='submetidas', username=username, guild_id=guild_id)

@app.route('/positivas')
async def positivas():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session['username']
    guild_id = session['guild_id']
    
    jobs = await database.get_jobs_by_status(username, guild_id, 'positiva')
    return render_template('jobs.html', jobs=jobs, current_page='positivas', username=username, guild_id=guild_id)

@app.route('/negativas')
async def negativas():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session['username']
    guild_id = session['guild_id']
    
    jobs = await database.get_jobs_by_status(username, guild_id, 'negativa')
    return render_template('jobs.html', jobs=jobs, current_page='negativas', username=username, guild_id=guild_id)

@app.route('/descartadas')
async def descartadas():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session['username']
    guild_id = session['guild_id']
    
    jobs = await database.get_jobs_by_status(username, guild_id, 'descartada')
    return render_template('jobs.html', jobs=jobs, current_page='descartadas', username=username, guild_id=guild_id)

@app.route('/estatisticas')
async def estatisticas():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session['username']
    guild_id = session['guild_id']
    
    # Obter dados estatísticos
    summary = await database.get_job_stats_summary(username, guild_id)
    sources = await database.get_jobs_by_source_stats(guild_id)
    over_time = await database.get_jobs_over_time_stats(guild_id)
    locations = await database.get_jobs_by_location_stats(guild_id)
    
    return render_template(
        'stats.html',
        summary=summary,
        sources=sources,
        over_time=over_time,
        locations=locations,
        current_page='estatisticas',
        username=username,
        guild_id=guild_id
    )

@app.route('/update-status', methods=['POST'])
async def update_status():
    if 'username' not in session:
        return jsonify({"success": False, "error": "Não autenticado"}), 401
        
    data = request.json or {}
    job_id = data.get('job_id')
    status = data.get('status') # 'submetida', 'descartada', 'disponivel', 'positiva', or 'negativa'
    
    if not job_id or status not in ['submetida', 'descartada', 'disponivel', 'positiva', 'negativa']:
        return jsonify({"success": False, "error": "Parâmetros inválidos"}), 400
        
    username = session['username']
    guild_id = session['guild_id']
    
    try:
        # 1. Obter o título e fonte da vaga para a notificação do Discord ANTES de alterar
        job_title = "Vaga Desconhecida"
        site_source = "Desconhecida"
        async with database.aiosqlite.connect(database.DB_FILE) as db:
            db.row_factory = database.aiosqlite.Row
            async with db.execute("SELECT title, site FROM jobs WHERE id = ?", (job_id,)) as cursor:
                job_row = await cursor.fetchone()
                if job_row:
                    job_title = job_row["title"]
                    site_source = job_row["site"]
 
        # 2. Atualizar o status do utilizador no BD
        await database.update_user_job_status(username, job_id, status)
        
        # 3. Notificar no canal do Discord configurado do servidor
        if bot:
            guild_cfg = await database.get_guild_config(guild_id)
            if guild_cfg:
                channel_id = guild_cfg["channel_id"]
                
                async def notify_discord():
                    channel = bot.get_channel(channel_id)
                    if not channel:
                        try:
                            channel = await bot.fetch_channel(channel_id)
                        except Exception:
                            pass
                    if channel:
                        # Mapeamento de cores
                        if status == 'submetida':
                            color = 0x3498db # azul
                        elif status == 'descartada':
                            color = 0xe74c3c # vermelho
                        elif status == 'disponivel':
                            color = 0x2ec7a2 # verde esmeralda
                        elif status == 'positiva':
                            color = 0x2ecc71 # verde brilhante (sucesso)
                        else:
                            color = 0x95a5a6 # cinza (negativa)

                        # Mapeamento de status label
                        if status == 'submetida':
                            status_label = "Submetida"
                        elif status == 'descartada':
                            status_label = "Descartada"
                        elif status == 'disponivel':
                            status_label = "Disponível"
                        elif status == 'positiva':
                            status_label = "Resposta Positiva 🎉"
                        else:
                            status_label = "Resposta Negativa 📉"

                        # Mapeamento de emoji
                        if status == 'submetida':
                            emoji = "✅"
                        elif status == 'descartada':
                            emoji = "❌"
                        elif status == 'disponivel':
                            emoji = "🔄"
                        elif status == 'positiva':
                            emoji = "🎉"
                        else:
                            emoji = "📉"
                        
                        embed = discord.Embed(
                            title=f"{emoji} Status de Vaga Atualizado no Painel",
                            color=color,
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.add_field(name="💼 Vaga", value=job_title, inline=False)
                        embed.add_field(name="🏢 Fonte", value=site_source, inline=True)
                        embed.add_field(name="👤 Utilizador", value=username, inline=True)
                        embed.add_field(name="🏷️ Novo Estado", value=f"**{status_label}**", inline=True)
                        embed.set_footer(text="Project-Emprego • Painel Web")
                        await channel.send(embed=embed)
                        
                asyncio.run_coroutine_threadsafe(notify_discord(), bot.loop)
                
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Erro ao atualizar status da vaga: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/run-sweep')
def run_sweep():
    if 'username' not in session:
        return jsonify({"success": False, "error": "Não autenticado"}), 401
        
    guild_id = session['guild_id']
    
    if not bot:
        return jsonify({"success": False, "error": "Bot Discord não inicializado"}), 500
        
    def event_stream():
        def run_async(coro):
            future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
            return future.result()

        try:
            guild_cfg = run_async(database.get_guild_config(guild_id))
        except Exception as e:
            yield f"data: [ERRO] Falha ao ler base de dados: {str(e)}\n\n"
            return

        if not guild_cfg:
            yield f"data: [ERRO] Servidor Discord {guild_id} não configurado no bot.\n\n"
            return

        channel_id = guild_cfg["channel_id"]
        
        async def fetch_channel_obj():
            channel = bot.get_channel(channel_id)
            if not channel:
                try:
                    channel = await bot.fetch_channel(channel_id)
                except Exception:
                    pass
            return channel

        try:
            channel = run_async(fetch_channel_obj())
        except Exception as e:
            yield f"data: [ERRO] Falha ao obter canal Discord: {str(e)}\n\n"
            return

        if not channel:
            yield f"data: [ERRO] Canal de alertas {channel_id} não encontrado no Discord.\n\n"
            return

        # Interceptação de logs
        monitor_logger = logging.getLogger("project_emprego.monitor")
        jsearch_logger = logging.getLogger("project_emprego.monitor.jsearch")
        serp_logger = logging.getLogger("project_emprego.monitor.serpapi")
        searchapi_logger = logging.getLogger("project_emprego.monitor.searchapi")
        
        handler = LogCaptureHandler()
        monitor_logger.addHandler(handler)
        jsearch_logger.addHandler(handler)
        serp_logger.addHandler(handler)
        searchapi_logger.addHandler(handler)

        monitor_cog = bot.get_cog("MonitorCog")
        if not monitor_cog:
            yield "data: [ERRO] Extensão do bot 'MonitorCog' não carregada.\n\n"
            monitor_logger.removeHandler(handler)
            jsearch_logger.removeHandler(handler)
            serp_logger.removeHandler(handler)
            searchapi_logger.removeHandler(handler)
            return

        yield "data: [SISTEMA] Conectado! Disparando monitor de busca...\n\n"
        
        scrape_future = asyncio.run_coroutine_threadsafe(
            monitor_cog.run_scraping_for_guild(guild_cfg, channel, is_forced=True),
            bot.loop
        )

        import time
        while not scrape_future.done() or not handler.log_queue.empty():
            try:
                log_line = handler.log_queue.get(timeout=0.2)
                log_line_clean = log_line.replace('\r', '').replace('\n', ' ')
                yield f"data: {log_line_clean}\n\n"
            except queue.Empty:
                time.sleep(0.05)

        monitor_logger.removeHandler(handler)
        jsearch_logger.removeHandler(handler)
        serp_logger.removeHandler(handler)
        searchapi_logger.removeHandler(handler)

        try:
            total_jobs = scrape_future.result()
            yield f"data: [SUCESSO] Varredura concluída com sucesso! Total de novas vagas enviadas: {total_jobs}\n\n"
        except Exception as e:
            yield f"data: [FALHA] Erro durante a varredura: {str(e)}\n\n"

    return Response(event_stream(), mimetype='text/event-stream')

@app.route('/api/debug-status')
def debug_status():
    import subprocess
    status_info = {}
    
    # 1. File stats for static/style.css
    css_path = os.path.join(app.static_folder, 'style.css')
    if os.path.exists(css_path):
        status_info['css_file'] = {
            'exists': True,
            'size': os.path.getsize(css_path),
            'mtime': datetime.fromtimestamp(os.path.getmtime(css_path)).isoformat()
        }
    else:
        status_info['css_file'] = {'exists': False}
        
    # 2. Git status and log
    try:
        git_status = subprocess.check_output(['git', 'status'], stderr=subprocess.STDOUT, text=True)
        git_log = subprocess.check_output(['git', 'log', '-n', '5', '--oneline'], stderr=subprocess.STDOUT, text=True)
        status_info['git'] = {
            'status': git_status,
            'log': git_log
        }
    except Exception as e:
        status_info['git'] = {'error': str(e)}
        
    return jsonify(status_info)


# ==========================================================================
# NOVOS ENDPOINTS - DETALHES DE VAGA, DEFINIÇÕES & INTELIGÊNCIA ARTIFICIAL
# ==========================================================================

@app.route('/vaga/<path:job_id>')
async def vaga_detail(job_id):
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session['username']
    guild_id = session['guild_id']
    
    job = await database.get_job_by_id(job_id)
    if not job:
        return "Vaga não encontrada", 404
        
    settings = await database.get_user_settings(username)
    return render_template(
        'job_detail.html', 
        job=job, 
        settings=settings, 
        current_page='disponiveis', 
        username=username, 
        guild_id=guild_id
    )


@app.route('/definicoes', methods=['GET', 'POST'])
async def definicoes():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    username = session['username']
    guild_id = session['guild_id']
    
    if request.method == 'POST':
        cv_text = request.form.get('cv_text', '')
        system_prompt = request.form.get('system_prompt', '')
        ai_provider = request.form.get('ai_provider', 'gemini')
        gemini_key = request.form.get('gemini_key', '')
        openai_key = request.form.get('openai_key', '')
        groq_key = request.form.get('groq_key', '')
        together_key = request.form.get('together_key', '')
        cover_prompt = request.form.get('cover_prompt', '')
        
        await database.save_user_settings(
            username, cv_text, system_prompt, ai_provider,
            gemini_key, openai_key, groq_key, together_key, cover_prompt
        )
        return redirect(url_for('definicoes', saved=1))
        
    settings = await database.get_user_settings(username)
    if not settings:
        settings = {
            "username": username,
            "cv_text": "",
            "system_prompt": "",
            "ai_provider": "gemini",
            "gemini_key": "",
            "openai_key": "",
            "groq_key": "",
            "together_key": "",
            "cover_prompt": ""
        }
        
    # Obter contagem de chamadas realizadas a cada provedor de IA
    usage = {
        "gemini": await database.get_api_usage('llm_gemini'),
        "openai": await database.get_api_usage('llm_openai'),
        "groq": await database.get_api_usage('llm_groq'),
        "together": await database.get_api_usage('llm_together')
    }
    
    return render_template(
        'settings.html', 
        settings=settings, 
        usage=usage,
        current_page='definicoes', 
        username=username, 
        guild_id=guild_id
    )


def call_llm(provider, api_key, system_prompt, user_prompt):
    import urllib.request
    import urllib.error
    import json
    
    if not api_key:
        raise Exception(f"Chave de API para o provedor '{provider}' não configurada nas definições.")
        
    provider = provider.lower()
    
    if provider == 'openai':
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7
        }
    elif provider == 'gemini':
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": 0.7
            }
        }
    elif provider == 'groq':
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7
        }
    elif provider == 'together':
        url = "https://api.together.xyz/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "meta-llama/Meta-Llama-3-8B-Instruct-Turbo",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7
        }
    else:
        raise Exception(f"Provedor de IA desconhecido: {provider}")

    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    req_data = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            
            if provider == 'gemini':
                text = res_json['candidates'][0]['content']['parts'][0]['text']
                return text
            else:
                return res_json['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        logger.error(f"Erro HTTP chamando LLM ({provider}): {err_body}")
        try:
            err_json = json.loads(err_body)
            error_msg = err_json.get("error", {}).get("message", err_body)
        except Exception:
            error_msg = err_body
        raise Exception(f"Erro na API {provider.upper()}: {error_msg}")
    except Exception as e:
        logger.error(f"Exceção ao chamar LLM ({provider}): {e}")
        raise e


def make_ai_generator(job_id, username, mode):
    import json
    import re
    import time
    
    def run_async(coro):
        future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
        return future.result()
        
    try:
        job = run_async(database.get_job_by_id(job_id))
        if not job:
            yield "data: [ERRO] Vaga não encontrada.\n\n"
            return
            
        settings = run_async(database.get_user_settings(username))
        if not settings or not settings.get('cv_text'):
            yield "data: [ERRO] Currículo base em falta. Aceda às Definições para o configurar.\n\n"
            return
            
        provider = settings.get('ai_provider', 'gemini')
        key_map = {
            'gemini': settings.get('gemini_key'),
            'openai': settings.get('openai_key'),
            'groq': settings.get('groq_key'),
            'together': settings.get('together_key')
        }
        api_key = key_map.get(provider)
        if not api_key:
            yield f"data: [ERRO] Chave de API para o provedor {provider.upper()} não configurada.\n\n"
            return
            
        user_instructions = settings.get('system_prompt', '')
        
        # Configuração de prompts
        if mode == 'cover-letter':
            cover_prompt_template = settings.get('cover_prompt', '')
            if not cover_prompt_template or not cover_prompt_template.strip():
                # Prompt padrão caso esteja vazio
                cover_prompt_template = """Você é um especialista em atração de talentos e escrita criativa de cartas de apresentação.
Escreva uma Carta de Motivação personalizada, profissional e altamente cativante para a empresa {empresa} para a vaga de {titulo_vaga} ({localizacao}).

Regras importantes:
- Escreva de forma extremamente natural e humana. Evite clichês de inteligência artificial (como "Escrevo para expressar meu forte interesse", "Com grande entusiasmo", "Altamente qualificado", "Vasta experiência", etc.).
- Use estruturas de frases variadas (frases curtas misturadas com médias e longas).
- Evite parágrafos muito longos ou linguagem corporativa robótica.
- Foque em demonstrar afinidade com os requisitos da vaga através das competências e experiências citadas no meu currículo.

Descrição da Vaga:
{descricao_vaga}

Meu Currículo Base:
{cv_text}"""

            system_prompt = "Você é um especialista em atração de talentos e escrita criativa de cartas de apresentação humana e natural."
            if user_instructions:
                system_prompt += f"\nInstruções personalizadas adicionais do utilizador:\n{user_instructions}"
                
            try:
                user_prompt = cover_prompt_template.format(
                    empresa=job['company'],
                    titulo_vaga=job['title'],
                    localizacao=job['location'],
                    descricao_vaga=job['description'],
                    cv_text=settings['cv_text']
                )
            except Exception as fe:
                yield f"data: [AVISO] Falha ao formatar o prompt customizado da carta: {str(fe)}. Usando prompt padrão...\n\n"
                user_prompt = f"""Você é um especialista em atração de talentos e escrita criativa de cartas de apresentação.
Escreva uma Carta de Motivação personalizada para a empresa {job['company']} para a vaga {job['title']} em {job['location']}.
Descrição:
{job['description']}

Currículo Base:
{settings['cv_text']}"""

        else: # adapt-cv
            system_prompt = """Você é um especialista em otimização de currículos para sistemas ATS (Applicant Tracking Systems) e recrutamento.
A sua tarefa é adaptar o currículo de base do candidato para se alinhar da melhor forma possível com a vaga fornecida.
Regras fundamentais:
- NÃO invente dados falsos (como empresas que não trabalhou, formação acadêmica que não possui ou anos de experiência incorretos).
- Adapte a linguagem do resumo profissional, das realizações profissionais e das competências para focar nos requisitos e palavras-chave descritos na vaga.
- Escreva de forma natural, humana e direta. Evite clichês robóticos e introduções vazias.
- Retorne o currículo adaptado por completo estruturado em formato de texto plano limpo e legível."""
            if user_instructions:
                system_prompt += f"\nInstruções personalizadas adicionais do utilizador:\n{user_instructions}"
                
            user_prompt = f"""Vaga de Emprego:
Título: {job['title']}
Empresa: {job['company']}
Localização: {job['location']}
Descrição:
{job['description']}

Currículo Base do Candidato:
{settings['cv_text']}

Por favor, adapte o currículo base para esta vaga específica."""

        # Avaliador Setup
        evaluator_system_prompt = """Você é um avaliador neutro e especialista em recrutamento, Sistemas ATS e análise de autoria (IA vs Humano).
Analise o documento fornecido em relação à vaga e atribua dois scores numéricos:
1. HUMAN_SCORE: Classificação de 0 a 100 de quão humano, autêntico, fluido e natural soa o texto (penalize repetições, clichês de IA e tom robótico).
2. ATS_SCORE: Classificação de 0 a 100 de quão alinhado o texto está com os requisitos e palavras-chave da vaga de emprego.

No final de sua resposta, você DEVE retornar obrigatoriamente estes marcadores no formato exato:
HUMAN_SCORE: <número de 0 a 100>
ATS_SCORE: <número de 0 a 100>
CRÍTICA: <seu feedback e orientações claras sobre como reescrever o texto para torná-lo mais natural, humano e menos robótico>"""

        current_draft = ""
        score = 0
        max_attempts = 5
        
        for attempt in range(1, max_attempts + 1):
            yield f"data: [INFO] Tentativa {attempt}/{max_attempts}: A enviar pedido de geração para o motor {provider.upper()}...\n\n"
            
            # Incrementar contador de chamadas da IA
            run_async(database.increment_api_usage('llm_' + provider))
            
            if attempt == 1:
                current_draft = call_llm(provider, api_key, system_prompt, user_prompt)
            else:
                rewrite_system = """Você é um especialista em escrita criativa e otimização de currículos/cartas de motivação.
O seu objetivo é reescrever o documento para parecer 100% humano (passar no detector de escrita de IA com score superior a 90%) e estar bem alinhado com a vaga.
Siga as críticas e recomendações do avaliador para reescrever o texto, removendo expressões robóticas, frases prontas de IA e variando o vocabulário."""
                
                rewrite_user = f"""Vaga de Emprego:
Título: {job['title']}
Empresa: {job['company']}
Descrição: {job['description']}

Currículo Base do Candidato:
{settings['cv_text']}

Versão Anterior a Otimizar:
{current_draft}

Crítica do Avaliador:
{critique}

Reescreva o documento completo seguindo a crítica do avaliador para torná-lo autêntico, humano e natural."""
                
                current_draft = call_llm(provider, api_key, rewrite_system, rewrite_user)
                
            yield f"data: [INFO] Tentativa {attempt}/{max_attempts}: A analisar qualidade humana e ATS...\n\n"
            
            # Incrementar contador de chamadas da IA para a avaliação
            run_async(database.increment_api_usage('llm_' + provider))
            
            evaluator_user_prompt = f"""Vaga:
Título: {job['title']}
Empresa: {job['company']}
Descrição: {job['description']}

Documento Gerado a Avaliar:
{current_draft}

Avalie o documento conforme as regras."""
            
            evaluation = call_llm(provider, api_key, evaluator_system_prompt, evaluator_user_prompt)
            
            human_match = re.search(r"HUMAN_SCORE:\s*(\d+)", evaluation)
            ats_match = re.search(r"ATS_SCORE:\s*(\d+)", evaluation)
            critique_match = re.search(r"CRÍTICA:\s*(.*)", evaluation, re.DOTALL)
            
            human_score = int(human_match.group(1)) if human_match else 75
            ats_score = int(ats_match.group(1)) if ats_match else 70
            critique = critique_match.group(1).strip() if critique_match else "Torne as frases mais simples, curtas e menos formais."
            
            yield f"data: [AVALIAÇÃO] Tentativa {attempt}: Escrita Humana = {human_score}% | ATS Match = {ats_score}%\n\n"
            
            score = human_score
            if score >= 90:
                yield f"data: [OK] Geração bem-sucedida! Score de escrita humana de {score}% é superior a 90%.\n\n"
                break
            elif attempt < max_attempts:
                short_critique = critique.split('\n')[0][:120] + ("..." if len(critique) > 120 else "")
                yield f"data: [AVALIAÇÃO] Crítica do Avaliador: \"{short_critique}\"\n\n"
                yield f"data: [INFO] Score de escrita humana ({score}%) abaixo de 90%. Iniciando novo ciclo de refinamento...\n\n"
            else:
                yield f"data: [INFO] Atingido o limite de 5 tentativas. Utilizando o melhor rascunho obtido com score {score}%.\n\n"

        # Enviar resultado final
        result_payload = {
            "content": current_draft,
            "score": score
        }
        yield f"event: result\ndata: {json.dumps(result_payload)}\n\n"
        
    except Exception as e:
        yield f"data: [ERRO] Falha no processo de IA: {str(e)}\n\n"


@app.route('/api/generate-cover-letter')
def generate_cover_letter():
    if 'username' not in session:
        return "Não autenticado", 401
    job_id = request.args.get('job_id')
    username = session['username']
    if not job_id:
        return "job_id em falta", 400
    return Response(make_ai_generator(job_id, username, 'cover-letter'), mimetype='text/event-stream')


@app.route('/api/adapt-resume')
def adapt_resume():
    if 'username' not in session:
        return "Não autenticado", 401
    job_id = request.args.get('job_id')
    username = session['username']
    if not job_id:
        return "job_id em falta", 400
    return Response(make_ai_generator(job_id, username, 'adapt-cv'), mimetype='text/event-stream')

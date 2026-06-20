from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import asyncio
import threading
import os
import sys
import logging
from datetime import datetime, timezone
from functools import partial
import discord
import database

# Configurar Logging para o servidor web
logger = logging.getLogger("project_emprego.web")

app = Flask(__name__)
app.secret_key = os.urandom(24) # Chave para gerir sessões de forma segura

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
    status = data.get('status') # 'submetida', 'descartada', or 'disponivel'
    
    if not job_id or status not in ['submetida', 'descartada', 'disponivel']:
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
                        # Destaques azuis para submetida, vermelhos para descartada, verde esmeralda para disponível
                        color = 0x3498db if status == 'submetida' else (0xe74c3c if status == 'descartada' else 0x2ec7a2)
                        status_label = "Submetida" if status == 'submetida' else ("Descartada" if status == 'descartada' else "Disponível")
                        emoji = "✅" if status == 'submetida' else ("❌" if status == 'descartada' else "🔄")
                        
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

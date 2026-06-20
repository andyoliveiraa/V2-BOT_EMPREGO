import aiosqlite
import logging

logger = logging.getLogger("project_emprego.database")

DB_FILE = "antigravity.db"

async def init_db():
    """Inicializa as tabelas do banco de dados SQLite de forma assíncrona."""
    async with aiosqlite.connect(DB_FILE) as db:
        # Tabela de configurações dos servidores
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_configs (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL,
                cities TEXT NOT NULL,
                search_engines TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ON'
            )
        """)
        
        # Tabela de controle de vagas enviadas
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sent_jobs (
                guild_id INTEGER,
                job_id TEXT,
                PRIMARY KEY (guild_id, job_id)
            )
        """)

        # Tabela de controle de última execução por motor/cidade para rate limit
        await db.execute("""
            CREATE TABLE IF NOT EXISTS engine_last_run (
                guild_id INTEGER,
                city TEXT,
                engine TEXT,
                last_run_timestamp REAL,
                PRIMARY KEY (guild_id, city, engine)
            )
        """)

        # Tabela de controle de contagem de uso de APIs
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_usage_counts (
                provider TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """)

        # Tabela de utilizadores do painel web
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                guild_id INTEGER NOT NULL
            )
        """)

        # Tabela de vagas de emprego completas
        await db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                job_url TEXT NOT NULL,
                location TEXT NOT NULL,
                site TEXT NOT NULL,
                description TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)

        # Tabela de estado das vagas por utilizador (submetida ou descartada)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_job_status (
                username TEXT NOT NULL,
                job_id TEXT NOT NULL,
                status TEXT NOT NULL, -- 'submetida' ou 'descartada'
                PRIMARY KEY (username, job_id)
            )
        """)
        
        # Tabela de definições do utilizador (currículo e chaves de IA)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                username TEXT PRIMARY KEY,
                cv_text TEXT,
                system_prompt TEXT,
                ai_provider TEXT,
                gemini_key TEXT,
                openai_key TEXT,
                groq_key TEXT,
                together_key TEXT,
                cover_prompt TEXT,
                FOREIGN KEY (username) REFERENCES users(username)
            )
        """)
        
        # Migração: Adicionar daily_channel_id à tabela guild_configs
        try:
            await db.execute("ALTER TABLE guild_configs ADD COLUMN daily_channel_id INTEGER DEFAULT 0")
            await db.commit()
            logger.info("Migração: Coluna daily_channel_id adicionada com sucesso.")
        except aiosqlite.OperationalError:
            pass

        # Migração: Adicionar timestamp à tabela user_job_status
        try:
            await db.execute("ALTER TABLE user_job_status ADD COLUMN timestamp REAL")
            await db.commit()
            logger.info("Migração: Coluna timestamp adicionada a user_job_status com sucesso.")
        except aiosqlite.OperationalError:
            pass

        # Migração: Adicionar cover_prompt à tabela user_settings
        try:
            await db.execute("ALTER TABLE user_settings ADD COLUMN cover_prompt TEXT")
            await db.commit()
            logger.info("Migração: Coluna cover_prompt adicionada a user_settings com sucesso.")
        except aiosqlite.OperationalError:
            pass

        await db.commit()
    logger.info("Banco de dados inicializado com sucesso.")

def hash_password(password: str) -> str:
    """Gera o hash PBKDF2-SHA256 para a password com salt aleatório."""
    import hashlib
    import os
    salt = os.urandom(16)
    pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ":" + pw_hash.hex()

def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica se a password fornecida corresponde ao hash armazenado."""
    import hashlib
    try:
        salt_hex, hash_hex = stored_hash.split(":")
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
        pw_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        return pw_hash == expected_hash
    except Exception:
        return False

async def save_guild_config(guild_id: int, channel_id: int, cities: str, search_engines: str, status: str = 'ON'):
    """Salva ou atualiza as configurações de um servidor."""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT INTO guild_configs (guild_id, channel_id, cities, search_engines, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                channel_id = excluded.channel_id,
                cities = excluded.cities,
                search_engines = excluded.search_engines,
                status = excluded.status
        """, (guild_id, channel_id, cities, search_engines, status))
        await db.commit()
    logger.info(f"Configuração salva para o servidor {guild_id}.")

async def get_guild_config(guild_id: int) -> dict:
    """Busca as configurações de um servidor específico."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT guild_id, channel_id, cities, search_engines, status, daily_channel_id FROM guild_configs WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

async def get_active_guild_configs() -> list:
    """Retorna a lista de configurações de todos os servidores com status 'ON'."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT guild_id, channel_id, cities, search_engines, status, daily_channel_id FROM guild_configs WHERE status = 'ON'"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def set_guild_status(guild_id: int, status: str):
    """Atualiza o status da rotina ('ON' ou 'OFF') de um servidor."""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE guild_configs SET status = ? WHERE guild_id = ?",
            (status, guild_id)
        )
        await db.commit()
    logger.info(f"Status do servidor {guild_id} alterado para {status}.")

async def get_sent_job_ids(guild_id: int) -> set:
    """Busca o conjunto de IDs de vagas já enviadas para um determinado servidor."""
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT job_id FROM sent_jobs WHERE guild_id = ?",
            (guild_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

async def add_sent_jobs(guild_id: int, job_ids: list):
    """Registra uma lista de IDs de vagas enviadas para evitar reenvio no servidor."""
    if not job_ids:
        return
    async with aiosqlite.connect(DB_FILE) as db:
        await db.executemany(
            "INSERT OR IGNORE INTO sent_jobs (guild_id, job_id) VALUES (?, ?)",
            [(guild_id, job_id) for job_id in job_ids]
        )
        await db.commit()

async def get_engine_last_run(guild_id: int, city: str, engine: str) -> float:
    """Busca o timestamp da última execução de um motor para uma determinada cidade e servidor."""
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT last_run_timestamp FROM engine_last_run WHERE guild_id = ? AND city = ? AND engine = ?",
            (guild_id, city, engine)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return float(row[0])
            return 0.0

async def update_engine_last_run(guild_id: int, city: str, engine: str, timestamp: float):
    """Atualiza o timestamp de última execução para um motor, cidade e servidor."""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT INTO engine_last_run (guild_id, city, engine, last_run_timestamp)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, city, engine) DO UPDATE SET
                last_run_timestamp = excluded.last_run_timestamp
        """, (guild_id, city, engine, timestamp))
        await db.commit()

async def increment_api_usage(provider: str):
    """Incrementa o contador de requisições de um provedor de API."""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT INTO api_usage_counts (provider, count)
            VALUES (?, 1)
            ON CONFLICT(provider) DO UPDATE SET count = count + 1
        """, (provider,))
        await db.commit()

async def get_api_usage(provider: str) -> int:
    """Busca a contagem de uso acumulado de um provedor de API."""
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute(
            "SELECT count FROM api_usage_counts WHERE provider = ?",
            (provider,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return int(row[0])
            return 0

async def save_job(guild_id: int, job_id: str, title: str, company: str, job_url: str, location: str, site: str, description: str):
    """Salva uma vaga no banco de dados para exibição no painel web."""
    import time
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT INTO jobs (id, guild_id, title, company, job_url, location, site, description, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                company = excluded.company,
                job_url = excluded.job_url,
                location = excluded.location,
                site = excluded.site,
                description = excluded.description
        """, (job_id, guild_id, title, company, job_url, location, site, description, time.time()))
        await db.commit()

async def get_configured_guilds() -> list:
    """Retorna a lista de servidores configurados (IDs e cidades) para o registo de utilizadores."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT guild_id, cities FROM guild_configs") as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def create_user(username: str, password: str, guild_id: int) -> bool:
    """Cria um novo utilizador no painel web."""
    username_cleaned = username.strip().lower()
    pw_hash = hash_password(password)
    async with aiosqlite.connect(DB_FILE) as db:
        try:
            await db.execute(
                "INSERT INTO users (username, password_hash, guild_id) VALUES (?, ?, ?)",
                (username_cleaned, pw_hash, guild_id)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False  # Utilizador já existe

async def authenticate_user(username: str, password: str) -> dict | None:
    """Autentica o utilizador e retorna seus dados (username, guild_id) se bem-sucedido."""
    username_cleaned = username.strip().lower()
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT username, password_hash, guild_id FROM users WHERE username = ?",
            (username_cleaned,)
        ) as cursor:
            row = await cursor.fetchone()
            if row and verify_password(password, row["password_hash"]):
                return {"username": row["username"], "guild_id": row["guild_id"]}
            return None

async def get_jobs_by_status(username: str, guild_id: int, status_filter: str) -> list:
    """Busca as vagas do servidor do utilizador, filtrando por estado."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        if status_filter == 'disponivel':
            # Vagas do servidor do utilizador que NÃO possuem entrada na tabela user_job_status
            query = """
                SELECT j.* FROM jobs j
                LEFT JOIN user_job_status ujs ON j.id = ujs.job_id AND ujs.username = ?
                WHERE j.guild_id = ? AND ujs.status IS NULL
                ORDER BY j.timestamp DESC
            """
            params = (username, guild_id)
        else:
            # Vagas do servidor do utilizador com o status correspondente
            query = """
                SELECT j.* FROM jobs j
                JOIN user_job_status ujs ON j.id = ujs.job_id
                WHERE j.guild_id = ? AND ujs.username = ? AND ujs.status = ?
                ORDER BY j.timestamp DESC
            """
            params = (guild_id, username, status_filter)
            
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def update_user_job_status(username: str, job_id: str, status: str | None):
    """Atualiza o estado de uma vaga para o utilizador."""
    import time
    async with aiosqlite.connect(DB_FILE) as db:
        if status is None or status == 'disponivel':
            await db.execute(
                "DELETE FROM user_job_status WHERE username = ? AND job_id = ?",
                (username, job_id)
            )
        else:
            await db.execute("""
                INSERT INTO user_job_status (username, job_id, status, timestamp)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(username, job_id) DO UPDATE SET status = excluded.status, timestamp = excluded.timestamp
            """, (username, job_id, status, time.time()))
        await db.commit()

async def save_daily_channel(guild_id: int, daily_channel_id: int):
    """Salva ou atualiza o canal de resumo diário de um servidor."""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            UPDATE guild_configs
            SET daily_channel_id = ?
            WHERE guild_id = ?
        """, (daily_channel_id, guild_id))
        await db.commit()
    logger.info(f"Canal de resumo diário atualizado para {daily_channel_id} no servidor {guild_id}.")


async def get_job_stats_summary(username: str, guild_id: int) -> dict:
    """Retorna um resumo estatístico das candidaturas e vagas do utilizador/servidor."""
    async with aiosqlite.connect(DB_FILE) as db:
        # Total recebidas
        async with db.execute("SELECT COUNT(*) FROM jobs WHERE guild_id = ?", (guild_id,)) as cursor:
            row = await cursor.fetchone()
            total_recebidas = row[0] if row else 0

        # Total submetidas (aguardando resposta)
        async with db.execute("""
            SELECT COUNT(*) FROM user_job_status ujs
            JOIN jobs j ON ujs.job_id = j.id
            WHERE j.guild_id = ? AND ujs.username = ? AND ujs.status = 'submetida'
        """, (guild_id, username)) as cursor:
            row = await cursor.fetchone()
            total_submetidas = row[0] if row else 0

        # Total positivas (respondida positivamente)
        async with db.execute("""
            SELECT COUNT(*) FROM user_job_status ujs
            JOIN jobs j ON ujs.job_id = j.id
            WHERE j.guild_id = ? AND ujs.username = ? AND ujs.status = 'positiva'
        """, (guild_id, username)) as cursor:
            row = await cursor.fetchone()
            total_positivas = row[0] if row else 0

        # Total negativas (respondida negativamente)
        async with db.execute("""
            SELECT COUNT(*) FROM user_job_status ujs
            JOIN jobs j ON ujs.job_id = j.id
            WHERE j.guild_id = ? AND ujs.username = ? AND ujs.status = 'negativa'
        """, (guild_id, username)) as cursor:
            row = await cursor.fetchone()
            total_negativas = row[0] if row else 0

        # Total descartadas
        async with db.execute("""
            SELECT COUNT(*) FROM user_job_status ujs
            JOIN jobs j ON ujs.job_id = j.id
            WHERE j.guild_id = ? AND ujs.username = ? AND ujs.status = 'descartada'
        """, (guild_id, username)) as cursor:
            row = await cursor.fetchone()
            total_descartadas = row[0] if row else 0

        total_candidaturas = total_submetidas + total_positivas + total_negativas
        total_disponiveis = max(0, total_recebidas - total_candidaturas - total_descartadas)
        
        taxa_conversao = round((total_candidaturas / total_recebidas * 100), 1) if total_recebidas > 0 else 0.0
        taxa_sucesso = round((total_positivas / total_candidaturas * 100), 1) if total_candidaturas > 0 else 0.0

        return {
            "total_recebidas": total_recebidas,
            "total_submetidas": total_submetidas,
            "total_positivas": total_positivas,
            "total_negativas": total_negativas,
            "total_descartadas": total_descartadas,
            "total_disponiveis": total_disponiveis,
            "total_candidaturas": total_candidaturas,
            "taxa_conversao": taxa_conversao,
            "taxa_sucesso": taxa_sucesso
        }

async def get_jobs_by_source_stats(guild_id: int) -> list:
    """Retorna contagem de vagas agrupadas por fonte (site)."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT site as source, COUNT(*) as count
            FROM jobs
            WHERE guild_id = ?
            GROUP BY site
            ORDER BY count DESC
        """, (guild_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_jobs_over_time_stats(guild_id: int) -> list:
    """Retorna a contagem de vagas recebidas agrupadas por dia nos últimos 14 dias."""
    import time
    fourteen_days_ago = time.time() - (14 * 24 * 60 * 60)
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT date(timestamp, 'unixepoch') as day, COUNT(*) as count
            FROM jobs
            WHERE guild_id = ? AND timestamp >= ?
            GROUP BY day
            ORDER BY day ASC
        """, (guild_id, fourteen_days_ago)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def get_jobs_by_location_stats(guild_id: int) -> list:
    """Retorna a contagem de vagas por localização (top 8)."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT location, COUNT(*) as count
            FROM jobs
            WHERE guild_id = ?
            GROUP BY location
            ORDER BY count DESC
            LIMIT 8
        """, (guild_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_job_by_id(job_id: str) -> dict | None:
    """Busca os detalhes de uma vaga específica pelo seu ID."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def get_user_settings(username: str) -> dict | None:
    """Busca as definições de IA do utilizador."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM user_settings WHERE username = ?", (username,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None


async def save_user_settings(username: str, cv_text: str, system_prompt: str, ai_provider: str, gemini_key: str, openai_key: str, groq_key: str, together_key: str, cover_prompt: str):
    """Salva ou atualiza as definições de IA do utilizador."""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT INTO user_settings (username, cv_text, system_prompt, ai_provider, gemini_key, openai_key, groq_key, together_key, cover_prompt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                cv_text = excluded.cv_text,
                system_prompt = excluded.system_prompt,
                ai_provider = excluded.ai_provider,
                gemini_key = excluded.gemini_key,
                openai_key = excluded.openai_key,
                groq_key = excluded.groq_key,
                together_key = excluded.together_key,
                cover_prompt = excluded.cover_prompt
        """, (username, cv_text, system_prompt, ai_provider, gemini_key, openai_key, groq_key, together_key, cover_prompt))
        await db.commit()



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
        await db.commit()
    logger.info("Banco de dados inicializado com sucesso.")

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
            "SELECT guild_id, channel_id, cities, search_engines, status FROM guild_configs WHERE guild_id = ?",
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
            "SELECT guild_id, channel_id, cities, search_engines, status FROM guild_configs WHERE status = 'ON'"
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

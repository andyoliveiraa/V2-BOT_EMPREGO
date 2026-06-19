import discord
from discord.ext import commands
import os
import sys
import logging
import asyncio
from dotenv import load_dotenv
import database

# Configurar Logging para produção
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("project_emprego.main")

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

class ProjectEmpregoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Habilitado para ler o conteúdo da mensagem digitada pelo usuário no setup
        super().__init__(
            command_prefix="!", 
            intents=intents,
            help_command=None
        )
        # Lock e timestamp globais para controle de taxa de requisições do Nominatim (limite de 1 por segundo)
        self.nominatim_lock = asyncio.Lock()
        self.last_nominatim_request_time = 0.0

    async def setup_hook(self):
        # 1. Inicializar o banco de dados SQLite assíncrono
        await database.init_db()

        # 2. Carregar as extensões (Cogs)
        try:
            await self.load_extension("cogs.setup")
            logger.info("Cog 'setup' carregado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao carregar o cog 'setup': {e}")

        try:
            await self.load_extension("cogs.monitor")
            logger.info("Cog 'monitor' carregado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao carregar o cog 'monitor': {e}")

        # 3. Inicializar o servidor web Flask
        try:
            import web_server
            web_server.start_web_server(self)
            logger.info("Servidor web iniciado com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao iniciar o servidor web: {e}")

        # 4. Remover a sincronização daqui para rodar no on_ready
        # pois o application_id só está disponível após o bot logar.

    async def on_ready(self):
        logger.info(f"Bot online! Conectado como {self.user} (ID: {self.user.id})")
        # Definir presença do bot
        activity = discord.Activity(type=discord.ActivityType.watching, name="vagas de emprego")
        await self.change_presence(status=discord.Status.online, activity=activity)

        # Sincronizar os comandos slash globalmente se ainda não foram nesta sessão
        if not hasattr(self, "synced_commands"):
            self.synced_commands = False
            
        if not self.synced_commands:
            logger.info("Sincronizando comandos slash...")
            try:
                synced = await self.tree.sync()
                logger.info(f"Sincronizados {len(synced)} comandos slash com sucesso.")
                self.synced_commands = True
            except Exception as e:
                logger.error(f"Erro ao sincronizar comandos slash: {e}")

def main():
    if not TOKEN or TOKEN == "INSIRA_SEU_TOKEN_AQUI":
        logger.critical("Erro: DISCORD_TOKEN não configurado no arquivo .env!")
        print("\n[ERRO CRÍTICO] Por favor, insira o token do seu bot no arquivo '.env' antes de iniciar.")
        sys.exit(1)

    bot = ProjectEmpregoBot()
    
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        logger.critical("Erro: Token do bot inválido ou expirado!")
        print("\n[ERRO CRÍTICO] Falha no login: O token fornecido no '.env' é inválido.")
    except Exception as e:
        logger.critical(f"Erro inesperado ao iniciar o bot: {e}")

if __name__ == "__main__":
    main()

import discord
from discord import app_commands
from discord.ext import commands, tasks
import database
import logging
import asyncio
from functools import partial
from datetime import datetime, timezone

# Importar o python-jobspy
try:
    from jobspy import scrape_jobs
except ImportError:
    scrape_jobs = None

logger = logging.getLogger("project_emprego.monitor")

# Configuração Padrão do País para o Indeed/Glassdoor.
# Altere para 'brazil', 'usa', etc., dependendo do país de busca padrão.
DEFAULT_COUNTRY = "portugal"

# Termo de busca padrão para vagas de emprego.
# Sendo um bot geral, um termo amplo funciona bem.
DEFAULT_SEARCH_TERM = "vagas"

class MonitorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Iniciar o loop de tarefas quando a cog é carregada
        self.monitor_loop.start()

    def cog_unload(self):
        # Cancelar o loop de tarefas quando a cog é descarregada
        self.monitor_loop.cancel()

    @tasks.loop(minutes=10)
    async def monitor_loop(self):
        """Loop executado a cada 10 minutos para verificar novas vagas nos servidores ativos."""
        logger.info("Iniciando ciclo de verificação de vagas...")
        
        if scrape_jobs is None:
            logger.error("A biblioteca python-jobspy não está instalada ou não pôde ser importada.")
            return

        try:
            # Buscar todos os servidores ativos (status = 'ON')
            active_guilds = await database.get_active_guild_configs()
            if not active_guilds:
                logger.info("Nenhum servidor com monitoramento ativo ('ON').")
                return

            for guild_cfg in active_guilds:
                guild_id = guild_cfg["guild_id"]
                channel_id = guild_cfg["channel_id"]
                cities_str = guild_cfg["cities"]
                engines_str = guild_cfg["search_engines"]

                # Obter o canal do Discord
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                    except Exception as e:
                        logger.warning(f"Não foi possível obter o canal {channel_id} para o servidor {guild_id}: {e}")
                        continue

                # Separar cidades e motores de busca
                cities = [c.strip() for c in cities_str.split(",") if c.strip()]
                engines = [e.strip() for e in engines_str.split(",") if e.strip()]

                if not cities or not engines:
                    logger.info(f"Servidor {guild_id} possui configurações incompletas. Pulando...")
                    continue

                # Executar a busca de vagas para cada cidade cadastrada
                for city in cities:
                    logger.info(f"Buscando vagas em '{city}' para o servidor {guild_id}...")
                    
                    try:
                        # Executar o scraping em um executor para não bloquear a thread principal
                        loop = asyncio.get_running_loop()
                        
                        # Chama a função síncrona do JobSpy
                        df = await loop.run_in_executor(
                            None,
                            partial(
                                scrape_jobs,
                                site_name=engines,
                                search_term=DEFAULT_SEARCH_TERM,
                                location=city,
                                results_wanted=15,
                                hours_old=24,
                                country_indeed=DEFAULT_COUNTRY
                            )
                        )
                        
                        if df is None or df.empty:
                            logger.info(f"Nenhuma vaga encontrada para '{city}' no servidor {guild_id}.")
                            continue

                        # Obter vagas que já foram enviadas anteriormente
                        sent_ids = await database.get_sent_job_ids(guild_id)
                        new_jobs_sent = []

                        # Iterar sobre as vagas encontradas
                        for idx, row in df.iterrows():
                            # Limpar e obter campos de forma segura contra variações de chaves (case/nome)
                            # JobSpy geralmente retorna colunas em minúsculo
                            job_id = str(row.get("id") or row.get("job_url") or "")
                            if not job_id:
                                continue

                            # Evitar duplicados
                            if job_id in sent_ids:
                                continue

                            # Extrair campos
                            title = str(row.get("title") or "Vaga Sem Título")
                            company = str(row.get("company") or "Empresa Não Especificada")
                            job_url = str(row.get("job_url") or "")
                            site_source = str(row.get("site") or "Desconhecido").capitalize()
                            
                            row_city = str(row.get("city") or "")
                            row_state = str(row.get("state") or "")
                            if row_city or row_state:
                                location = f"{row_city}, {row_state}".strip(", ")
                            else:
                                location = str(row.get("location") or "Não especificada")

                            # Se não houver URL, não enviamos pois o usuário precisa do link para se candidatar
                            if not job_url:
                                continue

                            # Criar Embed de Vaga
                            embed = discord.Embed(
                                title=f"💼 {title[:250]}",
                                url=job_url,
                                color=0x2ec7a2,  # Cor moderna esmeralda
                                timestamp=datetime.now(timezone.utc)
                            )
                            embed.add_field(name="🏢 Empresa", value=company, inline=True)
                            embed.add_field(name="📍 Localização", value=location, inline=True)
                            embed.add_field(name="🌐 Fonte", value=site_source, inline=True)
                            embed.set_footer(text="Project-Emprego • Nova Oportunidade")

                            # Enviar ao canal do Discord
                            try:
                                await channel.send(embed=embed)
                                new_jobs_sent.append(job_id)
                                # Adiciona um pequeno delay para não sofrer rate limit do discord
                                await asyncio.sleep(1)
                            except Exception as send_err:
                                logger.error(f"Erro ao enviar vaga {job_id} para canal {channel_id}: {send_err}")

                        # Atualizar a lista de vagas enviadas no BD de uma só vez para a cidade
                        if new_jobs_sent:
                            await database.add_sent_jobs(guild_id, new_jobs_sent)
                            logger.info(f"Enviadas {len(new_jobs_sent)} novas vagas para o servidor {guild_id} em '{city}'.")

                    except Exception as city_err:
                        # Tratar erros de scraping de forma a não interromper o loop de outras cidades/servidores
                        logger.error(f"Erro durante scraping de '{city}' para o servidor {guild_id}: {city_err}")
                        continue

        except Exception as loop_err:
            logger.error(f"Erro crítico no loop de monitoramento: {loop_err}")

    @monitor_loop.before_loop
    async def before_monitor_loop(self):
        # Aguardar o bot estar completamente pronto antes de rodar o loop
        await self.bot.wait_until_ready()
        logger.info("Bot pronto. Iniciando loop de monitoramento.")

    @app_commands.command(name="start", description="Inicia/Retoma o envio automático de vagas neste servidor.")
    @app_commands.default_permissions(administrator=True)
    async def start_monitor(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.response.send_message("Este comando só pode ser utilizado dentro de um servidor.", ephemeral=True)
            return

        # Verificar se o servidor já está cadastrado
        config = await database.get_guild_config(guild_id)
        if not config:
            await interaction.response.send_message(
                "❌ Este servidor ainda não foi configurado. Por favor, execute o comando `/setup` primeiro.",
                ephemeral=True
            )
            return

        if config["status"] == "ON":
            await interaction.response.send_message(
                "ℹ️ O monitoramento automático de vagas já está **ativo** (`ON`) neste servidor.",
                ephemeral=True
            )
            return

        try:
            # Atualizar status no BD
            await database.set_guild_status(guild_id, "ON")
            await interaction.response.send_message(
                "✅ O monitoramento automático de vagas foi **iniciado** para este servidor!",
                ephemeral=False
            )
        except Exception as e:
            await interaction.response.send_message(f"Ocorreu um erro ao iniciar: {e}", ephemeral=True)

    @app_commands.command(name="stop", description="Pausa o envio automático de vagas neste servidor.")
    @app_commands.default_permissions(administrator=True)
    async def stop_monitor(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if not guild_id:
            await interaction.response.send_message("Este comando só pode ser utilizado dentro de um servidor.", ephemeral=True)
            return

        # Verificar se o servidor já está cadastrado
        config = await database.get_guild_config(guild_id)
        if not config:
            await interaction.response.send_message(
                "❌ Este servidor ainda não foi configurado. Por favor, execute o comando `/setup` primeiro.",
                ephemeral=True
            )
            return

        if config["status"] == "OFF":
            await interaction.response.send_message(
                "ℹ️ O monitoramento automático de vagas já está **pausado** (`OFF`) neste servidor.",
                ephemeral=True
            )
            return

        try:
            # Atualizar status no BD
            await database.set_guild_status(guild_id, "OFF")
            await interaction.response.send_message(
                "🛑 O monitoramento automático de vagas foi **pausado** para este servidor!",
                ephemeral=False
            )
        except Exception as e:
            await interaction.response.send_message(f"Ocorreu um erro ao pausar: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(MonitorCog(bot))

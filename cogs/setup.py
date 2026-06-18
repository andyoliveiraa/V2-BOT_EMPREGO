import discord
from discord import app_commands
from discord.ext import commands
import database

class SetupModal(discord.ui.Modal, title="Configurar Cidades"):
    cities_input = discord.ui.TextInput(
        label="Cidades (separadas por vírgula)",
        style=discord.TextStyle.paragraph,
        placeholder="Ex: Lisboa, Porto, Coimbra",
        required=True,
        max_length=200
    )

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        # Transmitir os dados da cidade para a próxima etapa (Select View)
        cities = self.cities_input.value
        view = EngineSelectView(self.channel, cities)
        
        # Envia a mensagem efémera com o Select Menu
        await interaction.response.send_message(
            content="Por favor, selecione abaixo os sites que deseja monitorar:",
            view=view,
            ephemeral=True
        )

class EngineSelect(discord.ui.Select):
    def __init__(self, channel: discord.TextChannel, cities: str):
        options = [
            discord.SelectOption(label="LinkedIn", value="linkedin", description="Procura no LinkedIn"),
            discord.SelectOption(label="Indeed", value="indeed", description="Procura no Indeed"),
            discord.SelectOption(label="Glassdoor", value="glassdoor", description="Procura no Glassdoor"),
            discord.SelectOption(label="ZipRecruiter", value="zip_recruiter", description="Procura no ZipRecruiter"),
            discord.SelectOption(label="Google Jobs", value="google", description="Procura no Google Jobs"),
        ]
        super().__init__(
            placeholder="Selecione um ou mais sites...",
            min_values=1,
            max_values=len(options),
            options=options
        )
        self.channel = channel
        self.cities = cities

    async def callback(self, interaction: discord.Interaction):
        selected_engines = ",".join(self.values)
        guild_id = interaction.guild_id

        if not guild_id:
            await interaction.response.send_message("Este comando só pode ser utilizado dentro de um servidor.", ephemeral=True)
            return

        try:
            # Salvar configurações no banco de dados de forma assíncrona
            await database.save_guild_config(
                guild_id=guild_id,
                channel_id=self.channel.id,
                cities=self.cities,
                search_engines=selected_engines,
                status='ON'
            )

            # Formatar a resposta final para o administrador
            engines_formatted = ", ".join([opt.label for opt in self.options if opt.value in self.values])
            await interaction.response.edit_message(
                content=(
                    f"✅ **Configuração concluída com sucesso!**\n\n"
                    f"📍 **Canal de Alertas:** {self.channel.mention}\n"
                    f"🏙️ **Cidades de busca:** `{self.cities}`\n"
                    f"🔍 **Sites monitorados:** `{engines_formatted}`\n"
                    f"⚙️ **Status da Rotina:** `ON` (o monitoramento está ativo)"
                ),
                view=None
            )
        except Exception as e:
            await interaction.response.send_message(f"Ocorreu um erro ao salvar as configurações: {e}", ephemeral=True)

class EngineSelectView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel, cities: str):
        super().__init__(timeout=180)  # 3 minutos de timeout para interagir
        self.add_item(EngineSelect(channel, cities))

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Configura o canal de alertas, cidades e sites de busca.")
    @app_commands.describe(channel="Canal de texto onde os alertas de novas vagas serão enviados.")
    @app_commands.default_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        # Verificar permissão de escrita e envio no canal escolhido
        permissions = channel.permissions_for(interaction.guild.me)
        if not (permissions.send_messages and permissions.embed_links):
            await interaction.response.send_message(
                f"❌ Eu preciso de permissões para **Enviar Mensagens** e **Inserir Links** no canal {channel.mention}.",
                ephemeral=True
            )
            return

        # Enviar o Modal para o administrador preencher as cidades
        modal = SetupModal(channel)
        await interaction.response.send_modal(modal)

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))

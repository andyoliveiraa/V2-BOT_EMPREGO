import discord
from discord import app_commands
from discord.ext import commands
import database

class CitiesWizardModal(discord.ui.Modal):
    cities_input = discord.ui.TextInput(
        label="Cidades (separadas por vírgula)",
        style=discord.TextStyle.paragraph,
        placeholder="Ex: Lisboa, Porto, Coimbra",
        required=True,
        max_length=200
    )

    def __init__(self, view: "SetupWizardView"):
        super().__init__(title="Configurar Cidades")
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.view.cities = self.cities_input.value
        self.view.current_step = 2
        self.view.setup_buttons()
        await self.view.update_message(interaction)

class SetupWizardView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel, author_id: int):
        super().__init__(timeout=300)  # 5 minutos de timeout
        self.channel = channel
        self.author_id = author_id
        
        self.cities = None
        self.engines = {}  # E.g. {"linkedin": True, "indeed": False, ...}
        self.current_step = 1  # 1: Cidades, 2: LinkedIn, 3: Indeed, 4: Glassdoor, 5: ZipRecruiter, 6: Google Jobs
        
        self.engine_keys = ["linkedin", "indeed", "glassdoor", "zip_recruiter", "google"]
        self.engine_names = {
            "linkedin": "LinkedIn",
            "indeed": "Indeed",
            "glassdoor": "Glassdoor",
            "zip_recruiter": "ZipRecruiter",
            "google": "Google Jobs"
        }
        
        self.setup_buttons()

    def setup_buttons(self):
        self.clear_items()
        
        if self.current_step == 1:
            btn = discord.ui.Button(label="Digitar Cidades 🏙️", style=discord.ButtonStyle.primary)
            
            async def open_modal(interaction: discord.Interaction):
                modal = CitiesWizardModal(self)
                await interaction.response.send_modal(modal)
                
            btn.callback = open_modal
            self.add_item(btn)
            
        elif 2 <= self.current_step <= 6:
            engine_key = self.engine_keys[self.current_step - 2]
            
            btn_yes = discord.ui.Button(label="Sim ✅", style=discord.ButtonStyle.success)
            btn_no = discord.ui.Button(label="Não ❌", style=discord.ButtonStyle.danger)
            
            async def yes_click(interaction: discord.Interaction):
                await self.handle_choice(interaction, engine_key, True)
                
            async def no_click(interaction: discord.Interaction):
                await self.handle_choice(interaction, engine_key, False)
                
            btn_yes.callback = yes_click
            btn_no.callback = no_click
            
            self.add_item(btn_yes)
            self.add_item(btn_no)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Apenas o administrador que iniciou o setup pode responder às perguntas.", ephemeral=True)
            return False
        return True

    async def handle_choice(self, interaction: discord.Interaction, engine_key: str, choice: bool):
        self.engines[engine_key] = choice
        self.current_step += 1
        self.setup_buttons()
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        if self.current_step <= 6:
            next_engine = self.engine_names[self.engine_keys[self.current_step - 2]]
            
            content = (
                f"⚙️ **Configuração do Project-Emprego** (Progresso)\n\n"
                f"📍 **Canal de Alertas:** {self.channel.mention}\n"
                f"🏙️ **Cidades:** `{self.cities}`\n\n"
                f"**Respostas atuais:**\n"
                f"{self.format_choices()}\n"
                f"❓ **Pergunta {self.current_step}:** Deseja monitorizar vagas do **{next_engine}**?"
            )
            await interaction.response.edit_message(content=content, view=self)
        else:
            # Fim do setup, salvar no banco de dados!
            selected_engines = [k for k, v in self.engines.items() if v]
            if not selected_engines:
                await interaction.response.edit_message(
                    content=(
                        f"❌ **Erro na Configuração!**\n\n"
                        f"Você selecionou **Não** para todas as plataformas de busca.\n"
                        f"É necessário selecionar pelo menos uma plataforma. Por favor, execute o comando `/setup` novamente."
                    ),
                    view=None
                )
                return
            
            engines_str = ",".join(selected_engines)
            
            try:
                await database.save_guild_config(
                    guild_id=interaction.guild_id,
                    channel_id=self.channel.id,
                    cities=self.cities,
                    search_engines=engines_str,
                    status='ON'
                )
                
                engines_formatted = ", ".join([self.engine_names[k] for k in selected_engines])
                
                content = (
                    f"✅ **Configuração concluída com sucesso!**\n\n"
                    f"📍 **Canal de Alertas:** {self.channel.mention}\n"
                    f"🏙️ **Cidades de busca:** `{self.cities}`\n"
                    f"🔍 **Sites monitorados:** `{engines_formatted}`\n"
                    f"⚙️ **Status da Rotina:** `ON` (o monitoramento está ativo)"
                )
                await interaction.response.edit_message(content=content, view=None)
            except Exception as e:
                await interaction.response.edit_message(content=f"❌ Ocorreu um erro ao salvar as configurações: {e}", view=None)

    def format_choices(self) -> str:
        lines = []
        for key in self.engine_keys:
            if key in self.engines:
                status = "Sim ✅" if self.engines[key] else "Não ❌"
                lines.append(f"• **{self.engine_names[key]}:** {status}")
        return "\n".join(lines) + ("\n" if lines else "")

class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Configura o canal de alertas, cidades e sites de busca passo a passo.")
    @app_commands.describe(channel="Canal de texto onde os alertas de novas vagas serão enviados.")
    @app_commands.default_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        me = interaction.guild.me or interaction.guild.get_member(self.bot.user.id)
        if not me:
            await interaction.response.send_message(
                "❌ Não foi possível verificar as permissões do bot neste servidor.",
                ephemeral=True
            )
            return

        permissions = channel.permissions_for(me)
        if not (permissions.send_messages and permissions.embed_links):
            await interaction.response.send_message(
                f"❌ Eu preciso de permissões para **Enviar Mensagens** e **Inserir Links** no canal {channel.mention}.",
                ephemeral=True
            )
            return

        # Iniciar a view do Wizard de perguntas
        view = SetupWizardView(channel, interaction.user.id)
        
        # Enviar a primeira mensagem efémera para iniciar o setup
        content = (
            f"👋 **Bem-vindo ao Setup do Project-Emprego!**\n"
            f"Vamos configurar o monitoramento de vagas passo a passo por perguntas.\n\n"
            f"📍 **Canal de Alertas:** {channel.mention}\n\n"
            f"❓ **Pergunta 1:** Quais cidades deseja monitorar?\n"
            f"Clique no botão abaixo para digitar as cidades."
        )
        await interaction.response.send_message(content=content, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))

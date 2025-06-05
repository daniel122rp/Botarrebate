import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Modal, TextInput
import random
import string
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))
SUPPORT_ROLE_ID = int(os.getenv('SUPPORT_ROLE_ID'))
CATEGORY_ID = int(os.getenv('CATEGORY_ID'))
WELCOME_CHANNEL_ID = int(os.getenv('WELCOME_CHANNEL_ID'))

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

open_tickets = {}
MUTE_ROLE_NAME = "Muted"

# --- Funciones auxiliares ---
def generate_ticket_id(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

async def send_transcript(channel: discord.TextChannel, user: discord.User):
    messages = [f"[{msg.created_at}] {msg.author}: {msg.content}" async for msg in channel.history(limit=100)]
    transcript = "\n".join(reversed(messages))
    os.makedirs("transcripts", exist_ok=True)
    path = f"transcripts/transcript-{channel.id}.txt"

    with open(path, "w", encoding="utf-8") as f:
        f.write(transcript)

    try:
        await user.send(file=discord.File(path))
    except discord.Forbidden:
        print(f"No se pudo enviar el DM a {user}")

# --- Modal para crear ticket ---
class TicketModal(Modal, title="📨 Abrir Ticket"):
    motivo = TextInput(label="¿Cuál es el motivo del ticket?", style=discord.TextStyle.paragraph, required=True, max_length=500)

    async def on_submit(self, interaction: discord.Interaction):
        ticket_id = generate_ticket_id()
        sanitized_name = interaction.user.name.lower().replace(" ", "-")

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            interaction.guild.get_role(SUPPORT_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        channel = await interaction.guild.create_text_channel(
            name=f"🎫・{sanitized_name}-{ticket_id}",
            category=interaction.guild.get_channel(CATEGORY_ID),
            overwrites=overwrites
        )

        open_tickets[channel.id] = {
            "user": interaction.user,
            "reason": self.motivo.value,
            "id": ticket_id
        }

        view = TicketView()
        await channel.send(
            content=(
                f"**## Nuevo Ticket | Arrebate RP**\n"
                f"Espere a que un miembro del STAFF venga a revisar su TICKET\n\n"
                f"**ID de Ticket:** `{ticket_id}`\n"
                f"**Motivo de contacto:** `{self.motivo.value}`\n"
                f"**Tipo de ticket:** `Soporte`\n\n"
            ),
            view=view
        )

        await interaction.response.send_message(f"✅ Tu ticket ha sido creado: {channel.mention}", ephemeral=True)

# --- Vista de botones en tickets ---
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="❌ Cerrar", style=discord.ButtonStyle.danger, custom_id="close_ticket"))
        self.add_item(Button(label="📄 Transcripción", style=discord.ButtonStyle.secondary, custom_id="transcript_ticket"))
        self.add_item(Button(label="📞 Crear Llamada", style=discord.ButtonStyle.primary, custom_id="create_call"))
        self.add_item(Button(label="📲 Llamar Usuario", style=discord.ButtonStyle.success, custom_id="call_user"))
        self.add_item(Button(label="✅ Asumir", style=discord.ButtonStyle.success, custom_id="claim_ticket"))
        self.add_item(Button(label="🚪 Salir", style=discord.ButtonStyle.secondary, custom_id="leave_ticket"))

# --- Eventos ---
@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data["custom_id"]
        channel_id = interaction.channel.id

        if custom_id == "open_ticket":
            await interaction.response.send_modal(TicketModal())
            return

        if channel_id not in open_tickets:
            await interaction.response.send_message("❌ Este canal no es un ticket válido.", ephemeral=True)
            return

        user = open_tickets[channel_id]["user"]

        if custom_id == "close_ticket":
            await interaction.response.send_message("🗑️ Cerrando ticket y enviando transcripción...", ephemeral=True)
            await send_transcript(interaction.channel, user)
            await interaction.channel.delete()
        elif custom_id == "transcript_ticket":
            await interaction.response.send_message("📄 Enviando transcripción por DM...", ephemeral=True)
            await send_transcript(interaction.channel, user)
        elif custom_id == "create_call":
            await interaction.response.send_message("🔗 Intentando crear llamada de voz...", ephemeral=True)
            overwrites = interaction.channel.overwrites
            call_channel = await interaction.guild.create_voice_channel(
                name=f"Llamada-{user.name}",
                category=interaction.channel.category,
                overwrites=overwrites
            )
            await interaction.followup.send(f"📞 Llamada creada: {call_channel.mention}", ephemeral=True)
        elif custom_id == "call_user":
            try:
                await user.send(f"📲 El equipo de soporte te espera en tu ticket: {interaction.channel.mention}")
                await interaction.response.send_message(f"✅ Usuario {user.mention} notificado por DM.", ephemeral=True)
            except:
                await interaction.response.send_message("❌ No se pudo enviar el mensaje por DM al usuario.", ephemeral=True)
        elif custom_id == "claim_ticket":
            await interaction.response.send_message(f"✅ Ticket asumido por {interaction.user.mention}", ephemeral=False)
        elif custom_id == "leave_ticket":
            await interaction.channel.set_permissions(interaction.user, overwrite=None)
            await interaction.response.send_message("🚪 Has salido del ticket.", ephemeral=True)

# --- Comando del panel de tickets ---
@bot.command()
async def panel(ctx):
    embed = discord.Embed(
        title="🎫 Sistema de Tickets",
        description=(
            "Hola, este es el servicio de tickets de Arrebate RP. ⚡\n"
            "Haz clic en el botón de abajo para crear un ticket.\n\n"
            ":nexus_time: | Horario de servicio.\n"
            "🇺🇸 9:00 to 22:00\n"
            "🇩🇴 9:00 a.m. hasta 10:00 p.m.\n"
            "🇧🇷 10h00 às 22h00"
        ),
        color=0xFF0000
    )
    view = View()
    view.add_item(Button(label="📨 Abrir Ticket", style=discord.ButtonStyle.red, custom_id="open_ticket"))
    await ctx.send(embed=embed, view=view)

# --- Comando de difusión por DM ---
@bot.command()
@commands.has_permissions(administrator=True)
async def dmall(ctx, *, mensaje):
    await ctx.send("📤 Enviando mensaje a todos los miembros...")
    for member in ctx.guild.members:
        if not member.bot:
            try:
                await member.send(mensaje)
            except:
                continue
    await ctx.send("✅ Mensaje enviado.")

# --- Evento de bienvenida ---
@bot.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID:
        return

    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if channel is None:
        return

    member_count = member.guild.member_count

    embed = discord.Embed(
        title="🎉 ¡Bienvenido a Arrebate RP! 🎉",
        description=(
            f"Hola {member.mention}, ¡nos alegra que te hayas unido!\n\n"
            f"Actualmente somos **{member_count}** miembros disfrutando de la mejor experiencia de rol.\n\n"
            "Si necesitas ayuda o tienes dudas, usa nuestro sistema de tickets."
        ),
        color=0xFF0000
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text="Arrebate RP | ¡Diviértete!")

    await channel.send(embed=embed)

# --- Comandos de moderación ---
@bot.command()
@commands.has_permissions(administrator=True)
async def clear(ctx, amount: int):
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"✅ {amount} mensajes eliminados.", delete_after=5)

@bot.command()
@commands.has_permissions(administrator=True)
async def kick(ctx, member: discord.Member, *, reason="No especificado"):
    await member.kick(reason=reason)
    await ctx.send(f"👢 {member.mention} fue expulsado. Razón: {reason}")

@bot.command()
@commands.has_permissions(administrator=True)
async def ban(ctx, member: discord.Member, *, reason="No especificado"):
    await member.ban(reason=reason)
    await ctx.send(f"🔨 {member.mention} fue baneado. Razón: {reason}")

@bot.command()
@commands.has_permissions(administrator=True)
async def mute(ctx, member: discord.Member, tiempo: int = None):
    role = discord.utils.get(ctx.guild.roles, name=MUTE_ROLE_NAME)
    if not role:
        role = await ctx.guild.create_role(name=MUTE_ROLE_NAME)
        for channel in ctx.guild.channels:
            await channel.set_permissions(role, send_messages=False, speak=False)
    await member.add_roles(role)
    await ctx.send(f"🔇 {member.mention} ha sido silenciado.")
    if tiempo:
        await asyncio.sleep(tiempo * 60)
        await member.remove_roles(role)
        await ctx.send(f"🔊 {member.mention} ha sido desmuteado automáticamente.")

@bot.command()
@commands.has_permissions(administrator=True)
async def unmute(ctx, member: discord.Member):
    role = discord.utils.get(ctx.guild.roles, name=MUTE_ROLE_NAME)
    if role in member.roles:
        await member.remove_roles(role)
        await ctx.send(f"🔊 {member.mention} ha sido desmuteado.")

bot.run(TOKEN)

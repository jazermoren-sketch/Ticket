import asyncio
import time
import discord

from database.db import get_ticket_by_channel, update_ticket, get_guild_config, add_staff_points
from utils.embeds import error_embed, success_embed
from utils.transcript import create_transcript
from ui.rating import RatingView

class CloseReasonModal(discord.ui.Modal, title="🔒 إغلاق التذكرة"):
    reason = discord.ui.TextInput(
        label="سبب الإغلاق",
        placeholder="اكتب سبب إغلاق التذكرة...",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=False,
    )

    async def on_submit(self, interaction):
        view = TicketControlView()
        await view.close_ticket(interaction, self.reason.value or "لم يتم تحديد سبب.")

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استلام", emoji="👨‍💼", style=discord.ButtonStyle.primary)
    async def claim(self, interaction, button):
        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message(embed=error_embed("هذه القناة ليست تذكرة مفتوحة."), ephemeral=True)
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message(embed=error_embed("ليس لديك صلاحية استلام التذاكر."), ephemeral=True)
        # حماية ضد استغلال النقاط: صاحب التذكرة لا يستلم تذكرته.
        if interaction.user.id == ticket["user_id"]:
            return await interaction.response.send_message(
                embed=error_embed("❌ صاحب التذكرة لا يستطيع استلام تذكرته بنفسه."),
                ephemeral=True,
            )

        if ticket["claimed_by"]:
            return await interaction.response.send_message(embed=error_embed(f"التذكرة مستلمة بالفعل من طرف <@{ticket['claimed_by']}>."), ephemeral=True)
        update_ticket(interaction.channel.id, claimed_by=interaction.user.id)

        # +10 نقاط عند استلام التذكرة. لا يمكن تكرارها لأن التذكرة تصبح مستلمة.
        stats = add_staff_points(
            interaction.guild.id,
            interaction.user.id,
            10,
            source="claim",
        )
        tickets_cog = interaction.client.get_cog("Tickets")
        if tickets_cog:
            await tickets_cog.apply_promotion(
                interaction.guild,
                interaction.user,
                stats["points"],
            )

        await interaction.response.send_message(
            embed=success_embed(
                "تم استلام التذكرة",
                f"قام {interaction.user.mention} باستلام هذه التذكرة.\n"
                f"🏆 تمت إضافة **10 نقاط**. مجموع نقاطك: **{stats['points']}**",
            )
        )

    @discord.ui.button(label="قفل", emoji="🔒", style=discord.ButtonStyle.secondary)
    async def lock(self, interaction, button):
        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket or not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message(embed=error_embed("لا يمكنك استخدام هذا الزر هنا."), ephemeral=True)
        owner = interaction.guild.get_member(ticket["user_id"])
        if owner:
            await interaction.channel.set_permissions(owner, send_messages=False)
        await interaction.response.send_message(embed=success_embed("تم قفل التذكرة", "تم منع صاحب التذكرة من إرسال رسائل جديدة."))

    @discord.ui.button(label="فتح", emoji="🔓", style=discord.ButtonStyle.success)
    async def unlock(self, interaction, button):
        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket or not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message(embed=error_embed("لا يمكنك استخدام هذا الزر هنا."), ephemeral=True)
        owner = interaction.guild.get_member(ticket["user_id"])
        if owner:
            await interaction.channel.set_permissions(owner, send_messages=True)
        await interaction.response.send_message(embed=success_embed("تم فتح التذكرة", "يمكن لصاحب التذكرة إرسال الرسائل من جديد."))

    @discord.ui.button(label="إغلاق", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def close(self, interaction, button):
        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message(embed=error_embed("هذه القناة ليست تذكرة مفتوحة."), ephemeral=True)
        if not (interaction.user.id == ticket["user_id"] or interaction.user.guild_permissions.manage_channels):
            return await interaction.response.send_message(embed=error_embed("فقط صاحب التذكرة أو فريق الدعم يمكنه إغلاقها."), ephemeral=True)
        await interaction.response.send_modal(CloseReasonModal())

    async def close_ticket(self, interaction, reason):
        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message(embed=error_embed("هذه التذكرة مغلقة بالفعل."), ephemeral=True)

        await interaction.response.defer()
        transcript = await create_transcript(interaction.channel)
        config = get_guild_config(interaction.guild.id)
        update_ticket(interaction.channel.id, status="closed", closed_at=int(time.time()), close_reason=reason)

        transcript_file = discord.File(
            __import__("io").BytesIO(transcript.encode("utf-8")),
            filename=f"{interaction.channel.name}-transcript.html",
        )

        transcript_channel = interaction.guild.get_channel(config["transcript_channel_id"]) if config and config["transcript_channel_id"] else None
        if transcript_channel:
            await transcript_channel.send(
                content=f"📄 Transcript للتذكرة `{interaction.channel.name}`",
                file=transcript_file,
            )

        archive_category = interaction.guild.get_channel(config["archive_category_id"]) if config and config["archive_category_id"] else None

        await interaction.followup.send(
            embed=success_embed("تم إغلاق التذكرة", f"السبب: {reason}\nتم نقل التذكرة إلى الأرشيف."),
            view=RatingView(interaction.channel.id),
        )

        if archive_category:
            await interaction.channel.edit(category=archive_category, reason="Ticket archived")
            owner = interaction.guild.get_member(ticket["user_id"])
            if owner:
                await interaction.channel.set_permissions(owner, view_channel=True, send_messages=False)
            await interaction.channel.send("📦 **تم أرشفة هذه التذكرة.** يمكن للإدارة إعادة فتحها.")
        else:
            await asyncio.sleep(10)
            try:
                await interaction.channel.delete(reason=f"Ticket closed: {reason}")
            except discord.NotFound:
                pass

class ReopenView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إعادة فتح التذكرة", emoji="🔄", style=discord.ButtonStyle.success)
    async def reopen(self, interaction, button):
        ticket = get_ticket_by_channel(interaction.channel.id, include_closed=True)
        if not ticket:
            return await interaction.response.send_message(embed=error_embed("لم يتم العثور على بيانات التذكرة."), ephemeral=True)
        if not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message(embed=error_embed("فقط فريق الدعم يمكنه إعادة فتح التذكرة."), ephemeral=True)

        update_ticket(interaction.channel.id, status="open", closed_at=None)
        owner = interaction.guild.get_member(ticket["user_id"])
        if owner:
            await interaction.channel.set_permissions(owner, view_channel=True, send_messages=True, read_message_history=True)
        await interaction.response.send_message(embed=success_embed("تمت إعادة فتح التذكرة", "أصبحت التذكرة مفتوحة من جديد."))

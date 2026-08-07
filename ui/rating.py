import discord

from database.db import (
    get_ticket_by_channel,
    update_ticket,
    add_staff_points,
    create_ticket_rating,
    get_ticket_rating,
)
from database.staff import add_staff_xp, update_staff_stat
from utils.embeds import success_embed, error_embed
from utils.logger import log_event
from utils.config import get_xp_reward


class RatingView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=300)
        self.channel_id = channel_id

    @discord.ui.button(label="⭐", style=discord.ButtonStyle.secondary)
    async def one(self, interaction, button):
        await self.submit(interaction, 1)

    @discord.ui.button(label="⭐⭐", style=discord.ButtonStyle.secondary)
    async def two(self, interaction, button):
        await self.submit(interaction, 2)

    @discord.ui.button(label="⭐⭐⭐", style=discord.ButtonStyle.secondary)
    async def three(self, interaction, button):
        await self.submit(interaction, 3)

    @discord.ui.button(label="⭐⭐⭐⭐", style=discord.ButtonStyle.secondary)
    async def four(self, interaction, button):
        await self.submit(interaction, 4)

    @discord.ui.button(label="⭐⭐⭐⭐⭐", style=discord.ButtonStyle.success)
    async def five(self, interaction, button):
        await self.submit(interaction, 5)

    async def submit(self, interaction, rating):
        ticket = get_ticket_by_channel(self.channel_id, include_closed=True)

        if not ticket:
            return await interaction.response.send_message(
                embed=error_embed("لم يتم العثور على بيانات التذكرة."),
                ephemeral=True,
            )

        # التقييم خاص بصاحب التذكرة فقط.
        if interaction.user.id != ticket["user_id"]:
            return await interaction.response.send_message(
                embed=error_embed("فقط صاحب التذكرة يمكنه إرسال التقييم."),
                ephemeral=True,
            )

        # حماية ضد استغلال النقاط: لا تقييم قبل استلام إداري للتذكرة.
        if not ticket["claimed_by"]:
            return await interaction.response.send_message(
                embed=error_embed("❌ خاص شي إداري يستلم التذكرة أولاً، ومن بعد تقدر تقيّم الخدمة."),
                ephemeral=True,
            )

        if interaction.user.id == ticket["claimed_by"]:
            return await interaction.response.send_message(
                embed=error_embed("❌ لا يمكن للموظف تقييم نفسه أو تذكرته."),
                ephemeral=True,
            )

        # منع التقييم أكثر من مرة.
        if get_ticket_rating(self.channel_id, ticket["user_id"]):
            return await interaction.response.send_message(
                embed=error_embed("تم تقييم هذه التذكرة مسبقاً."),
                ephemeral=True,
            )

        if ticket["rating"] is not None:
            return await interaction.response.send_message(
                embed=error_embed("تم تقييم هذه التذكرة مسبقاً."),
                ephemeral=True,
            )

        rating_id = create_ticket_rating(interaction.guild.id, self.channel_id, ticket["user_id"], ticket["claimed_by"], rating)
        if rating_id is None:
            return await interaction.response.send_message(
                embed=error_embed("تم تقييم هذه التذكرة مسبقاً."),
                ephemeral=True,
            )
        update_ticket(self.channel_id, rating=rating)

        # عدد النجوم = عدد النقاط التي يحصل عليها الإداري المستلم.
        awarded = 0
        total_points = None

        if ticket["claimed_by"] and ticket["claimed_by"] != interaction.user.id:
            add_staff_xp(ticket["claimed_by"], rating * get_xp_reward("rating_multiplier", 2))
            update_staff_stat(ticket["claimed_by"], "ratings_received")
            stats = add_staff_points(
                interaction.guild.id,
                ticket["claimed_by"],
                rating,
                source="rating",
            )
            awarded = rating
            total_points = stats["points"]
            tickets_cog = interaction.client.get_cog("Tickets")
            staff_member = interaction.guild.get_member(ticket["claimed_by"])
            if tickets_cog and staff_member:
                await tickets_cog.apply_promotion(
                    interaction.guild,
                    staff_member,
                    stats["points"],
                )

        await log_event(interaction.guild, "⭐ Ticket Rating", f"{interaction.user.mention} قيّم <#{self.channel_id}> بـ {rating}/5.", color=discord.Color.gold())

        for child in self.children:
            child.disabled = True

        extra = (
            f"\\n🏆 تمت إضافة **{awarded} نقاط** للإداري الذي استلم التذكرة."
            if awarded
            else
            "\\nℹ️ لم تُضف نقاط للإدارة لأن التذكرة لم يتم استلامها."
        )

        await interaction.response.edit_message(
            embed=success_embed(
                "شكراً على تقييمك",
                f"تم تسجيل تقييمك: {'⭐' * rating}{extra}",
            ),
            view=self,
        )

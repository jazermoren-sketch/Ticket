import discord
from discord import app_commands
from discord.ext import commands

from database.db import get_staff_xp_multiplier, set_staff_xp_multiplier
from database.staff import get_staff, create_staff, get_staff_leaderboard, get_staff_totals
from utils.embeds import error_embed, info_embed, success_embed
from utils.ranks import progress_to_next_rank
from utils.logger import log_event


class Staff(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    staff = app_commands.Group(name="staff", description="Staff profile, stats, and leaderboard")

    @staticmethod
    def _can_view_staff(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.manage_channels or interaction.user.guild_permissions.administrator

    @staff.command(name="profile", description="عرض ملف موظف في نظام ArabicTickets Ultimate")
    async def profile(self, interaction: discord.Interaction, member: discord.Member | None = None):
        if not self._can_view_staff(interaction):
            member = interaction.user
        member = member or interaction.user
        profile = get_staff(member.id) or create_staff(member.id)
        progress = progress_to_next_rank(profile["xp"])
        next_text = "أعلى رتبة" if not progress["next"] else f"{progress['next']['name']} — متبقي {progress['remaining']} XP"
        embed = discord.Embed(
            title="👤 Staff Profile",
            description=(
                f"العضو: {member.mention}\n"
                f"XP: **{profile['xp']}**\n"
                f"Level: **{profile['level']}**\n"
                f"Rank: **{profile['rank']}**\n"
                f"Next: **{next_text}**\n\n"
                f"Tickets claimed: **{profile['tickets_claimed']}**\n"
                f"Tickets closed: **{profile['tickets_closed']}**\n"
                f"Ratings: **{profile['ratings_received']}**"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=not self._can_view_staff(interaction))

    @staff.command(name="stats", description="إحصائيات الطاقم العامة")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def stats(self, interaction: discord.Interaction):
        totals = get_staff_totals()
        await interaction.response.send_message(
            embed=info_embed(
                "📊 Staff Stats",
                f"Members: **{totals['members']}**\nXP: **{totals['xp']}**\nTickets claimed: **{totals['tickets_claimed']}**\nTickets closed: **{totals['tickets_closed']}**\nRatings: **{totals['ratings_received']}**",
            ),
            ephemeral=True,
        )

    @staff.command(name="leaderboard", description="ترتيب أفضل أعضاء الطاقم")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def leaderboard(self, interaction: discord.Interaction):
        rows = get_staff_leaderboard(10)
        if not rows:
            return await interaction.response.send_message(embed=info_embed("🏆 Staff Leaderboard", "لا توجد بيانات بعد."), ephemeral=True)
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for index, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.mention if member else f"<@{row['user_id']}>"
            lines.append(f"{medals[index] if index < 3 else f'#{index + 1}'} {name} — **{row['xp']} XP** • {row['rank']}")
        await interaction.response.send_message(embed=info_embed("🏆 Staff Leaderboard", "\n".join(lines)))


    @staff.command(name="xp-multiplier", description="عرض أو تعديل مضاعف Staff XP")
    async def xp_multiplier(self, interaction: discord.Interaction, multiplier: int | None = None):
        if not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator):
            return await interaction.response.send_message(
                embed=error_embed("ليس لديك صلاحية إدارة مضاعف Staff XP."),
                ephemeral=True,
            )

        current = get_staff_xp_multiplier(interaction.guild.id)
        if multiplier is None:
            status = "Normal (×1)" if current == 1 else f"×{current}"
            embed = info_embed("Staff XP Multiplier", f"Staff XP Multiplier: **{status}**")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if multiplier < 0:
            return await interaction.response.send_message(
                embed=error_embed("لا يمكن استخدام قيمة سالبة. القيم المسموحة: 0 أو 1 إلى 10."),
                ephemeral=True,
            )
        if multiplier > 10:
            return await interaction.response.send_message(
                embed=error_embed("أعلى مضاعف مسموح هو ×10."),
                ephemeral=True,
            )

        new_multiplier = set_staff_xp_multiplier(interaction.guild.id, multiplier)
        sample_base_xp = 10
        title = "Staff XP Multiplier Disabled" if multiplier == 0 or new_multiplier == 1 else "Staff XP Multiplier Updated"
        description = f"Multiplier:\n**×{new_multiplier}**"
        if new_multiplier != 1:
            description += (
                f"\n\nBase XP:\n**{sample_base_xp}**"
                f"\n\nFinal XP:\n**{sample_base_xp * new_multiplier}**"
            )
        embed = success_embed(title, description)
        await log_event(
            interaction.guild,
            "Staff XP Multiplier Changed",
            f"Admin: {interaction.user.mention}\nOld: ×{current}\nNew: ×{new_multiplier}",
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @staff.command(name="dashboard", description="لوحة إدارة الطاقم")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def dashboard(self, interaction: discord.Interaction):
        totals = get_staff_totals()
        await interaction.response.send_message(
            embed=info_embed(
                "🧭 Staff Dashboard",
                f"Members: **{totals['members']}**\nXP: **{totals['xp']}**\nاختر من الأزرار لعرض التفاصيل.",
            ),
            view=StaffDashboardView(),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Staff(bot))

class StaffDashboardView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    async def _send(self, interaction: discord.Interaction, title: str, body: str):
        await interaction.response.send_message(embed=info_embed(title, body), ephemeral=True)

    @discord.ui.button(label="Leaderboard", emoji="🏆", style=discord.ButtonStyle.primary)
    async def leaderboard_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        rows = get_staff_leaderboard(10)
        body = "\n".join(f"#{i+1} <@{r['user_id']}> — {r['xp']} XP • {r['rank']}" for i, r in enumerate(rows)) or "لا توجد بيانات."
        await self._send(interaction, "🏆 Staff Leaderboard", body)

    @discord.ui.button(label="Statistics", emoji="📊", style=discord.ButtonStyle.secondary)
    async def statistics_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        totals = get_staff_totals()
        await self._send(interaction, "📊 Staff Statistics", f"Members: {totals['members']}\nXP: {totals['xp']}\nClaimed: {totals['tickets_claimed']}\nClosed: {totals['tickets_closed']}\nRatings: {totals['ratings_received']}")

    @discord.ui.button(label="Promotions", emoji="🎉", style=discord.ButtonStyle.success)
    async def promotions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        rows = get_staff_leaderboard(5)
        body = "\n".join(f"<@{r['user_id']}> — {r['rank']} ({r['xp']} XP)" for r in rows) or "لا توجد ترقيات للعرض."
        await self._send(interaction, "🎉 Promotions", body)

    @discord.ui.button(label="Activity", emoji="⚡", style=discord.ButtonStyle.secondary)
    async def activity_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        rows = get_staff_leaderboard(5)
        body = "\n".join(f"<@{r['user_id']}> — claim {r['tickets_claimed']} / close {r['tickets_closed']} / rating {r['ratings_received']}" for r in rows) or "لا توجد بيانات نشاط."
        await self._send(interaction, "⚡ Staff Activity", body)

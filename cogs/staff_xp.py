import time

import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    add_staff_message,
    add_staff_points,
    get_guild_config,
    get_member_effective_points,
    get_promotions,
    get_staff_message_stats,
    get_staff_points,
    get_staff_xp_roles,
    remove_staff_xp_role,
    set_guild_config,
    upsert_staff_xp_role,
)
from utils.embeds import error_embed, info_embed, success_embed


class StaffXP(commands.Cog):
    """نظام Staff XP المستقل: الرسائل، الكولداون، والرتب المسموحة."""

    DEFAULT_MESSAGES_PER_XP = 30
    DEFAULT_COOLDOWN_SECONDS = 60

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_cooldowns: dict[tuple[int, int], float] = {}

    def _settings(self, guild_id: int) -> tuple[int, int]:
        config = get_guild_config(guild_id)
        messages_per_xp = (
            int(config["staff_xp_messages_per_point"])
            if config and config["staff_xp_messages_per_point"]
            else self.DEFAULT_MESSAGES_PER_XP
        )
        cooldown_seconds = (
            int(config["staff_xp_cooldown_seconds"])
            if config and config["staff_xp_cooldown_seconds"]
            else self.DEFAULT_COOLDOWN_SECONDS
        )
        return max(1, messages_per_xp), max(0, cooldown_seconds)

    @staticmethod
    def _has_allowed_role(member: discord.Member, role_ids: set[int]) -> bool:
        return any(role.id in role_ids for role in member.roles)

    async def _send_xp_log(self, guild: discord.Guild, member: discord.Member, total_points: int, total_messages: int) -> None:
        config = get_guild_config(guild.id)
        channel_id = config["staff_xp_log_channel_id"] if config and config["staff_xp_log_channel_id"] else None
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return

        embed = discord.Embed(
            title="⭐ Staff XP",
            description=(
                f"{member.mention} حصل على **1 XP** بسبب نشاط الرسائل.\n\n"
                f"🏆 مجموع النقاط: `{total_points}`\n"
                f"💬 الرسائل المحتسبة: `{total_messages}`"
            ),
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ArabicTickets Ultimate • {guild.name}")
        try:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
        except (discord.Forbidden, discord.HTTPException):
            return

    async def _try_apply_promotion(self, guild: discord.Guild, member: discord.Member, earned_points: int) -> None:
        tickets_cog = self.bot.get_cog("Tickets")
        if tickets_cog and hasattr(tickets_cog, "apply_promotion"):
            await tickets_cog.apply_promotion(guild, member, earned_points)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None or not isinstance(message.author, discord.Member):
            return

        role_ids = set(get_staff_xp_roles(message.guild.id))
        if not role_ids or not self._has_allowed_role(message.author, role_ids):
            return

        now = time.monotonic()
        messages_per_xp, cooldown_seconds = self._settings(message.guild.id)
        cooldown_key = (message.guild.id, message.author.id)
        last_counted = self.message_cooldowns.get(cooldown_key, 0)
        if cooldown_seconds and now - last_counted < cooldown_seconds:
            return
        self.message_cooldowns[cooldown_key] = now

        stats = add_staff_message(message.guild.id, message.author.id, messages_per_xp)
        awarded = int(stats.get("awarded_points", 0))
        if awarded <= 0:
            return

        point_row = add_staff_points(message.guild.id, message.author.id, awarded, source="message")
        await self._send_xp_log(message.guild, message.author, int(point_row["points"]), int(stats["counted_messages"]))
        await self._try_apply_promotion(message.guild, message.author, awarded)

    @app_commands.command(name="add-staff-xp-role", description="إضافة رتبة مسموح لها بجمع Staff XP من الرسائل")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_staff_xp_role(self, interaction: discord.Interaction, role: discord.Role):
        upsert_staff_xp_role(interaction.guild.id, role.id)
        await interaction.response.send_message(
            embed=success_embed("تمت إضافة رتبة Staff XP", f"سيتم احتساب رسائل أعضاء {role.mention}."),
            ephemeral=True,
        )

    @app_commands.command(name="remove-staff-xp-role", description="حذف رتبة من رتب Staff XP")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_staff_xp_role_command(self, interaction: discord.Interaction, role: discord.Role):
        if not remove_staff_xp_role(interaction.guild.id, role.id):
            return await interaction.response.send_message(embed=error_embed("هذه الرتبة غير مضافة لنظام Staff XP."), ephemeral=True)
        await interaction.response.send_message(embed=success_embed("تم حذف رتبة Staff XP", f"تم إيقاف احتساب رسائل {role.mention}."), ephemeral=True)

    @app_commands.command(name="staff-xp-roles", description="عرض الرتب المسموح لها بجمع Staff XP")
    async def staff_xp_roles(self, interaction: discord.Interaction):
        role_ids = get_staff_xp_roles(interaction.guild.id)
        if not role_ids:
            text = "لا توجد رتب محددة. أضف رتبة باستعمال `/add-staff-xp-role`."
        else:
            text = "\n".join(f"• {interaction.guild.get_role(role_id).mention if interaction.guild.get_role(role_id) else f'`{role_id}`'}" for role_id in role_ids)
        await interaction.response.send_message(embed=info_embed("رتب Staff XP", text), ephemeral=True)

    @app_commands.command(name="staff-xp-settings", description="تعديل إعدادات Staff XP للرسائل والكولداون")
    @app_commands.checks.has_permissions(administrator=True)
    async def staff_xp_settings(
        self,
        interaction: discord.Interaction,
        messages_per_xp: app_commands.Range[int, 1, 1000] = DEFAULT_MESSAGES_PER_XP,
        cooldown_seconds: app_commands.Range[int, 0, 86400] = DEFAULT_COOLDOWN_SECONDS,
        log_channel: discord.TextChannel | None = None,
    ):
        fields = {
            "staff_xp_messages_per_point": int(messages_per_xp),
            "staff_xp_cooldown_seconds": int(cooldown_seconds),
        }
        if log_channel is not None:
            fields["staff_xp_log_channel_id"] = log_channel.id
        set_guild_config(interaction.guild.id, **fields)
        log_text = log_channel.mention if log_channel else "بدون تغيير"
        await interaction.response.send_message(
            embed=success_embed(
                "تم حفظ إعدادات Staff XP",
                f"💬 كل `{messages_per_xp}` رسالة = `1 XP`\n⏳ الكولداون: `{cooldown_seconds}` ثانية\n📜 قناة اللوج: {log_text}",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="staff-xp", description="عرض XP ورسائل إداري")
    async def staff_xp(self, interaction: discord.Interaction, member: discord.Member | None = None):
        member = member or interaction.user
        stats = get_staff_points(interaction.guild.id, member.id)
        messages = get_staff_message_stats(interaction.guild.id, member.id)
        point_data = get_member_effective_points(interaction.guild.id, member.id, [role.id for role in member.roles])
        promotions = get_promotions(interaction.guild.id)
        next_promotion = next((p for p in promotions if p["required_points"] > point_data["effective_points"]), None)
        next_text = "وصل لأعلى رتبة" if not next_promotion else f"<@&{next_promotion['role_id']}> — متبقي `{next_promotion['required_points'] - point_data['effective_points']}` XP"
        await interaction.response.send_message(
            embed=info_embed(
                "⭐ Staff XP",
                f"👤 الإداري: {member.mention}\n🏆 XP المكتسب: `{stats['points']}`\n📊 XP الفعلي: `{point_data['effective_points']}`\n💬 الرسائل المحتسبة: `{messages['counted_messages']}`\n⬆️ الترقية القادمة: {next_text}",
            )
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffXP(bot))

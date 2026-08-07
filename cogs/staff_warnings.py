import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    add_staff_warning,
    delete_staff_warning,
    get_guild_config,
    get_staff_warning,
    get_staff_warnings,
    set_guild_config,
)
from utils.embeds import error_embed, info_embed, success_embed


class StaffWarnings(commands.Cog):
    """نظام تحذيرات الإدارة: إضافة، حذف، سجل، لوج، وعقوبة تلقائية."""

    DEFAULT_WARNING_LIMIT = 3

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _settings(self, guild_id: int) -> tuple[int, int | None, int | None]:
        config = get_guild_config(guild_id)
        limit = int(config["staff_warning_limit"]) if config and config["staff_warning_limit"] else self.DEFAULT_WARNING_LIMIT
        log_channel_id = config["staff_warning_log_channel_id"] if config and config["staff_warning_log_channel_id"] else None
        punishment_role_id = config["staff_warning_punishment_role_id"] if config and config["staff_warning_punishment_role_id"] else None
        return max(1, limit), log_channel_id, punishment_role_id

    async def _send_warning_log(
        self,
        guild: discord.Guild,
        *,
        title: str,
        description: str,
        color: discord.Color,
    ) -> None:
        _, log_channel_id, _ = self._settings(guild.id)
        channel = guild.get_channel(log_channel_id) if log_channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        embed.set_footer(text=f"Staff Warnings • {guild.name}")
        try:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
        except (discord.Forbidden, discord.HTTPException):
            return

    async def _apply_auto_punishment(
        self,
        guild: discord.Guild,
        member: discord.Member,
        active_count: int,
        moderator: discord.Member | discord.User,
    ) -> bool:
        limit, _, punishment_role_id = self._settings(guild.id)
        if active_count < limit or not punishment_role_id:
            return False
        role = guild.get_role(punishment_role_id)
        if role is None or role in member.roles:
            return False
        try:
            await member.add_roles(role, reason=f"Staff warnings reached {active_count}/{limit} by {moderator}")
        except (discord.Forbidden, discord.HTTPException):
            return False
        await self._send_warning_log(
            guild,
            title="⛔ عقوبة تلقائية بسبب التحذيرات",
            description=(
                f"👤 الإداري: {member.mention}\n"
                f"🛡️ المسؤول: {moderator.mention}\n"
                f"⚠️ التحذيرات النشطة: `{active_count}/{limit}`\n"
                f"🔒 رتبة العقوبة: {role.mention}"
            ),
            color=discord.Color.dark_red(),
        )
        return True

    @app_commands.command(name="warn-staff", description="إضافة تحذير لإداري")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(member="الإداري المراد تحذيره", reason="سبب التحذير")
    async def warn_staff(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if member.bot:
            return await interaction.response.send_message(embed=error_embed("لا يمكن تحذير البوتات."), ephemeral=True)
        warning = add_staff_warning(interaction.guild.id, member.id, interaction.user.id, reason)
        active_count = int(warning["active_count"])
        limit, _, _ = self._settings(interaction.guild.id)
        punished = await self._apply_auto_punishment(interaction.guild, member, active_count, interaction.user)

        description = (
            f"👤 الإداري: {member.mention}\n"
            f"🛡️ المسؤول: {interaction.user.mention}\n"
            f"🆔 رقم التحذير: `{warning['id']}`\n"
            f"⚠️ التحذيرات النشطة: `{active_count}/{limit}`\n"
            f"📝 السبب: {reason}"
        )
        if punished:
            description += "\n⛔ تم تطبيق العقوبة التلقائية."
        await self._send_warning_log(interaction.guild, title="⚠️ تحذير إداري جديد", description=description, color=discord.Color.orange())
        await interaction.response.send_message(embed=success_embed("تم إضافة التحذير", description), ephemeral=True)

    @app_commands.command(name="remove-staff-warning", description="حذف/إلغاء تحذير إداري")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_staff_warning(self, interaction: discord.Interaction, warning_id: int, reason: str = "تم حذف التحذير"):
        warning = get_staff_warning(interaction.guild.id, warning_id)
        if not warning or not warning["active"]:
            return await interaction.response.send_message(embed=error_embed("التحذير غير موجود أو محذوف مسبقاً."), ephemeral=True)
        delete_staff_warning(interaction.guild.id, warning_id, interaction.user.id, reason)
        member_text = f"<@{warning['user_id']}>"
        description = f"👤 الإداري: {member_text}\n🆔 رقم التحذير: `{warning_id}`\n🛡️ حذف بواسطة: {interaction.user.mention}\n📝 السبب: {reason}"
        await self._send_warning_log(interaction.guild, title="✅ حذف تحذير إداري", description=description, color=discord.Color.green())
        await interaction.response.send_message(embed=success_embed("تم حذف التحذير", description), ephemeral=True)

    @app_commands.command(name="staff-warnings", description="عرض سجل تحذيرات إداري")
    async def staff_warnings(self, interaction: discord.Interaction, member: discord.Member | None = None, show_inactive: bool = False):
        member = member or interaction.user
        rows = get_staff_warnings(interaction.guild.id, member.id, include_inactive=show_inactive, limit=15)
        if not rows:
            return await interaction.response.send_message(embed=info_embed("تحذيرات الإدارة", f"لا توجد تحذيرات مسجلة لـ {member.mention}."), ephemeral=True)
        lines = []
        for row in rows:
            status = "نشط" if row["active"] else "محذوف"
            lines.append(f"`#{row['id']}` **{status}** • <t:{row['created_at']}:R>\n└ {row['reason']}\n└ بواسطة: <@{row['moderator_id']}>")
        await interaction.response.send_message(embed=info_embed("⚠️ سجل التحذيرات", f"👤 {member.mention}\n\n" + "\n\n".join(lines)), ephemeral=True)

    @app_commands.command(name="staff-warning-settings", description="تعديل إعدادات تحذيرات الإدارة")
    @app_commands.checks.has_permissions(administrator=True)
    async def staff_warning_settings(
        self,
        interaction: discord.Interaction,
        limit: app_commands.Range[int, 1, 100] = DEFAULT_WARNING_LIMIT,
        log_channel: discord.TextChannel | None = None,
        punishment_role: discord.Role | None = None,
    ):
        fields = {"staff_warning_limit": int(limit)}
        if log_channel is not None:
            fields["staff_warning_log_channel_id"] = log_channel.id
        if punishment_role is not None:
            fields["staff_warning_punishment_role_id"] = punishment_role.id
        set_guild_config(interaction.guild.id, **fields)
        await interaction.response.send_message(
            embed=success_embed(
                "تم حفظ إعدادات التحذيرات",
                f"⚠️ حد العقوبة: `{limit}`\n📜 قناة اللوج: {log_channel.mention if log_channel else 'بدون تغيير'}\n⛔ رتبة العقوبة: {punishment_role.mention if punishment_role else 'بدون تغيير'}",
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(StaffWarnings(bot))

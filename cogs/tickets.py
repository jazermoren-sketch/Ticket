import asyncio
import time
import discord
from discord import app_commands
from discord.ext import commands, tasks

from database.db import (
    get_guild_config, set_guild_config, create_ticket,
    get_ticket_by_channel, get_open_ticket_for_user,
    get_open_tickets_for_autoclose, update_ticket,
    get_staff_points, get_staff_leaderboard,
    add_promotion, remove_promotion, get_promotions, get_promotion_for_role,
    get_member_effective_points,
)
from ui.panel import TicketPanelView
from ui.ticket import TicketControlView, ReopenView
from utils.embeds import success_embed, error_embed, info_embed
from utils.transcript import create_transcript
from utils.advanced import priority_label, format_tags

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.autoclose_loop.start()
        self.sla_loop.start()

    def cog_unload(self):
        self.autoclose_loop.cancel()
        self.sla_loop.cancel()

    def is_admin(self, interaction):
        return interaction.user.guild_permissions.administrator


    async def apply_promotion(self, guild, member, earned_points):
        promotions = get_promotions(guild.id)
        if not promotions:
            return None

        point_data = get_member_effective_points(
            guild.id, member.id, [role.id for role in member.roles]
        )
        effective_points = point_data["effective_points"]

        eligible = [
            promotion for promotion in promotions
            if effective_points >= promotion["required_points"]
        ]
        if not eligible:
            return None

        target = eligible[-1]
        target_role = guild.get_role(target["role_id"])
        if target_role is None or target_role in member.roles:
            return None

        promotion_role_ids = {p["role_id"] for p in promotions}
        current_roles = [
            role for role in member.roles
            if role.id in promotion_role_ids
        ]
        old_role = max(
            current_roles,
            key=lambda role: next(
                (p["required_points"] for p in promotions if p["role_id"] == role.id),
                0,
            ),
            default=None,
        )

        old_roles = [role for role in current_roles if role.id != target_role.id]

        try:
            if old_roles:
                await member.remove_roles(
                    *old_roles,
                    reason="ترقية تلقائية حسب نقاط التكت",
                )
            await member.add_roles(
                target_role,
                reason="ترقية تلقائية حسب نقاط التكت",
            )

            config = get_guild_config(guild.id)
            channel_id = config["promotion_channel_id"] if config and config["promotion_channel_id"] else None
            channel = guild.get_channel(channel_id) if channel_id else None
            if isinstance(channel, discord.TextChannel):
                old_role_text = old_role.mention if old_role else "بدون رتبة إدارية سابقة"
                embed = discord.Embed(
                    title="🎉 تهانينا لك، حصلت على المستوى الإداري التالي",
                    description=(
                        f"{member.mention}\n\n"
                        f"📌 **الرتبة السابقة:** {old_role_text}\n"
                        f"🚀 **الرتبة الجديدة:** {target_role.mention}\n"
                        f"🏆 **النقاط الفعلية:** `{effective_points}`\n\n"
                        "واصل التفاعل والتألق، وبالتوفيق في مهامك الإدارية!"
                    ),
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"ترقية إدارية • {guild.name}")
                try:
                    await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
                except (discord.Forbidden, discord.HTTPException) as error:
                    print(f"Promotion announcement error: {error}")

            return {
                "old_role": old_role,
                "new_role": target_role,
                "earned_points": earned_points,
                "base_points": point_data["base_points"],
                "effective_points": effective_points,
            }
        except (discord.Forbidden, discord.HTTPException) as error:
            print(f"Promotion error: {error}")
            return None

    @app_commands.command(name="set-promotion-channel", description="تحديد قناة إعلانات ترقيات الإدارة")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="القناة التي ستظهر فيها إعلانات الترقيات")
    async def set_promotion_channel_command(self, interaction, channel: discord.TextChannel):
        set_guild_config(interaction.guild.id, promotion_channel_id=channel.id)
        await interaction.response.send_message(
            embed=success_embed("تم تحديد قناة الترقيات", f"📢 سيتم إعلان ترقيات الإدارة في {channel.mention}."),
            ephemeral=True,
        )

    @app_commands.command(name="promotion-channel", description="عرض قناة إعلانات الترقيات الحالية")
    async def promotion_channel_command(self, interaction):
        config = get_guild_config(interaction.guild.id)
        channel_id = config["promotion_channel_id"] if config and config["promotion_channel_id"] else None
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        text = channel.mention if channel else "لم يتم تحديد قناة بعد."
        await interaction.response.send_message(
            embed=info_embed("📢 قناة ترقيات الإدارة", text), ephemeral=True
        )

    @app_commands.command(name="clear-promotion-channel", description="إلغاء قناة إعلانات الترقيات")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_promotion_channel_command(self, interaction):
        set_guild_config(interaction.guild.id, promotion_channel_id=None)
        await interaction.response.send_message(
            embed=success_embed("تم إلغاء قناة الترقيات", "لن يتم إرسال إعلانات الترقيات حتى تحدد قناة جديدة."),
            ephemeral=True,
        )

    @app_commands.command(name="add-promotion", description="إضافة رتبة إلى نظام الترقيات")
    @app_commands.describe(role="الرتبة التي ستتم إضافتها", points="عدد النقاط المطلوبة")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_promotion_command(self, interaction, role: discord.Role, points: app_commands.Range[int, 0, 10000000]):
        add_promotion(interaction.guild.id, role.id, points)
        await interaction.response.send_message(
            embed=success_embed(
                "تم حفظ الترقية",
                f"🏅 الرتبة: {role.mention}\n🏆 النقاط المطلوبة: **{points}**",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="edit-promotion", description="تعديل نقاط رتبة في نظام الترقيات")
    @app_commands.describe(role="الرتبة المراد تعديلها", points="عدد النقاط الجديدة")
    @app_commands.checks.has_permissions(administrator=True)
    async def edit_promotion_command(self, interaction, role: discord.Role, points: app_commands.Range[int, 0, 10000000]):
        if not get_promotion_for_role(interaction.guild.id, role.id):
            return await interaction.response.send_message(
                embed=error_embed("❌ هاد الرتبة ماكايناش فـنظام الترقيات."),
                ephemeral=True,
            )

        add_promotion(interaction.guild.id, role.id, points)
        await interaction.response.send_message(
            embed=success_embed(
                "تم تعديل الترقية",
                f"🏅 {role.mention}\n🏆 النقاط الجديدة: **{points}**",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="remove-promotion", description="حذف رتبة من نظام الترقيات")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_promotion_command(self, interaction, role: discord.Role):
        if not remove_promotion(interaction.guild.id, role.id):
            return await interaction.response.send_message(
                embed=error_embed("❌ هاد الرتبة ماكايناش فـنظام الترقيات."),
                ephemeral=True,
            )

        await interaction.response.send_message(
            embed=success_embed(
                "تم حذف الترقية",
                f"تم حذف {role.mention} من قائمة الترقيات.",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="promotions", description="عرض قائمة الترقيات")
    async def promotions_command(self, interaction):
        promotions = get_promotions(interaction.guild.id)

        if not promotions:
            return await interaction.response.send_message(
                embed=info_embed("📋 قائمة الترقيات", "مازال ما تضافات حتى رتبة."),
            )

        pages = []
        chunk = []
        for index, promotion in enumerate(promotions, start=1):
            role = interaction.guild.get_role(promotion["role_id"])
            role_text = role.mention if role else f"`Role ID: {promotion['role_id']}`"
            chunk.append(
                f"**{index} — {role_text}**\n"
                f"└ 🏆 `{promotion['required_points']} نقطة`"
            )
            if len(chunk) == 10:
                pages.append(chunk)
                chunk = []
        if chunk:
            pages.append(chunk)

        for page_index, lines in enumerate(pages):
            embed = discord.Embed(
                title="📋 قائمة الترقيات" + (
                    f" — الصفحة {page_index + 1}/{len(pages)}"
                    if len(pages) > 1 else ""
                ),
                description="\n\n".join(lines),
                color=discord.Color.gold(),
            )
            if page_index == len(pages) - 1:
                embed.set_footer(text=f"العدد الكلي: {len(promotions)} رتبة")
            await interaction.response.send_message(embed=embed) if page_index == 0 else await interaction.followup.send(embed=embed)

    @app_commands.command(name="my-rank", description="عرض نقاطك ورتبتك الحالية والقادمة")
    async def my_rank_command(self, interaction, member: discord.Member | None = None):
        member = member or interaction.user
        promotions = get_promotions(interaction.guild.id)

        point_data = get_member_effective_points(
            interaction.guild.id,
            member.id,
            [role.id for role in member.roles],
        )
        earned = point_data["earned_points"]
        base = point_data["base_points"]
        effective = point_data["effective_points"]

        current = None
        upcoming = None
        for promotion in promotions:
            if effective >= promotion["required_points"]:
                current = promotion
            elif upcoming is None:
                upcoming = promotion

        current_text = "لا توجد رتبة مستحقة"
        if current:
            role = interaction.guild.get_role(current["role_id"])
            current_text = role.mention if role else "رتبة محذوفة"

        if upcoming:
            role = interaction.guild.get_role(upcoming["role_id"])
            next_text = role.mention if role else "رتبة محذوفة"
            remaining = max(0, upcoming["required_points"] - effective)
        else:
            next_text = "وصلت لأعلى رتبة"
            remaining = 0

        embed = discord.Embed(
            title="📊 معلومات الترقية",
            description=(
                f"👤 العضو: {member.mention}\n\n"
                f"🏅 نقاط الرتبة الأساسية: **{base}**\n"
                f"🎫 النقاط المكتسبة من التكت: **{earned}**\n"
                f"🏆 النقاط الفعلية: **{effective}**\n\n"
                f"📈 الرتبة الحالية: {current_text}\n"
                f"⬆️ الرتبة القادمة: {next_text}\n"
                f"📌 المتبقي للترقية: **{remaining} نقطة**"
            ),
            color=discord.Color.blue(),
        )
        await interaction.response.send_message(embed=embed)

    @tasks.loop(minutes=5)
    async def autoclose_loop(self):
        for guild in self.bot.guilds:
            config = get_guild_config(guild.id)
            if not config or not config["auto_close_minutes"]:
                continue
            for ticket in get_open_tickets_for_autoclose(guild.id, config["auto_close_minutes"]):
                channel = guild.get_channel(ticket["channel_id"])
                if not channel:
                    update_ticket(ticket["channel_id"], status="closed", closed_at=int(time.time()))
                    continue
                update_ticket(
                    ticket["channel_id"],
                    status="closed",
                    closed_at=int(time.time()),
                    close_reason="إغلاق تلقائي بسبب عدم النشاط",
                )
                try:
                    transcript = await create_transcript(channel)
                    transcript_channel = guild.get_channel(config["transcript_channel_id"]) if config["transcript_channel_id"] else None
                    if transcript_channel:
                        await transcript_channel.send(
                            content=f"⏰ إغلاق تلقائي للتذكرة `{channel.name}`",
                            file=discord.File(
                                __import__("io").BytesIO(transcript.encode()),
                                filename=f"{channel.name}-transcript.html",
                            ),
                        )
                    archive = guild.get_channel(config["archive_category_id"]) if config["archive_category_id"] else None
                    if archive:
                        await channel.edit(category=archive)
                        await channel.send(
                            "⏰ **تم إغلاق وأرشفة هذه التذكرة تلقائياً بسبب عدم النشاط.**",
                            view=ReopenView(),
                        )
                    else:
                        await channel.delete(reason="Auto-close due to inactivity")
                except discord.HTTPException:
                    pass

    @autoclose_loop.before_loop
    async def before_autoclose(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)
    async def sla_loop(self):
        now = int(time.time())
        for guild in self.bot.guilds:
            config = get_guild_config(guild.id)
            if not config or not config["sla_minutes"]:
                continue
            for ticket in get_open_tickets_for_autoclose(guild.id, config["sla_minutes"]):
                if ticket["first_response_at"]:
                    continue
                channel = guild.get_channel(ticket["channel_id"])
                if not channel:
                    continue
                try:
                    await channel.send(
                        f"⚠️ **SLA Alert:** لم يتم تسجيل أول رد على هذه التذكرة خلال {config['sla_minutes']} دقيقة."
                    )
                except discord.HTTPException:
                    pass

    @sla_loop.before_loop
    async def before_sla(self):
        await self.bot.wait_until_ready()




    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        if message.content.strip().lower() not in {"نقاطي", "نقاط الادارة", "نقاط الإدارة"}:
            return
        config = get_guild_config(message.guild.id)
        allowed_id = config["staff_points_channel_id"] if config and config["staff_points_channel_id"] else None
        if allowed_id and message.channel.id != allowed_id:
            return
        await self.send_staff_points_card(message)

    @app_commands.command(name="set-staff-points-channel", description="تحديد قناة استعمال اختصار نقاطي")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="القناة المسموح فيها باستعمال اختصار نقاطي")
    async def set_staff_points_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        set_guild_config(interaction.guild.id, staff_points_channel_id=channel.id)
        await interaction.response.send_message(
            embed=success_embed("تم تحديد قناة نقاط الإدارة", f"اختصار **نقاطي** غادي يخدم غير فـ {channel.mention}."),
            ephemeral=True,
        )

    @app_commands.command(name="clear-staff-points-channel", description="إلغاء تقييد اختصار نقاطي بقناة")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_staff_points_channel(self, interaction: discord.Interaction):
        set_guild_config(interaction.guild.id, staff_points_channel_id=None)
        await interaction.response.send_message(
            embed=success_embed("تم إلغاء التقييد", "اختصار **نقاطي** يقدر يخدم دابا فكل القنوات."),
            ephemeral=True,
        )

    @app_commands.command(name="staff-points-channel", description="عرض قناة اختصار نقاطي")
    async def staff_points_channel(self, interaction: discord.Interaction):
        config = get_guild_config(interaction.guild.id)
        channel_id = config["staff_points_channel_id"] if config and config["staff_points_channel_id"] else None
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        text = f"اختصار **نقاطي** مسموح غير فـ {channel.mention}." if channel else "ماكاين حتى تقييد؛ اختصار **نقاطي** خدام فكل القنوات."
        await interaction.response.send_message(embed=info_embed("📍 قناة نقاط الإدارة", text), ephemeral=True)

    async def send_staff_points_card(self, message: discord.Message):
        guild = message.guild
        member = message.author
        stats = get_staff_points(guild.id, member.id)
        promotions = get_promotions(guild.id)
        point_data = get_member_effective_points(guild.id, member.id, [role.id for role in member.roles])
        effective = point_data["effective_points"]

        current = None
        upcoming = None
        for promotion in promotions:
            if effective >= promotion["required_points"]:
                current = promotion
            elif upcoming is None:
                upcoming = promotion

        current_role = guild.get_role(current["role_id"]) if current else None
        upcoming_role = guild.get_role(upcoming["role_id"]) if upcoming else None
        current_text = current_role.mention if current_role else "بدون رتبة إدارية"
        next_text = upcoming_role.mention if upcoming_role else "وصلت لأعلى رتبة"
        remaining = max(0, upcoming["required_points"] - effective) if upcoming else 0

        embed = discord.Embed(
            title="📊 نقاط الإدارة",
            description=(
                f"{member.mention}\n\n"
                f"🏆 **نقاطك الحالية:** `{effective} نقطة`\n"
                f"🎖️ **رتبتك الحالية:** {current_text}\n"
                f"⬆️ **الرتبة القادمة:** {next_text}\n"
                f"📌 **المتبقي للترقية:** `{remaining} نقطة`\n\n"
                f"🎫 **التذاكر المستلمة:** `{stats['tickets_claimed']} تذكرة`"
            ),
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"نظام الإدارة • {guild.name}")
        await message.channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))

    @app_commands.command(name="staff-points", description="عرض نقاط إداري التذاكر")
    async def staff_points(self, interaction, member: discord.Member | None = None):
        member = member or interaction.user
        stats = get_staff_points(interaction.guild.id, member.id)

        embed = discord.Embed(
            title="🏆 نقاط فريق التذاكر",
            description=(
                f"👤 الإداري: {member.mention}\n"
                f"⭐ مجموع النقاط: **{stats['points']}**\n"
                f"🎫 التذاكر المستلمة: **{stats['tickets_claimed']}**\n"
                f"🌟 نقاط التقييمات: **{stats['rating_points']}**"
            ),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="staff-leaderboard", description="ترتيب إداريي التذاكر حسب النقاط")
    async def staff_leaderboard(self, interaction):
        rows = get_staff_leaderboard(interaction.guild.id, limit=10)

        if not rows:
            return await interaction.response.send_message(
                embed=info_embed("ترتيب الإدارة", "لا توجد نقاط مسجلة حالياً.")
            )

        lines = []
        medals = ["🥇", "🥈", "🥉"]

        for index, row in enumerate(rows):
            member = interaction.guild.get_member(row["user_id"])
            name = member.mention if member else f"<@{row['user_id']}>"
            icon = medals[index] if index < 3 else f"`#{index + 1}`"
            lines.append(
                f"{icon} {name} — **{row['points']} نقطة** "
                f"🎫 {row['tickets_claimed']} | 🌟 {row['rating_points']}"
            )

        embed = discord.Embed(
            title="🏆 ترتيب فريق التذاكر",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="setup", description="إعداد نظام التذاكر")
    @app_commands.describe(
        category="فئة التذاكر",
        support_role="رتبة الدعم",
        archive_category="فئة الأرشيف اختيارية",
        transcript_channel="قناة السجلات اختيارية",
        log_channel="قناة اللوجات اختيارية",
    )
    async def setup(
        self,
        interaction,
        category: discord.CategoryChannel,
        support_role: discord.Role,
        archive_category: discord.CategoryChannel | None = None,
        transcript_channel: discord.TextChannel | None = None,
        log_channel: discord.TextChannel | None = None,
    ):
        if not self.is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("ليس لديك صلاحية Administrator."), ephemeral=True)
        set_guild_config(
            interaction.guild.id,
            category_id=category.id,
            support_role_id=support_role.id,
            archive_category_id=archive_category.id if archive_category else None,
            transcript_channel_id=transcript_channel.id if transcript_channel else None,
            log_channel_id=log_channel.id if log_channel else None,
        )
        await interaction.response.send_message(
            embed=success_embed(
                "تم إعداد النظام",
                f"🎫 التذاكر: {category.mention}\n"
                f"📦 الأرشيف: {archive_category.mention if archive_category else 'غير محدد'}\n"
                f"📄 السجلات: {transcript_channel.mention if transcript_channel else 'غير محددة'}",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="autoclose", description="تفعيل أو تعطيل الإغلاق التلقائي")
    async def autoclose(self, interaction, minutes: app_commands.Range[int, 0, 10080]):
        if not self.is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("ليس لديك صلاحية Administrator."), ephemeral=True)
        set_guild_config(interaction.guild.id, auto_close_minutes=minutes)
        text = "تم تعطيل الإغلاق التلقائي." if minutes == 0 else f"سيتم إغلاق التذاكر بعد {minutes} دقيقة من عدم النشاط."
        await interaction.response.send_message(embed=success_embed("Auto Close", text), ephemeral=True)

    @app_commands.command(name="sla", description="تحديد وقت SLA لأول رد")
    async def sla(self, interaction, minutes: app_commands.Range[int, 0, 10080]):
        if not self.is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("ليس لديك صلاحية Administrator."), ephemeral=True)
        set_guild_config(interaction.guild.id, sla_minutes=minutes)
        text = "تم تعطيل SLA." if minutes == 0 else f"سيتم التنبيه إذا لم يتم تسجيل أول رد خلال {minutes} دقيقة."
        await interaction.response.send_message(embed=success_embed("SLA", text), ephemeral=True)

    @app_commands.command(name="panel", description="إرسال Panel فتح التذاكر")
    async def panel(self, interaction, channel: discord.TextChannel | None = None):
        if not self.is_admin(interaction):
            return await interaction.response.send_message(embed=error_embed("ليس لديك صلاحية Administrator."), ephemeral=True)
        config = get_guild_config(interaction.guild.id)
        if not config or not config["category_id"] or not config["support_role_id"]:
            return await interaction.response.send_message(embed=error_embed("قم بإعداد النظام أولاً باستخدام /setup."), ephemeral=True)
        target = channel or interaction.channel
        embed = discord.Embed(
            title="🎫 الدعم الفني",
            description="مرحباً بك في نظام الدعم الفني.\n\nاختر نوع التذكرة من القائمة بالأسفل لفتح تذكرة جديدة.",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="ArabicTickets • المرحلة الرابعة")
        await target.send(embed=embed, view=TicketPanelView())
        await interaction.response.send_message(embed=success_embed("تم إرسال Panel", f"تم إرسال Panel في {target.mention}."), ephemeral=True)

    @app_commands.command(name="ticket-info", description="عرض معلومات التذكرة الحالية")
    async def ticket_info(self, interaction):
        ticket = get_ticket_by_channel(interaction.channel.id, include_closed=True)
        if not ticket:
            return await interaction.response.send_message(embed=error_embed("هذه القناة ليست تذكرة."), ephemeral=True)
        claimed = f"<@{ticket['claimed_by']}>" if ticket["claimed_by"] else "غير مستلمة"
        await interaction.response.send_message(
            embed=info_embed(
                "معلومات التذكرة",
                f"👤 صاحب التذكرة: <@{ticket['user_id']}>\n"
                f"📁 النوع: `{ticket['ticket_type']}`\n"
                f"📌 الحالة: `{ticket['status']}`\n"
                f"🚦 الأولوية: {priority_label(ticket['priority'] or 'normal')}\n"
                f"🏷️ Tags: {format_tags(ticket['tags'])}\n"
                f"📅 الإنشاء: <t:{ticket['created_at']}:F>\n"
                f"👨‍💼 المستلم: {claimed}\n"
                f"📝 سبب الإغلاق: {ticket['close_reason'] or '—'}",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="priority", description="تحديد أولوية التذكرة")
    @app_commands.choices(priority=[
        app_commands.Choice(name="منخفضة", value="low"),
        app_commands.Choice(name="عادية", value="normal"),
        app_commands.Choice(name="عالية", value="high"),
        app_commands.Choice(name="عاجلة", value="urgent"),
    ])
    async def priority(self, interaction, priority: app_commands.Choice[str]):
        ticket = get_ticket_by_channel(interaction.channel.id, include_closed=True)
        if not ticket or not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message(embed=error_embed("لا يمكنك استخدام هذا الأمر هنا."), ephemeral=True)
        update_ticket(interaction.channel.id, priority=priority.value)
        await interaction.response.send_message(embed=success_embed("تم تحديث الأولوية", priority_label(priority.value)))

    @app_commands.command(name="tag", description="إضافة Tag للتذكرة")
    async def tag(self, interaction, tag: str):
        ticket = get_ticket_by_channel(interaction.channel.id, include_closed=True)
        if not ticket or not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message(embed=error_embed("لا يمكنك استخدام هذا الأمر هنا."), ephemeral=True)
        tags = [x.strip() for x in (ticket["tags"] or "").split(",") if x.strip()]
        if tag not in tags:
            tags.append(tag)
        update_ticket(interaction.channel.id, tags=",".join(tags))
        await interaction.response.send_message(embed=success_embed("تمت إضافة Tag", f"`{tag}`"))

    @app_commands.command(name="untag", description="حذف Tag من التذكرة")
    async def untag(self, interaction, tag: str):
        ticket = get_ticket_by_channel(interaction.channel.id, include_closed=True)
        if not ticket or not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message(embed=error_embed("لا يمكنك استخدام هذا الأمر هنا."), ephemeral=True)
        tags = [x.strip() for x in (ticket["tags"] or "").split(",") if x.strip() and x.strip() != tag]
        update_ticket(interaction.channel.id, tags=",".join(tags))
        await interaction.response.send_message(embed=success_embed("تم حذف Tag", f"`{tag}`"))

    @app_commands.command(name="team", description="تعيين فريق للتذكرة")
    async def team(self, interaction, team: str):
        ticket = get_ticket_by_channel(interaction.channel.id, include_closed=True)
        if not ticket or not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message(embed=error_embed("لا يمكنك استخدام هذا الأمر هنا."), ephemeral=True)
        update_ticket(interaction.channel.id, team=team)
        await interaction.response.send_message(embed=success_embed("تم تعيين الفريق", f"الفريق: `{team}`"))

    @app_commands.command(name="add-member", description="إضافة عضو إلى التذكرة")
    async def add_member(self, interaction, member: discord.Member):
        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket or not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message(embed=error_embed("لا يمكنك استخدام هذا الأمر هنا."), ephemeral=True)
        await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        await interaction.response.send_message(embed=success_embed("تمت الإضافة", f"تمت إضافة {member.mention} إلى التذكرة."))

    @app_commands.command(name="remove-member", description="إزالة عضو من التذكرة")
    async def remove_member(self, interaction, member: discord.Member):
        ticket = get_ticket_by_channel(interaction.channel.id)
        if not ticket or not interaction.user.guild_permissions.manage_channels:
            return await interaction.response.send_message(embed=error_embed("لا يمكنك استخدام هذا الأمر هنا."), ephemeral=True)
        if member.id == ticket["user_id"]:
            return await interaction.response.send_message(embed=error_embed("لا يمكن إزالة صاحب التذكرة."), ephemeral=True)
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(embed=success_embed("تمت الإزالة", f"تمت إزالة {member.mention} من التذكرة."))

    @app_commands.command(name="stats", description="إحصائيات التذاكر")
    async def stats(self, interaction):
        await interaction.response.send_message(
            embed=info_embed(
                "إحصائيات المرحلة الرابعة",
                "📊 النظام يدعم الآن Priority وTags وTeams وSLA وAuto Close.\n"
                "سيتم توسيع Analytics التفصيلية في المرحلة الخامسة.",
            ),
            ephemeral=True,
        )

    async def create_ticket_channel(self, interaction, ticket_type, reason, details):
        config = get_guild_config(interaction.guild.id)
        category = interaction.guild.get_channel(config["category_id"])
        support_role = interaction.guild.get_role(config["support_role_id"])
        if not category or not support_role:
            return await interaction.followup.send(embed=error_embed("إعدادات التذاكر غير مكتملة. استخدم /setup."), ephemeral=True)
        existing = get_open_ticket_for_user(interaction.guild.id, interaction.user.id)
        if existing:
            channel = interaction.guild.get_channel(existing["channel_id"])
            return await interaction.followup.send(embed=error_embed(f"لديك تذكرة مفتوحة بالفعل: {channel.mention if channel else 'تذكرة قديمة'}"), ephemeral=True)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
            support_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True),
        }
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}".lower()[:90],
            category=category,
            overwrites=overwrites,
            topic=f"ArabicTickets | {ticket_type} | {interaction.user.id}",
        )
        ticket_id = create_ticket(interaction.guild.id, channel.id, interaction.user.id, ticket_type)
        embed = discord.Embed(
            title=f"🎫 تذكرة {ticket_type}",
            description=f"مرحباً {interaction.user.mention}!\n\n**سبب فتح التذكرة:**\n{reason}\n\n**تفاصيل إضافية:**\n{details}\n\nسيقوم فريق الدعم بالرد عليك قريباً.",
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Ticket ID: {ticket_id}")
        await channel.send(content=f"{interaction.user.mention} {support_role.mention}", embed=embed, view=TicketControlView())
        success_message = success_embed(
            "تم إنشاء التذكرة",
            f"تم فتح تذكرتك: {channel.mention}",
        )

        # Modal interactions may not have an active followup webhook unless
        # they were acknowledged first. Respond directly when possible.
        if interaction.response.is_done():
            await interaction.followup.send(
                embed=success_message,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=success_message,
                ephemeral=True,
            )

async def setup(bot):
    await bot.add_cog(Tickets(bot))

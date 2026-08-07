import asyncio
import time

import discord
from discord import app_commands
from discord.ext import commands

from database.db import (
    add_shortcut_log,
    add_staff_points,
    get_guild_config,
    get_shortcut_setting,
    get_ticket_by_channel,
    update_shortcut_setting,
    update_ticket,
)
from utils.embeds import error_embed, info_embed, success_embed


SHORTCUT_CHOICES = [
    app_commands.Choice(name="2خلصت", value="done"),
    app_commands.Choice(name="خمول", value="idle"),
    app_commands.Choice(name="مطلوب عليا", value="need_staff"),
    app_commands.Choice(name="مرحبا", value="welcome"),
]


class Shortcuts(commands.Cog):
    """Advanced ticket shortcuts that only run inside open ticket channels."""

    DEFAULT_XP = 1
    DEFAULT_COOLDOWN = 30
    DEFAULT_COLORS = {
        "done": 0x2ECC71,
        "idle": 0xF1C40F,
        "need_staff": 0xE67E22,
        "welcome": 0x3498DB,
    }
    DEFAULT_MESSAGES = {
        "done": "✅ تم الانتهاء من طلبك. إذا احتجت أي شيء إضافي يمكنك الرد هنا قبل إغلاق التذكرة.",
        "idle": "⏳ تم وضع علامة خمول على هذه التذكرة بسبب عدم وجود تفاعل كافٍ.",
        "need_staff": "📣 يوجد طلب مساعدة من Staff داخل هذه التذكرة.",
        "need_user": "📌 تم طلب حضورك داخل هذه التذكرة.",
        "welcome": "👋 مرحباً بك! يسعدنا مساعدتك، الرجاء توضيح طلبك وسيقوم الفريق بالرد عليك قريباً.",
    }
    TRIGGERS = {
        "2خلصت": "done",
        "خمول": "idle",
        "مطلوب عليا": "need_staff",
        "مطلوب علياء": "need_staff",
        "مرحبا": "welcome",
    }

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cooldowns: dict[tuple[int, int, str], float] = {}
        self.reminder_tasks: dict[tuple[int, int], asyncio.Task] = {}

    def cog_unload(self):
        for task in self.reminder_tasks.values():
            task.cancel()

    @staticmethod
    def _role_ids_from_setting(value: str | None) -> list[int]:
        if not value:
            return []
        return [int(role_id) for role_id in value.split(",") if role_id.strip().isdigit()]

    @staticmethod
    def _roles_to_csv(*roles: discord.Role | None) -> str | None:
        role_ids = [str(role.id) for role in roles if role is not None]
        return ",".join(role_ids) if role_ids else None

    @staticmethod
    def _clean_content(content: str) -> str:
        return " ".join(content.strip().split())

    @staticmethod
    def _parse_color(value: str | None, fallback: int) -> int:
        if not value:
            return fallback
        cleaned = value.strip().removeprefix("#").removeprefix("0x")
        try:
            parsed = int(cleaned, 16)
        except ValueError:
            return fallback
        return parsed if 0 <= parsed <= 0xFFFFFF else fallback

    def _match_shortcut(self, content: str) -> tuple[str | None, discord.Member | None]:
        cleaned = self._clean_content(content)
        if cleaned in {"2خلصت", "خمول", "مرحبا", "مطلوب عليا", "مطلوب علياء"}:
            return self.TRIGGERS[cleaned], None
        for prefix in ("مطلوب عليا", "مطلوب علياء", "مرحبا"):
            if cleaned.startswith(prefix + " "):
                return self.TRIGGERS[prefix], None
        return None, None

    def _extract_mentioned_member(self, message: discord.Message) -> discord.Member | None:
        return message.mentions[0] if message.mentions else None

    def _staff_role_ids(self, guild_id: int, setting: dict) -> list[int]:
        configured = self._role_ids_from_setting(setting.get("allowed_roles"))
        if configured:
            return configured
        config = get_guild_config(guild_id)
        support_role_id = config["support_role_id"] if config and config["support_role_id"] else None
        return [int(support_role_id)] if support_role_id else []

    def _can_use_shortcut(self, member: discord.Member, setting: dict) -> bool:
        if member.guild_permissions.manage_channels:
            return True
        role_ids = set(self._staff_role_ids(member.guild.id, setting))
        return bool(role_ids and any(role.id in role_ids for role in member.roles))

    def _is_channel_allowed(self, channel_id: int, setting: dict) -> bool:
        configured_channel = setting.get("channel_id")
        return configured_channel in (None, 0) or int(configured_channel) == channel_id

    def _cooldown_ready(self, guild_id: int, user_id: int, shortcut_name: str, cooldown: int) -> bool:
        if cooldown <= 0:
            return True
        key = (guild_id, user_id, shortcut_name)
        now = time.monotonic()
        last_used = self.cooldowns.get(key, 0)
        if now - last_used < cooldown:
            return False
        self.cooldowns[key] = now
        return True

    async def _send_ticket_log(self, guild: discord.Guild, *, title: str, description: str, color: int) -> None:
        config = get_guild_config(guild.id)
        channel_id = config["log_channel_id"] if config and config["log_channel_id"] else None
        channel = guild.get_channel(channel_id) if channel_id else None
        if not isinstance(channel, discord.TextChannel):
            return
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        embed.set_footer(text=f"Ticket Shortcuts • {guild.name}")
        try:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
        except (discord.Forbidden, discord.HTTPException):
            return

    async def _award_shortcut_xp(self, message: discord.Message) -> None:
        stats = add_staff_points(message.guild.id, message.author.id, self.DEFAULT_XP, source="shortcut")
        tickets_cog = self.bot.get_cog("Tickets")
        if tickets_cog and hasattr(tickets_cog, "apply_promotion"):
            await tickets_cog.apply_promotion(message.guild, message.author, stats["points"])

    def _make_embed(self, title: str, description: str, color: int, author: discord.Member) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color, timestamp=discord.utils.utcnow())
        embed.set_footer(text=f"بواسطة {author.display_name}")
        embed.set_thumbnail(url=author.display_avatar.url)
        return embed

    async def _handle_done(self, message: discord.Message, ticket, setting: dict) -> None:
        color = int(setting.get("embed_color") or self.DEFAULT_COLORS["done"])
        text = setting.get("message") or self.DEFAULT_MESSAGES["done"]
        embed = self._make_embed("✅ تم إنهاء الطلب", text, color, message.author)
        await message.channel.send(content=f"<@{ticket['user_id']}>", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        auto_close = bool(setting.get("auto_close"))
        if auto_close:
            update_ticket(message.channel.id, status="closed", closed_at=int(time.time()), close_reason="تم الإغلاق تلقائياً عبر اختصار 2خلصت")
        await self._log_action(message, ticket, "done", "استخدم اختصار 2خلصت", color, extra=f"الإغلاق التلقائي: {'مفعل' if auto_close else 'غير مفعل'}")

    async def _handle_idle(self, message: discord.Message, ticket, setting: dict) -> None:
        now = int(time.time())
        color = int(setting.get("embed_color") or self.DEFAULT_COLORS["idle"])
        text = setting.get("message") or self.DEFAULT_MESSAGES["idle"]
        reminder_minutes = int(setting.get("reminder_minutes") or 0)
        reminder_text = f"\n🔔 سيتم التذكير بعد `{reminder_minutes}` دقيقة." if reminder_minutes > 0 else ""
        embed = self._make_embed("⏳ تذكرة خاملة", f"{text}\n\n🕒 وقت التسجيل: <t:{now}:F>{reminder_text}", color, message.author)
        await message.channel.send(content=f"<@{ticket['user_id']}>", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        update_ticket(message.channel.id, last_activity_at=now)
        if reminder_minutes > 0:
            self._schedule_idle_reminder(message.channel, ticket["user_id"], reminder_minutes, color)
        await self._log_action(message, ticket, "idle", "استخدم اختصار خمول", color, extra=f"وقت الخمول: <t:{now}:F>")

    def _schedule_idle_reminder(self, channel: discord.TextChannel, owner_id: int, minutes: int, color: int) -> None:
        key = (channel.guild.id, channel.id)
        old_task = self.reminder_tasks.pop(key, None)
        if old_task:
            old_task.cancel()
        self.reminder_tasks[key] = asyncio.create_task(self._idle_reminder_task(channel, owner_id, minutes, color, key))

    async def _idle_reminder_task(self, channel: discord.TextChannel, owner_id: int, minutes: int, color: int, key: tuple[int, int]) -> None:
        try:
            await asyncio.sleep(minutes * 60)
            if not get_ticket_by_channel(channel.id):
                return
            embed = discord.Embed(
                title="🔔 تذكير تذكرة خاملة",
                description="هذه التذكرة مازالت خاملة وتحتاج متابعة من الفريق أو صاحب التذكرة.",
                color=color,
                timestamp=discord.utils.utcnow(),
            )
            await channel.send(content=f"<@{owner_id}>", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except asyncio.CancelledError:
            return
        except (discord.Forbidden, discord.HTTPException):
            return
        finally:
            self.reminder_tasks.pop(key, None)

    async def _handle_need_staff(self, message: discord.Message, ticket, setting: dict) -> None:
        color = int(setting.get("embed_color") or self.DEFAULT_COLORS["need_staff"])
        mentioned = self._extract_mentioned_member(message)
        if mentioned:
            text = setting.get("message") or self.DEFAULT_MESSAGES["need_user"]
            content = mentioned.mention
            description = f"{text}\n\n👤 العضو المطلوب: {mentioned.mention}\n🛡️ تم الطلب بواسطة: {message.author.mention}"
            allowed_mentions = discord.AllowedMentions(users=True, roles=False, everyone=False)
            extra = f"العضو المطلوب: {mentioned.id}"
        else:
            text = setting.get("message") or self.DEFAULT_MESSAGES["need_staff"]
            role_mentions = []
            for role_id in self._staff_role_ids(message.guild.id, setting):
                role = message.guild.get_role(role_id)
                if role:
                    role_mentions.append(role.mention)
            content = " ".join(role_mentions) if role_mentions else None
            description = f"{text}\n\n🛡️ تم الطلب بواسطة: {message.author.mention}"
            allowed_mentions = discord.AllowedMentions(users=False, roles=True, everyone=False)
            extra = f"الرتب المطلوبة: {', '.join(str(r) for r in self._staff_role_ids(message.guild.id, setting)) or 'غير محددة'}"
        embed = self._make_embed("📣 مطلوب مساعدة", description, color, message.author)
        await message.channel.send(content=content, embed=embed, allowed_mentions=allowed_mentions)
        await self._log_action(message, ticket, "need_staff", "استخدم اختصار مطلوب عليا", color, extra=extra)

    async def _handle_welcome(self, message: discord.Message, ticket, setting: dict) -> None:
        color = int(setting.get("embed_color") or self.DEFAULT_COLORS["welcome"])
        text = setting.get("message") or self.DEFAULT_MESSAGES["welcome"]
        mentioned = self._extract_mentioned_member(message)
        target = mentioned or message.guild.get_member(ticket["user_id"])
        content = target.mention if target else f"<@{ticket['user_id']}>"
        embed = self._make_embed("👋 مرحباً", text, color, message.author)
        await message.channel.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        await self._log_action(message, ticket, "welcome", "استخدم اختصار مرحبا", color, extra=f"المستهدف: {target.id if target else ticket['user_id']}")

    async def _log_action(self, message: discord.Message, ticket, shortcut_name: str, action: str, color: int, extra: str = "") -> None:
        add_shortcut_log(message.guild.id, message.channel.id, ticket["id"], message.author.id, shortcut_name, action, extra)
        await self._send_ticket_log(
            message.guild,
            title="🧩 Ticket Shortcut Log",
            description=(
                f"🎫 التذكرة: {message.channel.mention}\n"
                f"👤 المستخدم: {message.author.mention}\n"
                f"⌨️ الاختصار: `{shortcut_name}`\n"
                f"📝 الحدث: {action}\n"
                f"{extra}"
            ),
            color=color,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None or not isinstance(message.author, discord.Member):
            return

        shortcut_name, _ = self._match_shortcut(message.content)
        if shortcut_name is None:
            return

        ticket = get_ticket_by_channel(message.channel.id)
        if not ticket:
            return

        setting = get_shortcut_setting(message.guild.id, shortcut_name)
        if not setting.get("enabled", True):
            return
        if not self._is_channel_allowed(message.channel.id, setting):
            return
        if not self._can_use_shortcut(message.author, setting):
            return
        cooldown = int(setting.get("cooldown") or self.DEFAULT_COOLDOWN)
        if not self._cooldown_ready(message.guild.id, message.author.id, shortcut_name, cooldown):
            return

        handlers = {
            "done": self._handle_done,
            "idle": self._handle_idle,
            "need_staff": self._handle_need_staff,
            "welcome": self._handle_welcome,
        }
        await handlers[shortcut_name](message, ticket, setting)
        await self._award_shortcut_xp(message)

    @app_commands.command(name="shortcut-settings", description="تعديل إعدادات اختصار تذاكر")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(shortcut=SHORTCUT_CHOICES)
    async def shortcut_settings(
        self,
        interaction: discord.Interaction,
        shortcut: app_commands.Choice[str],
        enabled: bool | None = None,
        channel: discord.TextChannel | None = None,
        message: str | None = None,
        embed_color: str | None = None,
        cooldown: app_commands.Range[int, 0, 86400] | None = None,
        auto_close: bool | None = None,
        reminder_minutes: app_commands.Range[int, 0, 10080] | None = None,
        role_1: discord.Role | None = None,
        role_2: discord.Role | None = None,
        role_3: discord.Role | None = None,
    ):
        current = get_shortcut_setting(interaction.guild.id, shortcut.value)
        color = self._parse_color(embed_color, int(current.get("embed_color") or self.DEFAULT_COLORS[shortcut.value])) if embed_color else None
        roles_csv = self._roles_to_csv(role_1, role_2, role_3)
        fields = {}
        if enabled is not None:
            fields["enabled"] = 1 if enabled else 0
        if channel is not None:
            fields["channel_id"] = channel.id
        if roles_csv is not None:
            fields["allowed_roles"] = roles_csv
        if message is not None:
            fields["message"] = message
        if color is not None:
            fields["embed_color"] = color
        if cooldown is not None:
            fields["cooldown"] = int(cooldown)
        if auto_close is not None:
            fields["auto_close"] = 1 if auto_close else 0
        if reminder_minutes is not None:
            fields["reminder_minutes"] = int(reminder_minutes)
        if not fields:
            return await interaction.response.send_message(embed=error_embed("حدد إعداداً واحداً على الأقل لتعديله."), ephemeral=True)
        updated = update_shortcut_setting(interaction.guild.id, shortcut.value, **fields)
        role_text = updated.get("allowed_roles") or "Support Role الافتراضية"
        await interaction.response.send_message(
            embed=success_embed(
                "تم حفظ إعدادات الاختصار",
                f"⌨️ الاختصار: `{shortcut.name}`\n"
                f"✅ مفعل: `{bool(updated['enabled'])}`\n"
                f"📍 القناة: {f'<#{updated['channel_id']}>' if updated.get('channel_id') else 'أي قناة Ticket'}\n"
                f"🛡️ الرتب: `{role_text}`\n"
                f"🎨 اللون: `#{int(updated['embed_color']):06X}`\n"
                f"⏳ الكولداون: `{updated['cooldown']}` ثانية\n"
                f"🔒 إغلاق تلقائي: `{bool(updated.get('auto_close'))}`\n"
                f"🔔 Reminder: `{updated.get('reminder_minutes') or 0}` دقيقة",
            ),
            ephemeral=True,
        )

    @app_commands.command(name="shortcut-info", description="عرض إعدادات اختصار تذاكر")
    @app_commands.choices(shortcut=SHORTCUT_CHOICES)
    async def shortcut_info(self, interaction: discord.Interaction, shortcut: app_commands.Choice[str]):
        setting = get_shortcut_setting(interaction.guild.id, shortcut.value)
        roles = self._role_ids_from_setting(setting.get("allowed_roles"))
        roles_text = ", ".join(f"<@&{role_id}>" for role_id in roles) if roles else "Support Role الافتراضية"
        await interaction.response.send_message(
            embed=info_embed(
                "إعدادات الاختصار",
                f"⌨️ الاختصار: `{shortcut.name}`\n"
                f"✅ مفعل: `{bool(setting['enabled'])}`\n"
                f"📍 القناة: {f'<#{setting['channel_id']}>' if setting.get('channel_id') else 'أي قناة Ticket'}\n"
                f"🛡️ الرتب: {roles_text}\n"
                f"💬 الرسالة: {setting.get('message') or 'الرسالة الافتراضية'}\n"
                f"🎨 اللون: `#{int(setting['embed_color']):06X}`\n"
                f"⏳ الكولداون: `{setting['cooldown']}` ثانية\n"
                f"🔒 إغلاق تلقائي: `{bool(setting.get('auto_close'))}`\n"
                f"🔔 Reminder: `{setting.get('reminder_minutes') or 0}` دقيقة",
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Shortcuts(bot))

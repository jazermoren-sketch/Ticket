import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

from database.db import init_db
from cogs.tickets import Tickets
from cogs.staff_xp import StaffXP
from cogs.staff_warnings import StaffWarnings
from cogs.shortcuts import Shortcuts
from cogs.staff import Staff

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

class ArabicTickets(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        init_db()
        await self.add_cog(Tickets(self))
        await self.add_cog(StaffXP(self))
        await self.add_cog(StaffWarnings(self))
        await self.add_cog(Shortcuts(self))
        await self.add_cog(Staff(self))
        synced = await self.tree.sync()
        print(f"تم تسجيل {len(synced)} أمر Slash.")

    async def on_ready(self):
        print(f"تم تشغيل البوت: {self.user} ({self.user.id})")

    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        from database.db import get_ticket_by_channel, update_ticket
        ticket = get_ticket_by_channel(message.channel.id)
        if ticket:
            now = int(__import__("time").time())
            fields = {"last_activity_at": now}
            if message.author.id != ticket["user_id"] and not ticket["first_response_at"]:
                fields["first_response_at"] = now
            update_ticket(message.channel.id, **fields)

        await self.process_commands(message)

bot = ArabicTickets()

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN غير موجود. أضفه في Quaxly داخل Environment Variables "
        "بالاسم DISCORD_TOKEN، ثم احفظ الإعدادات وأعد تشغيل البوت."
    )

TOKEN = TOKEN.strip()

if __name__ == "__main__":
    bot.run(TOKEN, log_handler=None)

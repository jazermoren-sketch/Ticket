import discord

class TicketForm(discord.ui.Modal, title="📋 معلومات التذكرة"):
    reason = discord.ui.TextInput(
        label="ما هو سبب فتح التذكرة؟",
        placeholder="اكتب سبب فتح التذكرة بالتفصيل...",
        style=discord.TextStyle.paragraph,
        min_length=3,
        max_length=1000,
        required=True,
    )

    details = discord.ui.TextInput(
        label="تفاصيل إضافية",
        placeholder="اكتب أي معلومات إضافية تساعد فريق الدعم...",
        style=discord.TextStyle.paragraph,
        max_length=1500,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Tickets")
        await cog.create_ticket_channel(
            interaction,
            self.ticket_type,
            self.reason.value,
            self.details.value or "لا توجد تفاصيل إضافية.",
        )

    def __init__(self, ticket_type):
        super().__init__()
        self.ticket_type = ticket_type

import discord
from ui.forms import TicketForm

class TicketTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="دعم فني", value="دعم فني", emoji="🛠️", description="للمشاكل والاستفسارات التقنية"),
            discord.SelectOption(label="شراء", value="شراء", emoji="💰", description="للاستفسار عن المنتجات أو الشراء"),
            discord.SelectOption(label="شكوى", value="شكوى", emoji="🚨", description="لتقديم شكوى للإدارة"),
            discord.SelectOption(label="شراكة", value="شراكة", emoji="🤝", description="لطلب شراكة أو تعاون"),
        ]
        super().__init__(placeholder="اختر نوع التذكرة...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketForm(self.values[0]))

class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())

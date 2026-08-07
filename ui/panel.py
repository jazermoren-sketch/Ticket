import discord

from ui.forms import TicketForm
from database.panels import get_panel


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


class CustomTicketPanelButton(discord.ui.Button):
    def __init__(self, panel_id: int, emoji: str, label: str, style: discord.ButtonStyle):
        super().__init__(
            style=style,
            label=label[:80],
            emoji=emoji or None,
            custom_id=f"ticket_panel:{panel_id}",
        )
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):
        panel = get_panel(self.panel_id)
        if not panel or panel['guild_id'] != interaction.guild_id:
            return await interaction.response.send_message(
                "❌ هاد الـ Panel ما بقاش متوفر.", ephemeral=True
            )
        await interaction.response.send_modal(
            TicketForm(panel.get('ticket_type') or panel['name'])
        )


class CustomTicketPanelView(discord.ui.View):
    def __init__(self, panel):
        super().__init__(timeout=None)
        style_value = int(panel.get('button_style') or 1)
        try:
            style = discord.ButtonStyle(style_value)
        except ValueError:
            style = discord.ButtonStyle.primary
        self.add_item(
            CustomTicketPanelButton(
                panel_id=int(panel['id']),
                emoji=panel.get('emoji') or '',
                label=panel.get('button_label') or 'فتح تذكرة',
                style=style,
            )
        )


def build_custom_panel_embed(panel):
    title = panel.get('embed_title') or panel.get('name') or '🎫 فتح تذكرة'
    description = panel.get('embed_description') or panel.get('description') or ''
    color_value = int(panel.get('embed_color') or 5793266)
    embed = discord.Embed(title=title[:256], description=description[:4096], color=color_value)
    if panel.get('name') and panel.get('description') and not panel.get('embed_description'):
        embed.set_footer(text=panel['name'][:2048])
    return embed

import discord
from discord import app_commands
from discord.ext import commands

from database.db import get_guild_config
from database.panels import create_panels_table, create_panel, get_panel, get_panels, update_panel, delete_panel
from ui.panel import CustomTicketPanelView, build_custom_panel_embed


class PanelCreateModal(discord.ui.Modal):
    def __init__(self, existing=None):
        self.existing = existing
        super().__init__(title='تخصيص Ticket Panel' if existing else 'إنشاء Ticket Panel')
        self.name_input = discord.ui.TextInput(label='اسم الـ Panel', default=(existing or {}).get('name', ''), max_length=80, required=True)
        self.emoji_input = discord.ui.TextInput(label='الإيموجي', default=(existing or {}).get('emoji', '🎫'), max_length=10, required=False)
        self.description_input = discord.ui.TextInput(label='الوصف (اختياري)', default=(existing or {}).get('description', ''), style=discord.TextStyle.paragraph, max_length=1000, required=False)
        self.title_input = discord.ui.TextInput(label='عنوان الـ Embed (اختياري)', default=(existing or {}).get('embed_title', ''), max_length=256, required=False)
        self.embed_description_input = discord.ui.TextInput(label='نص الـ Embed (اختياري)', default=(existing or {}).get('embed_description', ''), style=discord.TextStyle.paragraph, max_length=4000, required=False)
        for item in (self.name_input, self.emoji_input, self.description_input, self.title_input, self.embed_description_input):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        data = {
            'name': self.name_input.value.strip(),
            'emoji': self.emoji_input.value.strip() or '🎫',
            'description': self.description_input.value.strip(),
            'embed_title': self.title_input.value.strip(),
            'embed_description': self.embed_description_input.value.strip(),
        }
        if self.existing:
            panel = update_panel(self.existing['id'], interaction.guild.id, **data)
            text = '✅ تم تعديل الـ Panel.'
        else:
            config = get_guild_config(interaction.guild.id)
            panel = create_panel(
                interaction.guild.id,
                data.pop('name'),
                interaction.user.id,
                **data,
                category_id=config['category_id'] if config else None,
                support_role_id=config['support_role_id'] if config else None,
            )
            text = '✅ تم إنشاء الـ Panel.'
        await interaction.response.send_message(content=text, embed=build_custom_panel_embed(panel), view=CustomTicketPanelView(panel), ephemeral=True)


class PanelCog(commands.Cog):
    """Custom Ticket Panel Builder."""

    ticket = app_commands.Group(name='ticket', description='إدارة نظام التكتات والـ Panels')
    panel = app_commands.Group(name='panel', description='إنشاء وتخصيص Ticket Panels', parent=ticket)

    def __init__(self, bot):
        self.bot = bot
        create_panels_table()

    async def register_persistent_views(self):
        for guild in self.bot.guilds:
            for panel in get_panels(guild.id):
                try:
                    self.bot.add_view(CustomTicketPanelView(panel))
                except (discord.HTTPException, ValueError):
                    pass

    @panel.command(name='create', description='إنشاء Ticket Panel مخصص')
    @app_commands.checks.has_permissions(administrator=True)
    async def panel_create(self, interaction: discord.Interaction):
        await interaction.response.send_modal(PanelCreateModal())

    @panel.command(name='edit', description='تعديل Ticket Panel موجود')
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(panel_id='رقم الـ Panel')
    async def panel_edit(self, interaction: discord.Interaction, panel_id: int):
        panel = get_panel(panel_id)
        if not panel or panel['guild_id'] != interaction.guild.id:
            return await interaction.response.send_message('❌ الـ Panel غير موجود.', ephemeral=True)
        await interaction.response.send_modal(PanelCreateModal(panel))

    @panel.command(name='delete', description='حذف Ticket Panel')
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(panel_id='رقم الـ Panel')
    async def panel_delete(self, interaction: discord.Interaction, panel_id: int):
        if not delete_panel(panel_id, interaction.guild.id):
            return await interaction.response.send_message('❌ الـ Panel غير موجود.', ephemeral=True)
        await interaction.response.send_message('🗑️ تم حذف الـ Panel بنجاح.', ephemeral=True)

    @panel.command(name='list', description='عرض جميع Ticket Panels')
    async def panel_list(self, interaction: discord.Interaction):
        panels = get_panels(interaction.guild.id)
        if not panels:
            return await interaction.response.send_message('📋 ما كاين حتى Panel مخصص حالياً.', ephemeral=True)
        lines = [f"**#{p['id']}** {p['emoji']} **{p['name']}** — زر: `{p['button_label']}`" for p in panels]
        embed = discord.Embed(title='🎫 Ticket Panels', description='\n'.join(lines), color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @panel.command(name='preview', description='معاينة Ticket Panel')
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(panel_id='رقم الـ Panel')
    async def panel_preview(self, interaction: discord.Interaction, panel_id: int):
        panel = get_panel(panel_id)
        if not panel or panel['guild_id'] != interaction.guild.id:
            return await interaction.response.send_message('❌ الـ Panel غير موجود.', ephemeral=True)
        await interaction.response.send_message(embed=build_custom_panel_embed(panel), view=CustomTicketPanelView(panel), ephemeral=True)

    @panel.command(name='send', description='إرسال Ticket Panel إلى قناة')
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(panel_id='رقم الـ Panel', channel='القناة التي سيتم إرسال الـ Panel فيها')
    async def panel_send(self, interaction: discord.Interaction, panel_id: int, channel: discord.TextChannel):
        panel = get_panel(panel_id)
        if not panel or panel['guild_id'] != interaction.guild.id:
            return await interaction.response.send_message('❌ الـ Panel غير موجود.', ephemeral=True)
        await channel.send(embed=build_custom_panel_embed(panel), view=CustomTicketPanelView(panel))
        await interaction.response.send_message(f'✅ تم إرسال **{panel["name"]}** إلى {channel.mention}.', ephemeral=True)

    @panel.command(name='configure', description='تخصيص Category وStaff Role والزر والـ Embed')
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        panel_id='رقم الـ Panel',
        category='Category التي ستوضع فيها التذاكر',
        staff_role='Role الذي سيملك صلاحية التذاكر',
        button_label='اسم الزر (اختياري)',
        ticket_name='اسم التكت: {username} و {display_name} و {id}',
        embed_color='لون الـ Embed بصيغة HEX بدون #، مثال: 5865F2',
        button_style='1=Primary، 2=Secondary، 3=Success، 4=Danger',
    )
    async def panel_configure(
        self,
        interaction: discord.Interaction,
        panel_id: int,
        category: discord.CategoryChannel | None = None,
        staff_role: discord.Role | None = None,
        button_label: str | None = None,
        ticket_name: str | None = None,
        embed_color: str | None = None,
        button_style: app_commands.Range[int, 1, 4] | None = None,
    ):
        panel = get_panel(panel_id)
        if not panel or panel['guild_id'] != interaction.guild.id:
            return await interaction.response.send_message('❌ الـ Panel غير موجود.', ephemeral=True)
        changes = {}
        if category is not None:
            changes['category_id'] = category.id
        if staff_role is not None:
            changes['support_role_id'] = staff_role.id
        if button_label is not None:
            changes['button_label'] = button_label[:80]
        if ticket_name is not None:
            changes['ticket_name'] = ticket_name[:90]
        if embed_color is not None:
            raw = embed_color.strip().removeprefix('#')
            try:
                if len(raw) != 6:
                    raise ValueError
                changes['embed_color'] = int(raw, 16)
            except ValueError:
                return await interaction.response.send_message('❌ لون HEX غير صالح. مثال: `5865F2`.', ephemeral=True)
        if button_style is not None:
            changes['button_style'] = int(button_style)
        panel = update_panel(panel_id, interaction.guild.id, **changes)
        await interaction.response.send_message(content='✅ تم تحديث إعدادات الـ Panel.', embed=build_custom_panel_embed(panel), view=CustomTicketPanelView(panel), ephemeral=True)

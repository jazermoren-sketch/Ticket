import discord

from database.db import get_open_ticket_for_user
from database.panels import get_panel


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

    def __init__(self, ticket_type, panel_id=None):
        super().__init__()
        self.ticket_type = ticket_type
        self.panel_id = panel_id

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Tickets")
        if cog is None:
            return await interaction.response.send_message(
                "❌ نظام التكت غير متوفر حالياً.", ephemeral=True
            )

        await cog.create_ticket_channel(
            interaction,
            self.ticket_type,
            self.reason.value,
            self.details.value or "لا توجد تفاصيل إضافية.",
        )

        # Apply panel-specific channel settings after the existing ticket
        # creation flow succeeds. This keeps old tickets compatible.
        if self.panel_id:
            panel = get_panel(self.panel_id)
            if not panel:
                return
            ticket = get_open_ticket_for_user(interaction.guild.id, interaction.user.id)
            if not ticket:
                return
            channel = interaction.guild.get_channel(ticket["channel_id"])
            if not channel:
                return

            edits = {}
            category_id = panel.get("category_id")
            category = interaction.guild.get_channel(category_id) if category_id else None
            if isinstance(category, discord.CategoryChannel) and channel.category_id != category.id:
                edits["category"] = category

            ticket_name = panel.get("ticket_name") or "ticket-{username}"
            safe_name = ticket_name.replace("{username}", interaction.user.name).replace(
                "{display_name}", interaction.user.display_name
            ).replace("{id}", str(interaction.user.id))
            safe_name = safe_name.lower().replace(" ", "-")[:100]
            if safe_name:
                edits["name"] = safe_name

            if edits:
                try:
                    await channel.edit(**edits, reason="Custom Ticket Panel configuration")
                except (discord.Forbidden, discord.HTTPException):
                    pass

            support_role_id = panel.get("support_role_id")
            support_role = interaction.guild.get_role(support_role_id) if support_role_id else None
            if support_role:
                try:
                    await channel.set_permissions(
                        support_role,
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        reason="Custom Ticket Panel staff access",
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass

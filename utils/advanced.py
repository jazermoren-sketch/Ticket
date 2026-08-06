import discord
from database.db import get_ticket_by_channel, update_ticket

PRIORITIES = {
    "low": "🟢 منخفضة",
    "normal": "🔵 عادية",
    "high": "🟠 عالية",
    "urgent": "🔴 عاجلة",
}

def priority_label(value):
    return PRIORITIES.get(value, value)

def parse_tags(value):
    return [x.strip() for x in (value or "").split(",") if x.strip()]

def format_tags(value):
    tags = parse_tags(value)
    return ", ".join(f"`{tag}`" for tag in tags) if tags else "لا توجد"

async def set_priority(interaction, priority):
    ticket = get_ticket_by_channel(interaction.channel.id, include_closed=True)
    if not ticket:
        return await interaction.response.send_message("هذه القناة ليست تذكرة.", ephemeral=True)
    if not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message("لا تملك الصلاحية.", ephemeral=True)
    update_ticket(interaction.channel.id, priority=priority)
    await interaction.response.send_message(f"تم تعيين الأولوية: **{priority_label(priority)}**")

async def set_tags(interaction, tags):
    ticket = get_ticket_by_channel(interaction.channel.id, include_closed=True)
    if not ticket:
        return await interaction.response.send_message("هذه القناة ليست تذكرة.", ephemeral=True)
    if not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message("لا تملك الصلاحية.", ephemeral=True)
    update_ticket(interaction.channel.id, tags=",".join(tags))
    await interaction.response.send_message(f"تم تحديث Tags: {format_tags(','.join(tags))}")

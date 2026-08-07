import discord

from database.db import get_guild_config


async def log_event(guild: discord.Guild, title: str, description: str, *, color: discord.Color | None = None):
    config = get_guild_config(guild.id)
    channel_id = config["log_channel_id"] if config and config["log_channel_id"] else None
    channel = guild.get_channel(channel_id) if channel_id else None
    if not isinstance(channel, discord.TextChannel):
        return False
    embed = discord.Embed(
        title=title,
        description=description,
        color=color or discord.Color.blurple(),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_footer(text=f"ArabicTickets Ultimate • {guild.name}")
    try:
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False

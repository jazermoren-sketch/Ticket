import discord

def success_embed(title, description):
    return discord.Embed(
        title=f"✅ {title}",
        description=description,
        color=discord.Color.green(),
    )

def error_embed(description):
    return discord.Embed(
        title="❌ خطأ",
        description=description,
        color=discord.Color.red(),
    )

def info_embed(title, description):
    return discord.Embed(
        title=f"ℹ️ {title}",
        description=description,
        color=discord.Color.blurple(),
    )

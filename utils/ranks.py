import discord

RANKS = [
    {"name": "Trainee", "xp": 0},
    {"name": "Helper", "xp": 100},
    {"name": "Moderator", "xp": 300},
    {"name": "Senior Moderator", "xp": 700},
    {"name": "Manager", "xp": 1500},
]


def calculate_level(xp: int) -> int:
    xp = max(0, int(xp))
    return xp // 100


def rank_for_xp(xp: int) -> dict:
    xp = max(0, int(xp))
    current = RANKS[0]
    for rank in RANKS:
        if xp >= rank["xp"]:
            current = rank
        else:
            break
    return current.copy()


def next_rank(xp: int) -> dict | None:
    xp = max(0, int(xp))
    for rank in RANKS:
        if xp < rank["xp"]:
            return rank.copy()
    return None


def detect_promotion(old_xp: int, new_xp: int) -> dict | None:
    old_rank = rank_for_xp(old_xp)
    new_rank = rank_for_xp(new_xp)
    if old_rank["name"] != new_rank["name"]:
        return {"old_rank": old_rank, "new_rank": new_rank}
    return None


def progress_to_next_rank(xp: int) -> dict:
    current = rank_for_xp(xp)
    upcoming = next_rank(xp)
    if not upcoming:
        return {"current": current, "next": None, "remaining": 0, "percent": 100}
    span = max(1, upcoming["xp"] - current["xp"])
    gained = max(0, int(xp) - current["xp"])
    return {
        "current": current,
        "next": upcoming,
        "remaining": upcoming["xp"] - int(xp),
        "percent": min(100, int((gained / span) * 100)),
    }


async def send_promotion_notice(guild: discord.Guild, member: discord.Member, old_rank: str, new_rank: str, channel_id: int | None = None):
    channel = guild.get_channel(channel_id) if channel_id else None
    if not isinstance(channel, discord.TextChannel):
        channel = member.guild.system_channel
    if not isinstance(channel, discord.TextChannel):
        return False
    embed = discord.Embed(
        title="🎉 Staff Promotion",
        description=f"{member.mention} تمت ترقيته من **{old_rank}** إلى **{new_rank}**.",
        color=discord.Color.gold(),
        timestamp=discord.utils.utcnow(),
    )
    try:
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False

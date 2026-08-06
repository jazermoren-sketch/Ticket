import html
from datetime import datetime, timezone

async def create_transcript(channel):
    messages = [message async for message in channel.history(limit=None, oldest_first=True)]

    rows = []
    for message in messages:
        author = html.escape(str(message.author))
        content = html.escape(message.content or "[بدون نص]")
        timestamp = message.created_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        attachments = ""
        if message.attachments:
            links = " ".join(
                f'<a href="{html.escape(a.url)}">{html.escape(a.filename)}</a>'
                for a in message.attachments
            )
            attachments = f"<div class='attachments'>📎 {links}</div>"

        rows.append(
            f"""
            <article class="message">
                <div class="meta"><strong>{author}</strong> <span>{timestamp}</span></div>
                <div class="content">{content}</div>
                {attachments}
            </article>
            """
        )

    body = "\n".join(rows) or "<p>لا توجد رسائل.</p>"

    return f"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>Transcript - {html.escape(channel.name)}</title>
<style>
body {{ font-family: Arial, sans-serif; background:#f4f5f7; margin:0; padding:24px; color:#202225; }}
.container {{ max-width:1000px; margin:auto; background:white; padding:24px; border-radius:12px; }}
h1 {{ margin-top:0; }}
.message {{ padding:14px 0; border-bottom:1px solid #e5e7eb; }}
.meta {{ margin-bottom:6px; }}
.meta span {{ color:#6b7280; font-size:12px; margin-right:8px; }}
.content {{ white-space:pre-wrap; word-break:break-word; }}
.attachments {{ margin-top:8px; }}
a {{ color:#2563eb; }}
</style>
</head>
<body>
<div class="container">
<h1>🎫 Transcript: {html.escape(channel.name)}</h1>
<p>تم إنشاء السجل بتاريخ: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
<hr>
{body}
</div>
</body>
</html>"""

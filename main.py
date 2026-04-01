import os
import json
import re
import logging
import threading
import gspread
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, PicklePersistence
from flask import Flask

# --- LOGGER SETUP ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONFIGURATION (Environment Variables မှ ဖတ်ရန်) ---
TOKEN = os.getenv("BOT_TOKEN")
MAIN_ADMIN_ID = int(os.getenv("ADMIN_ID") or 0)
ADMIN_GROUP_A = int(os.getenv("GROUP_A") or 0)
ADMIN_GROUP_B = int(os.getenv("GROUP_B") or 0)

# KPay အချက်အလက်များ
KPAY_GROUP_A = "09793655312 (Sai Khun Thet Hein)"
KPAY_GROUP_B = "09402021942 (Hnin Pwint Phyu)"

ADMIN_ROUTING = {
    "Game": ADMIN_GROUP_A,
    "Digital product": ADMIN_GROUP_A,
    "Online Class": ADMIN_GROUP_B,
    "Gsm reseller": ADMIN_GROUP_B,
    "Online class": ADMIN_GROUP_B,
    "သင်တန်းများကြည့်ရန်": ADMIN_GROUP_B
}

# --- FLASK SERVER (For Render Keep-Alive) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running..."

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- GOOGLE SHEET CONNECTION ---
def connect_sheet():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Render Environment Variable (GOOGLE_SHEETS_JSON) မှ JSON String ကို ဖတ်ခြင်း
        google_json_str = os.environ.get("GOOGLE_SHEETS_JSON")
        
        if google_json_str:
            creds_dict = json.loads(google_json_str)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            # Local PC မှာ စမ်းသပ်ရန်အတွက်သာ
            creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
            
        client = gspread.authorize(creds)
        # အစ်ကို့ Google Sheet အမည်ကို ဒီနေရာမှာ အတိအကျ ပြန်ပြင်ပေးပါ
        ss = client.open("DigitalProductBot") 
        return ss.worksheet("Products"), ss.worksheet("Orders"), ss.worksheet("Settings")
    except Exception as e:
        logger.error(f"Sheet Connection Error: {e}")
        return None, None, None

sheet, order_sheet, settings_sheet = connect_sheet()

# --- PERSISTENCE (မှတ်ဉာဏ်သိမ်းဆည်းရန်) ---
my_persistence = PicklePersistence(filepath='bot_memory')

# --- HELPERS ---
def get_direct_drive_link(url):
    if not url or "drive.google.com" not in str(url):
        return url
    match = re.search(r'(?:id=|\/d\/|src=)([\w-]{25,})', str(url))
    return f"https://drive.google.com/uc?export=view&id={match.group(1)}" if match else url

# --- BOT HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    welcome_text = "<b>mm tech မှ ကြိုဆိုပါတယ်ရှင့်။</b>\n\nလူကြီးမင်း အလိုရှိတဲ့ product ကိုဝယ်ဖို့ အောက်က <b>🚀 Start Shopping</b> button လေးကို နှိပ်ပေးပါရှင့်।"
    
    keyboard = [[InlineKeyboardButton("🚀 Start Shopping", callback_data="main_menu")]]
    
    try:
        if settings_sheet:
            settings_data = settings_sheet.get_all_records()
            for idx, row in enumerate(settings_data):
                btn_name = str(row.get('buttom', '')).strip()
                d_link = str(row.get('direct link', '')).strip()
                if btn_name:
                    btn = InlineKeyboardButton(btn_name, url=d_link) if d_link.startswith("http") else InlineKeyboardButton(btn_name, callback_data=f"set_{idx}")
                    keyboard.append([btn])
    except Exception as e:
        logger.warning(f"Settings Load Error: {e}")

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "main_menu":
        all_p = sheet.get_all_records()
        cats = sorted(list(set([str(p.get('Category')).strip() for p in all_p if p.get('Category')])))
        keyboard = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in cats]
        keyboard.append([InlineKeyboardButton("🔙 Back to Start", callback_data="back_start")])
        await query.edit_message_text("<b>ဘယ်ကဏ္ဍကို ကြည့်ချင်ပါသလဲရှင့်?</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data == "back_start":
        await start(update, context)

    elif data.startswith("cat_"):
        cat = data.split("_")[1]
        context.user_data['sel_cat'] = cat
        all_p = sheet.get_all_records()
        names = sorted(list(set([p['Name'] for p in all_p if str(p.get('Category')) == cat])))
        keyboard = [[InlineKeyboardButton(n, callback_data=f"name_{n}")] for n in names]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        await query.edit_message_text(f"📂 <b>{cat}</b> အောက်ရှိ ပစ္စည်းများ -", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith("name_"):
        name = data.split("_", 1)[1]
        all_p = sheet.get_all_records()
        plans = [p for p in all_p if str(p.get('Name')) == name and str(p.get('Category')) == context.user_data.get('sel_cat')]
        keyboard = [[InlineKeyboardButton(f"💎 {p['Plan']} - {p['Price']} Ks", callback_data=f"buy_{p['ID']}")] for p in plans]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"cat_{context.user_data.get('sel_cat')}")])
        await query.edit_message_text(f"📦 <b>{name}</b> အတွက် Plan ရွေးပါ -", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')

    elif data.startswith("buy_"):
        pid = data.split("_")[1]
        item = next((p for p in sheet.get_all_records() if str(p.get('ID')) == pid), None)
        if item:
            context.user_data.update({
                'sel_pid': pid, 
                'sel_pname': f"{item['Name']} ({item['Plan']})", 
                'sel_price': item['Price'],
                'sel_cat': context.user_data.get('sel_cat')
            })
            desc = item.get('Des') or item.get('Details') or 'အသေးစိတ် အချက်အလက် မရှိပါ'
            kpay = KPAY_GROUP_A if context.user_data.get('sel_cat') in ["Game", "Digital product"] else KPAY_GROUP_B
            
            msg = (f"✅ <b>{item['Name']} ({item['Plan']})</b>\n"
                   f"📝 <b>အသေးစိတ်:</b> {desc}\n"
                   f"💰 <b>စျေးနှုန်း:</b> {item['Price']} Ks\n\n"
                   f"KPay - {kpay} သို့ ငွေလွှဲပြီး Screenshot ပို့ပေးပါရှင့်။")
            
            p_link = get_direct_drive_link(item.get('Link', ''))
            if p_link and p_link.startswith("http"):
                try:
                    await query.message.delete()
                    await context.bot.send_photo(chat_id=query.message.chat_id, photo=p_link, caption=msg, parse_mode='HTML')
                except:
                    await query.edit_message_text(msg, parse_mode='HTML')
            else:
                await query.edit_message_text(msg, parse_mode='HTML')

    elif data.startswith("ad_accept_"):
        parts = data.split("_")
        target_uid, target_pid = parts[2], parts[3]
        admin_name = update.effective_user.full_name
        original_caption = query.message.caption_html if query.message.caption else query.message.text_html
        new_caption = f"{original_caption}\n\n🤝 <b>ကိုင်တွယ်သူ:</b> {admin_name}"
        context.user_data['admin_task'] = {'uid': target_uid, 'pid': target_pid}
        
        await query.edit_message_caption(caption=new_caption, reply_markup=None, parse_mode='HTML')
        await query.answer("အော်ဒါကို လက်ခံလိုက်ပါပြီ။")
        await query.message.reply_text("စစ်ဆေးပြီးပါက Customer ထံ ပို့မည့် 'Account/Code' ကို ဒီနေရာမှာ တန်းရိုက်ပို့ပေးပါ။")

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('sel_pid'):
        await update.message.reply_text("⚠️ ပစ္စည်း ပြန်ရွေးပေးပါဦးရှင်။", parse_mode='HTML')
        return
    context.user_data['temp_photo_id'] = update.message.photo[-1].file_id
    context.user_data['waiting_order_details'] = True
    await update.message.reply_text("📸 <b>Screenshot ရရှိပါတယ်</b>\nအချက်အလက် (ဥပမာ- Game ID) ကို ရိုက်ပို့ပေးပါရှင်။", parse_mode='HTML')

async def handle_all_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    # Admin မှ ပစ္စည်းပြန်ပို့ခြင်း
    if 'admin_task' in context.user_data:
        task = context.user_data.pop('admin_task')
        try:
            target_uid, target_pid = task['uid'], task['pid']
            all_p = sheet.get_all_records()
            item = next((p for p in all_p if str(p.get('ID')) == str(target_pid)), None)
            p_name = item['Name'] if item else "Product"
            
            await context.bot.send_message(chat_id=target_uid, text=f"🎉 <b>ဝယ်ယူမှု အောင်မြင်ပါသည်</b>\n\n📦 ပစ္စည်း: {p_name}\n🔑 {text}", parse_mode='HTML')
            await update.message.reply_text("✅ Customer ထံ ပစ္စည်းပို့ဆောင်ပြီးပါပြီ။")
            
            all_rows = order_sheet.get_all_records()
            for i, row in enumerate(all_rows, 2):
                if str(row.get('User_ID')) == str(target_uid) and row.get('Status') == 'Pending':
                    order_sheet.update_cell(i, 8, "Paid")
                    break
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
        return

    # User မှ အချက်အလက်ပို့ခြင်း
    if context.user_data.get('waiting_order_details'):
        loading_msg = await update.message.reply_text("⏳ ခဏစောင့်ပေးပါ...")
        context.user_data['waiting_order_details'] = False
        pname, pid, cat, price = context.user_data.get('sel_pname'), context.user_data.get('sel_pid'), context.user_data.get('sel_cat'), context.user_data.get('sel_price')
        photo_id = context.user_data.get('temp_photo_id')

        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            order_sheet.append_row([user.id, f"@{user.username}", user.full_name, "", f"{pname} [{text}]", price, now, "Pending"])
            
            target_admin = ADMIN_ROUTING.get(cat, MAIN_ADMIN_ID) or MAIN_ADMIN_ID
            user_link = f'<a href="tg://user?id={user.id}">{user.full_name}</a>'
            caption = (f"🔔 <b>အော်ဒါအသစ်!</b>\n\n📦 <b>ပစ္စည်း:</b> {pname}\n📝 <b>အချက်အလက်:</b> {text}\n💰 <b>စျေးနှုန်း:</b> {price} Ks\n👤 <b>ဝယ်သူ:</b> {user_link}\n🆔 <b>User ID:</b> <code>{user.id}</code>")
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🤝 ကိုင်တွယ်မည်", callback_data=f"ad_accept_{user.id}_{pid}")]])
            
            await context.bot.send_photo(chat_id=target_admin, photo=photo_id, caption=caption, reply_markup=markup, parse_mode='HTML')
            if str(target_admin) != str(MAIN_ADMIN_ID):
                await context.bot.send_photo(chat_id=MAIN_ADMIN_ID, photo=photo_id, caption=f"📢 <b>Copy to Main Admin</b>\n{caption}", reply_markup=markup, parse_mode='HTML')

            await loading_msg.edit_text("✅ လက်ခံရရှိပါတယ်ရှင်။ Admin မှ စစ်ဆေးပြီး ပစ္စည်းပို့ပေးပါမယ်။")
        except Exception as e:
            await loading_msg.edit_text(f"❌ အမှားရှိပါသည်: {e}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MAIN_ADMIN_ID: return
    if not context.args: return
    
    msg_text = " ".join(context.args)
    all_orders = order_sheet.get_all_records()
    user_ids = list(set([str(o.get('User_ID')) for o in all_orders if o.get('User_ID')]))
    
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 <b>MM Tech အကြောင်းကြားစာ</b>\n\n{msg_text}", parse_mode='HTML')
        except: continue
    await update.message.reply_text("✅ Broadcast ပို့ဆောင်ပြီးပါပြီ။")

# --- MAIN ---
if __name__ == '__main__':
    # Start Keep-alive server
    threading.Thread(target=run_web_server, daemon=True).start()
    
    if not TOKEN:
        logger.error("BOT_TOKEN missing!")
    else:
        # Persistence ပါဝင်သော Application တည်ဆောက်ခြင်း
        app = Application.builder().token(TOKEN).persistence(my_persistence).build()
        
        # Handlers များ ထည့်သွင်းခြင်း
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("broadcast", broadcast))
        app.add_handler(CallbackQueryHandler(button_click))
        app.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_text))
        
        print("Bot is starting on Render...")
        app.run_polling(drop_pending_updates=True)

import os
import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler
)
import firebase_admin
from firebase_admin import credentials, firestore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()
# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Firebase sozlamalari
cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# Admin ID
ADMIN_ID = 1685356708

class PaymentBot:
    def __init__(self):
        self.scheduler = None
        self.temp_data = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot ishga tushganda admin uchun keyboard"""
        if self.scheduler is None:
            self.scheduler = AsyncIOScheduler()
            self.scheduler.start()
        
        user = update.effective_user
        chat_type = update.effective_chat.type
        
        # Guruhda /start ishlamaydi
        if chat_type in ['group', 'supergroup']:
            return
        
        if user.id == ADMIN_ID:
            keyboard = [
                [KeyboardButton("➕ O'quvchi qo'shish"), KeyboardButton("💰 To'lov belgilash")],
                [KeyboardButton("📋 O'quvchilar ro'yxati"), KeyboardButton("⏰ Qolgan kunlar")],
                [KeyboardButton("📨 Guruhga to'lovlarni eslatish"), KeyboardButton("📊 Statistika")],
                [KeyboardButton("📱 Guruhlar ro'yxati"), KeyboardButton("⚙️ Joriy guruhni o'rnatish")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"🤖 Assalomu alaykum, Admin!\n\n"
                f"To'lov boshqaruv tizimiga xush kelibsiz.\n"
                f"Quyidagi tugmalardan foydalaning:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "Assalomu alaykum! Sizning to'lovlaringiz adminlar tomonidan nazorat qilinadi."
            )

    async def set_group(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Joriy guruhni o'rnatish"""
        if update.effective_user.id != ADMIN_ID:
            return
        
        chat_type = update.effective_chat.type
        
        if chat_type in ['group', 'supergroup']:
            group_id = update.effective_chat.id
            group_title = update.effective_chat.title
            
            # Guruh ma'lumotlarini saqlash
            db.collection("groups").document(str(group_id)).set({
                "group_id": group_id,
                "title": group_title,
                "added_date": datetime.now(timezone.utc)
            })
            
            await update.message.reply_text(
                f"✅ Guruh muvaffaqiyatli qo'shildi!\n\n"
                f"📱 Guruh: {group_title}\n"
                f"🆔 ID: {group_id}\n\n"
                f"Endi bu guruhga o'quvchilarni biriktirishingiz mumkin."
            )
        else:
            await update.message.reply_text(
                "❌ Bu funksiya faqat guruhda ishlaydi!\n\n"
                "Botni guruhga qo'shing va u yerda /setgroup kommandasini yuboring."
            )

    async def show_groups(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Barcha guruhlar ro'yxati"""
        groups = db.collection("groups").stream()
        
        text = "📱 GURUHLAR RO'YXATI\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        count = 0
        for group in groups:
            data = group.to_dict()
            count += 1
            
            # Guruhga biriktirilgan o'quvchilar sonini hisoblash
            students = db.collection("students").where("group_id", "==", data['group_id']).stream()
            student_count = sum(1 for _ in students)
            
            text += f"{count}. {data['title']}\n"
            text += f"   🆔 ID: {data['group_id']}\n"
            text += f"   👥 O'quvchilar: {student_count} ta\n\n"
        
        if count == 0:
            text += "Hech qanday guruh topilmadi.\n\n"
            text += "Guruhga botni qo'shing va /setgroup komandasini yuboring."
        else:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📊 Jami: {count} ta guruh"
        
        await update.message.reply_text(text)

    async def show_stats_text(self, update: Update):
        """Statistika ko'rsatish"""
        students = db.collection("students").stream()
        
        total = 0
        paid = 0
        overdue = 0
        today = 0
        week = 0
        
        now = datetime.now(timezone.utc)
        
        for student in students:
            data = student.to_dict()
            total += 1
            
            next_payment = data.get("next_payment")
            if next_payment:
                days_left = (next_payment - now).days
                
                if days_left < 0:
                    overdue += 1
                elif days_left == 0:
                    today += 1
                elif days_left <= 7:
                    week += 1
                else:
                    paid += 1
        
        # Guruhlar statistikasi
        groups = db.collection("groups").stream()
        total_groups = sum(1 for _ in groups)
        
        text = "📊 UMUMIY STATISTIKA\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        text += f"👥 Jami o'quvchilar: {total} ta\n"
        text += f"📱 Guruhlar soni: {total_groups} ta\n\n"
        
        text += "TO'LOV HOLATI:\n"
        text += f"✅ To'lagan: {paid} ta\n"
        text += f"🟠 7 kun ichida: {week} ta\n"
        text += f"🟡 Bugun to'lov: {today} ta\n"
        text += f"🔴 Kechikkan: {overdue} ta\n\n"
        
        if total > 0:
            paid_percent = (paid / total) * 100
            text += f"📈 To'lagan foiz: {paid_percent:.1f}%\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━"
        
        await update.message.reply_text(text)

    async def handle_button_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Keyboard tugmalari uchun handler"""
        if update.effective_user.id != ADMIN_ID:
            return
        
        # Guruhda tugmalar ishlamaydi
        if update.effective_chat.type in ['group', 'supergroup']:
            return
            
        text = update.message.text
        
        if text == "➕ O'quvchi qo'shish":
            await update.message.reply_text(
                "👤 O'quvchining to'liq ismini kiriting:\n\n"
                "Misol: Abdullayev Ali"
            )
            context.user_data['action'] = 'add_student'
            context.user_data['step'] = 'name'
            
        elif text == "💰 To'lov belgilash":
            await self.show_students_for_payment_text(update, context)
            
        elif text == "📋 O'quvchilar ro'yxati":
            await self.list_students_text(update)
            
        elif text == "⏰ Qolgan kunlar":
            await self.show_days_remaining_text(update)
            
        elif text == "📨 Guruhga to'lovlarni eslatish":
            await self.select_group_for_reminder(update, context)
            
        elif text == "📊 Statistika":
            await self.show_stats_text(update)
            
        elif text == "📱 Guruhlar ro'yxati":
            await self.show_groups(update, context)
            
        elif text == "⚙️ Joriy guruhni o'rnatish":
            await update.message.reply_text(
                "⚙️ Guruhni o'rnatish:\n\n"
                "1. Botni guruhga qo'shing\n"
                "2. Botni admin qiling\n"
                "3. Guruhda /setgroup kommandasini yuboring\n\n"
                "Shundan keyin o'quvchilarni shu guruhga biriktirishingiz mumkin."
            )

    async def select_group_for_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Eslatma yuborish uchun guruhni tanlash"""
        groups = db.collection("groups").stream()
        
        text = "📨 GURUHGA TO'LOV ESLATMASI\n\n"
        text += "Qaysi guruhga eslatma yuborishni xohlaysiz?\n\n"
        
        group_list = []
        for group in groups:
            data = group.to_dict()
            group_list.append(data)
            text += f"🆔 Guruh ID: {data['group_id']}\n"
            text += f"📱 Nomi: {data['title']}\n\n"
        
        if not group_list:
            text = "❌ Guruhlar topilmadi!\n\n"
            text += "Avval guruh qo'shing:\n"
            text += "1. Botni guruhga qo'shing\n"
            text += "2. /setgroup kommandasini guruhda yuboring"
            await update.message.reply_text(text)
            return
        
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        text += "Guruh ID sini kiriting:"
        
        await update.message.reply_text(text)
        context.user_data['action'] = 'send_reminder'
        context.user_data['step'] = 'select_group'

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Xabarlarni qayta ishlash"""
        if update.effective_chat.type in ['group', 'supergroup']:
            return
            
        if update.effective_user.id != ADMIN_ID:
            return

        user_data = context.user_data
        text = update.message.text

        # O'quvchi qo'shish jarayoni
        if user_data.get('action') == 'add_student':
            if user_data.get('step') == 'name':
                context.user_data['student_name'] = text
                context.user_data['step'] = 'phone'
                await update.message.reply_text(
                    "📱 Telefon raqamini kiriting:\n\n"
                    "Misol: +998901234567"
                )
                
            elif user_data.get('step') == 'phone':
                context.user_data['student_phone'] = text
                context.user_data['step'] = 'user_id'
                await update.message.reply_text(
                    "🆔 Telegram ID ni kiriting:\n\n"
                    "ID ni qanday topish mumkin:\n"
                    "1. @userinfobot ga /start yuboring\n"
                    "2. O'quvchining xabarini forward qiling\n"
                    "3. ID ni ko'chirib oling"
                )
                
            elif user_data.get('step') == 'user_id':
                try:
                    user_id = int(text)
                    context.user_data['student_user_id'] = user_id
                    context.user_data['step'] = 'group'
                    
                    # Guruhlar ro'yxatini ko'rsatish
                    groups = db.collection("groups").stream()
                    group_text = "📱 GURUHNI TANLANG\n\n"
                    
                    group_count = 0
                    for group in groups:
                        data = group.to_dict()
                        group_count += 1
                        group_text += f"{group_count}. {data['title']}\n"
                        group_text += f"   🆔 ID: {data['group_id']}\n\n"
                    
                    if group_count == 0:
                        group_text = "❌ Guruhlar topilmadi!\n\n"
                        group_text += "Avval guruh qo'shing."
                        await update.message.reply_text(group_text)
                        context.user_data.clear()
                        return
                    
                    group_text += "━━━━━━━━━━━━━━━━━━━━\n"
                    group_text += "O'quvchini qaysi guruhga qo'shmoqchisiz?\nGuruh ID sini kiriting:"
                    
                    await update.message.reply_text(group_text)
                    
                except ValueError:
                    await update.message.reply_text(
                        "❌ Xato format!\n\n"
                        "ID faqat raqamlardan iborat bo'lishi kerak.\n"
                        "Misol: 123456789"
                    )
                    
            elif user_data.get('step') == 'group':
                try:
                    group_id = int(text)
                    
                    # Guruh mavjudligini tekshirish
                    group = db.collection("groups").document(str(group_id)).get()
                    if not group.exists:
                        await update.message.reply_text(
                            "❌ Bu guruh topilmadi!\n\n"
                            "Iltimos, mavjud guruh ID sini kiriting."
                        )
                        return
                    
                    user_id = context.user_data.get('student_user_id')
                    name = context.user_data.get('student_name')
                    phone = context.user_data.get('student_phone')
                    
                    # Username olish
                    username = None
                    try:
                        user_info = await context.bot.get_chat(user_id)
                        username = user_info.username
                    except:
                        pass
                    
                    student_data = {
                        "user_id": user_id,
                        "name": name,
                        "phone": phone,
                        "username": username,
                        "group_id": group_id,
                        "last_payment": None,
                        "next_payment": None,
                        "added_date": datetime.now(timezone.utc),
                        "status": "active"
                    }
                    
                    db.collection("students").document(str(user_id)).set(student_data)
                    
                    group_data = group.to_dict()
                    await update.message.reply_text(
                        f"✅ O'quvchi muvaffaqiyatli qo'shildi!\n\n"
                        f"👤 Ism: {name}\n"
                        f"🆔 Telegram ID: {user_id}\n"
                        f"📱 Telefon: {phone}\n"
                        f"📱 Guruh: {group_data['title']}\n"
                        f"{'🔗 Username: @' + username if username else '⚠️ Username topilmadi'}"
                    )
                    
                    context.user_data.clear()
                except ValueError:
                    await update.message.reply_text(
                        "❌ Xato format!\n\n"
                        "Guruh ID faqat raqam bo'lishi kerak."
                    )
        
        # To'lov belgilash jarayoni
        elif user_data.get('action') == 'mark_payment':
            if user_data.get('step') == 'select_student':
                try:
                    user_id = int(text)
                    
                    # O'quvchi mavjudligini tekshirish
                    student = db.collection("students").document(str(user_id)).get()
                    if student.exists:
                        context.user_data['payment_user_id'] = user_id
                        context.user_data['step'] = 'payment_days'
                        
                        data = student.to_dict()
                        group_id = data.get('group_id')
                        group_name = "Belgilanmagan"
                        if group_id:
                            group = db.collection("groups").document(str(group_id)).get()
                            if group.exists:
                                group_name = group.to_dict()['title']
                        
                        await update.message.reply_text(
                            f"👤 {data['name']}\n"
                            f"🆔 ID: {user_id}\n"
                            f"📱 Guruh: {group_name}\n\n"
                            f"📅 Necha kunlik to'lov?\n\n"
                            f"Misol:\n"
                            f"30 - 1 oylik\n"
                            f"90 - 3 oylik\n"
                            f"180 - 6 oylik"
                        )
                    else:
                        await update.message.reply_text("❌ Bu ID bazada topilmadi. Qaytadan kiriting:")
                except ValueError:
                    await update.message.reply_text("❌ Faqat raqam kiriting!")
                    
            elif user_data.get('step') == 'payment_days':
                try:
                    days = int(text)
                    user_id = context.user_data.get('payment_user_id')
                    
                    student_ref = db.collection("students").document(str(user_id))
                    student = student_ref.get()
                    
                    if student.exists:
                        now = datetime.now(timezone.utc)
                        next_payment = now + timedelta(days=days)
                        
                        student_ref.update({
                            "last_payment": now,
                            "next_payment": next_payment,
                            "payment_days": days,
                            "status": "paid"
                        })
                        
                        # Scheduler
                        if self.scheduler is None:
                            self.scheduler = AsyncIOScheduler()
                            self.scheduler.start()
                        
                        try:
                            self.scheduler.remove_job(f"reminder_{user_id}")
                        except:
                            pass
                        
                        self.scheduler.add_job(
                            self.send_reminder,
                            'date',
                            run_date=next_payment,
                            args=[context.application, user_id],
                            id=f"reminder_{user_id}"
                        )
                        
                        student_data = student.to_dict()
                        
                        await update.message.reply_text(
                            f"✅ TO'LOV MUVAFFAQIYATLI BELGILANDI!\n\n"
                            f"👤 O'quvchi: {student_data['name']}\n"
                            f"🆔 ID: {user_id}\n"
                            f"📅 To'lov sanasi: {now.strftime('%d.%m.%Y')}\n"
                            f"⏰ Keyingi to'lov: {next_payment.strftime('%d.%m.%Y')}\n"
                            f"📆 Muddat: {days} kun ({days//30} oy)"
                        )
                        
                        context.user_data.clear()
                except ValueError:
                    await update.message.reply_text(
                        "❌ Faqat raqam kiriting!\n\n"
                        "Misol: 30"
                    )
        
        # Guruh uchun eslatma yuborish
        elif user_data.get('action') == 'send_reminder':
            if user_data.get('step') == 'select_group':
                try:
                    group_id = int(text)
                    
                    # Guruh mavjudligini tekshirish
                    group = db.collection("groups").document(str(group_id)).get()
                    if not group.exists:
                        await update.message.reply_text(
                            "❌ Bu guruh topilmadi!\n\n"
                            "Iltimos, mavjud guruh ID sini kiriting."
                        )
                        return
                    
                    group_data = group.to_dict()
                    await self.send_group_reminder(update, context, group_id, group_data['title'])
                    context.user_data.clear()
                    
                except ValueError:
                    await update.message.reply_text("❌ Faqat raqam kiriting!")

    async def send_group_reminder(self, update: Update, context: ContextTypes.DEFAULT_TYPE, group_id: int, group_title: str):
        """Tanlangan guruhga to'lov eslatmasi"""
        await update.message.reply_text(f"⏳ {group_title} guruhi uchun eslatmalar tayyorlanmoqda...")
        
        # Faqat shu guruhga tegishli o'quvchilarni olish
        students = db.collection("students").where("group_id", "==", group_id).stream()
        now = datetime.now(timezone.utc)
        
        # Barcha o'quvchilarni kategoriyalarga ajratish
        overdue_students = []  # Muddati o'tgan
        today_students = []     # Bugun to'lov
        week_students = []      # 7 kun ichida
        paid_students = []      # To'lagan (7 kundan ko'p)
        
        for student in students:
            data = student.to_dict()
            next_payment = data.get("next_payment")
            
            if next_payment:
                days_left = (next_payment - now).days
                username = data.get('username')
                user_mention = f"@{username}" if username else data['name']
                
                student_info = {
                    'mention': user_mention,
                    'name': data['name'],
                    'days': days_left,
                    'date': next_payment.strftime('%d.%m.%Y')
                }
                
                if days_left < 0:
                    overdue_students.append(student_info)
                elif days_left == 0:
                    today_students.append(student_info)
                elif days_left <= 7:
                    week_students.append(student_info)
                else:
                    paid_students.append(student_info)
        
        # Har bir kategoriyani kunlar bo'yicha saralash
        overdue_students.sort(key=lambda x: x['days'])
        week_students.sort(key=lambda x: x['days'])
        paid_students.sort(key=lambda x: x['days'])
        
        # Guruhga xabar yuborish
        if overdue_students or today_students or week_students:
            message = "📢OYLIK TO'LOV ESLATMALARI\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n\n"
            
            # Muddati o'tganlar
            if overdue_students:
                message += "🔴 MUDDATI O'TGAN:\n\n"
                for student in overdue_students:
                    message += f"▪️ {student['mention']}\n"
                    message += f"   ⚠️ {abs(student['days'])} kun kechikkan\n"
                    message += f"   📅 {student['date']}\n\n"
            
            # Bugun to'lov
            if today_students:
                message += "🟡 BUGUN TO'LOV:\n\n"
                for student in today_students:
                    message += f"▪️ {student['mention']}\n"
                    message += f"   📅 {student['date']}\n\n"
            
            # 7 kun ichida
            if week_students:
                message += "🟠 YAQIN MUDDA (7 kun ichida):\n\n"
                for student in week_students:
                    message += f"▪️ {student['mention']}\n"
                    message += f"   ⏰ {student['days']} kun qoldi\n"
                    message += f"   📅 {student['date']}\n\n"
            
            message += "━━━━━━━━━━━━━━━━━━━━\n"
            message += "💡 To'lovlarni o'z vaqtida amalga oshiring!"
            
            try:
                await context.bot.send_message(
                    chat_id=group_id,
                    text=message
                )
                
                # Adminга hisobot
                total = len(overdue_students) + len(today_students) + len(week_students)
                await update.message.reply_text(
                    f"✅ {group_title} guruhiga eslatma yuborildi!\n\n"
                    f"📊 Jami: {total} ta o'quvchi\n"
                    f"🔴 Kechikkan: {len(overdue_students)}\n"
                    f"🟡 Bugun: {len(today_students)}\n"
                    f"🟠 7 kun ichida: {len(week_students)}"
                )
            except Exception as e:
                logger.error(f"Guruhga xabar yuborishda xato: {e}")
                await update.message.reply_text(
                    f"❌ Xatolik yuz berdi!\n\n"
                    f"Guruh: {group_title}\n"
                    f"ID: {group_id}\n"
                    f"Xato: {str(e)}\n\n"
                    f"Botni guruhda admin qilganingizga ishonch hosil qiling."
                )
        else:
            await update.message.reply_text(
                f"ℹ️ {group_title} guruhida eslatish kerak bo'lgan o'quvchi yo'q.\n\n"
                f"✅ To'lagan: {len(paid_students)} ta\n"
                "Barcha o'quvchilar o'z vaqtida to'lovni amalga oshirgan."
            )

    async def send_reminder(self, application: Application, user_id: int):
        """O'quvchiga to'lov eslatmasi yuborish"""
        try:
            student_ref = db.collection("students").document(str(user_id))
            student = student_ref.get()
            
            if student.exists:
                data = student.to_dict()
                
                await application.bot.send_message(
                    chat_id=user_id,
                    text=f"⏰ TO'LOV ESLATMASI\n\n"
                         f"Hurmatli {data['name']},\n"
                         f"Sizning to'lov muddatingiz tugadi!\n\n"
                         f"📅 To'lov sanasi: Bugun\n"
                         f"📱 Admin bilan bog'laning."
                )
                
                # Statusni yangilash
                student_ref.update({"status": "overdue"})
                
        except Exception as e:
            logger.error(f"Eslatma yuborishda xato: {e}")

    async def show_students_for_payment_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """To'lov belgilash uchun o'quvchilar ro'yxati"""
        students = db.collection("students").stream()
        
        text = "💰 TO'LOV BELGILASH\n\n"
        text += "O'quvchilar ro'yxati:\n\n"
        
        count = 0
        for student in students:
            data = student.to_dict()
            count += 1
            
            group_name = "Guruhsiz"
            group_id = data.get('group_id')
            if group_id:
                group = db.collection("groups").document(str(group_id)).get()
                if group.exists:
                    group_name = group.to_dict()['title']
            
            text += f"{count}. {data['name']}\n"
            text += f"   🆔 ID: {data['user_id']}\n"
            text += f"   📱 {data.get('phone', 'N/A')}\n"
            text += f"   📱 Guruh: {group_name}\n\n"
        
        if count == 0:
            text = "❌ O'quvchilar ro'yxati bo'sh!\n\nAvval o'quvchi qo'shing."
        else:
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += "O'quvchining Telegram ID sini kiriting:"
        
        await update.message.reply_text(text)
        
        if count > 0:
            context.user_data['action'] = 'mark_payment'
            context.user_data['step'] = 'select_student'

    async def list_students_text(self, update: Update):
        """O'quvchilar ro'yxati"""
        students = db.collection("students").stream()
        
        text = "📋 O'QUVCHILAR RO'YXATI\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        count = 0
        for student in students:
            data = student.to_dict()
            count += 1
            
            status_emoji = "✅" if data.get("status") == "paid" else "⚠️"
            next_payment = data.get("next_payment")
            next_date = next_payment.strftime("%d.%m.%Y") if next_payment else "Belgilanmagan"
            
            group_name = "Guruhsiz"
            group_id = data.get('group_id')
            if group_id:
                group = db.collection("groups").document(str(group_id)).get()
                if group.exists:
                    group_name = group.to_dict()['title']
            
            text += f"{status_emoji} {data['name']}\n"
            text += f"   🆔 ID: {data['user_id']}\n"
            text += f"   📱 {data.get('phone', 'N/A')}\n"
            text += f"   📱 Guruh: {group_name}\n"
            text += f"   📅 Keyingi to'lov: {next_date}\n"
            
            if next_payment:
                days_left = (next_payment - datetime.now(timezone.utc)).days
                if days_left < 0:
                    text += f"   🔴 {abs(days_left)} kun kechikkan\n"
                elif days_left == 0:
                    text += f"   🟡 Bugun to'lov\n"
                else:
                    text += f"   ⏰ {days_left} kun qoldi\n"
            
            text += "\n"
        
        if count == 0:
            text += "Ro'yxat bo'sh"
        else:
            text += f"━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📊 Jami: {count} ta o'quvchi"
        
        await update.message.reply_text(text)

    async def show_days_remaining_text(self, update: Update):
        """Qolgan kunlarni ko'rsatish"""
        students = db.collection("students").stream()
        
        text = "⏰ TO'LOVGA QOLGAN KUNLAR\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        now = datetime.now(timezone.utc)
        student_list = []
        
        for student in students:
            data = student.to_dict()
            next_payment = data.get("next_payment")
            
            if next_payment:
                days_left = (next_payment - now).days
                student_list.append((data, days_left))
        
        # Kunlar bo'yicha saralash (kamdan ko'pga)
        student_list.sort(key=lambda x: x[1])
        
        if not student_list:
            text += "Hech kimga to'lov belgilanmagan"
        else:
            for data, days_left in student_list:
                group_name = "Guruhsiz"
                group_id = data.get('group_id')
                if group_id:
                    group = db.collection("groups").document(str(group_id)).get()
                    if group.exists:
                        group_name = group.to_dict()['title']
                
                if days_left < 0:
                    emoji = "🔴"
                    status = f"KECHIKDI ({abs(days_left)} kun)"
                elif days_left == 0:
                    emoji = "🟡"
                    status = "BUGUN TO'LOV"
                elif days_left <= 7:
                    emoji = "🟠"
                    status = f"{days_left} kun qoldi"
                else:
                    emoji = "🟢"
                    status = f"{days_left} kun qoldi"
                
                text += f"{emoji} {data['name']}\n"
                text += f"   📱 {data.get('phone', 'N/A')}\n"
                text += f"   📱 Guruh: {group_name}\n"
                text += f"   📅 {data.get('next_payment').strftime('%d.%m.%Y')}\n"
                text += f"   ⏱ {status}\n\n"
            
            text += "━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📊 Jami: {len(student_list)} ta o'quvchi"
        
        await update.message.reply_text(text)


def main():
    """Botni ishga tushirish"""
    # Bot tokenini o'rnatish
    TOKEN = os.getenv("BOT_TOKEN")
    
    if not TOKEN:
        logger.error("BOT_TOKEN topilmadi! .env faylini tekshiring.")
        return
    
    # Bot obyektini yaratish
    bot = PaymentBot()
    
    # Application yaratish
    application = Application.builder().token(TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("setgroup", bot.set_group))
    
    # Message handlers
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(
            r"^(➕ O'quvchi qo'shish|💰 To'lov belgilash|📋 O'quvchilar ro'yxati|"
            r"⏰ Qolgan kunlar|📨 Guruhga to'lovlarni eslatish|📊 Statistika|"
            r"📱 Guruhlar ro'yxati|⚙️ Joriy guruhni o'rnatish)$"
        ),
        bot.handle_button_text
    ))
    
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        bot.handle_message
    ))
    
    # Botni ishga tushirish
    logger.info("Bot ishga tushdi...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
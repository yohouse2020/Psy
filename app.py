import os
import logging
import tempfile
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai
import requests
import subprocess

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Конфигурация
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

class PsychologistBot:
    def __init__(self):
        pass
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_text = """
👋 Добро пожаловать в кабинет психологической помощи!

Я - ваш виртуальный психолог, готовый выслушать и помочь. Вы можете:
• Отправлять голосовые сообщения 🎤
• Писать текстовые сообщения
• Получать профессиональную психологическую поддержку

Я соблюдаю полную конфиденциальность и этику психологической практики.

Расскажите, что вас беспокоит...
        """
        await update.message.reply_text(welcome_text)

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка голосовых сообщений"""
        try:
            await update.message.reply_text("🎤 Обрабатываю ваше сообщение...")
            
            voice = update.message.voice
            voice_file = await voice.get_file()
            
            # Скачиваем голосовое сообщение
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_ogg:
                await voice_file.download_to_drive(temp_ogg.name)
                ogg_path = temp_ogg.name

            # Конвертируем в WAV
            wav_path = await self.convert_ogg_to_wav(ogg_path)
            
            if wav_path:
                # Распознаем речь
                text = await self.speech_to_text(wav_path)
                
                # Удаляем временные файлы
                os.unlink(ogg_path)
                os.unlink(wav_path)
                
                if text:
                    await update.message.reply_text(f"🎤 Я услышал: _{text}_", parse_mode='Markdown')
                    
                    # Генерируем ответ психолога
                    response = await self.generate_psychologist_response(text)
                    await update.message.reply_text(response)
                    
                else:
                    await update.message.reply_text("❌ Не удалось распознать речь. Пожалуйста, попробуйте еще раз или напишите текстом.")
            else:
                await update.message.reply_text("❌ Ошибка конвертации аудио.")
                if os.path.exists(ogg_path):
                    os.unlink(ogg_path)

        except Exception as e:
            logging.error(f"Error processing voice: {e}")
            await update.message.reply_text("❌ Ошибка обработки голосового сообщения. Попробуйте написать текстом.")

    async def convert_ogg_to_wav(self, ogg_path: str) -> str:
        """Конвертация OGG в WAV используя ffmpeg"""
        try:
            wav_path = ogg_path.replace('.ogg', '.wav')
            
            # Используем subprocess для вызова ffmpeg
            result = subprocess.run([
                'ffmpeg', '-i', ogg_path, '-acodec', 'pcm_s16le', 
                '-ac', '1', '-ar', '16000', wav_path, '-y'
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(wav_path):
                return wav_path
            else:
                logging.error(f"FFmpeg error: {result.stderr}")
                return None
                
        except Exception as e:
            logging.error(f"Conversion error: {e}")
            return None

    async def speech_to_text(self, wav_path: str) -> str:
        """Распознавание речи используя Google Speech Recognition"""
        try:
            # Импортируем здесь чтобы избежать проблем с aifc
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            
            with sr.AudioFile(wav_path) as source:
                # Adjust for ambient noise and record
                recognizer.adjust_for_ambient_noise(source)
                audio_data = recognizer.record(source)
                
                # Recognize using Google Speech Recognition
                text = recognizer.recognize_google(audio_data, language='ru-RU')
                return text
                
        except sr.UnknownValueError:
            logging.error("Google Speech Recognition could not understand audio")
            return ""
        except sr.RequestError as e:
            logging.error(f"Could not request results from Google Speech Recognition service; {e}")
            return ""
        except Exception as e:
            logging.error(f"Speech recognition error: {e}")
            return ""

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        user_text = update.message.text
        
        # Проверяем кризисные ситуации
        if await self.check_crisis_situation(user_text):
            await update.message.reply_text(self.get_crisis_response())
            return
        
        # Генерируем ответ психолога
        response = await self.generate_psychologist_response(user_text)
        await update.message.reply_text(response)

    async def generate_psychologist_response(self, user_message: str) -> str:
        """Генерация ответа психолога"""
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            prompt = f"""
Ты - дипломированный психолог с 15-летним опытом работы. Твоя задача - оказывать профессиональную психологическую поддержку.

Пациент: {user_message}

Твой ответ должен быть:
1. Профессиональным и этичным
2. Поддерживающим и эмпатичным  
3. Основанным на принципах доказательной психологии
4. Конкретным и практичным
5. В формате терапевтического диалога

Не давай медицинских диагнозов и не заменяй очную консультацию. Сосредоточься на активном слушании и поддержке.

Ответ психолога:
            """
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты - опытный психолог, оказывающий профессиональную поддержку."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logging.error(f"OpenAI error: {e}")
            return "Благодарю вас за доверие. Я внимательно вас выслушал и хочу отметить, что обращение за помощью - это важный шаг. Давайте вместе подумаем, как мы можем работать с этой ситуацией."

    async def check_crisis_situation(self, text: str) -> bool:
        """Проверка на кризисные ситуации"""
        crisis_keywords = ['суицид', 'самоубийство', 'умру', 'покончить', 'кризис', 'хочу умереть', 'наложу на себя руки']
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in crisis_keywords)

    def get_crisis_response(self) -> str:
        """Ответ для кризисных ситуаций"""
        return """
🚨 Я понимаю, что вы переживаете тяжелые чувства. 

Пожалуйста, обратитесь за немедленной помощью:
• Телефон доверия: 8-800-2000-122 (круглосуточно)
• Экстренная психологическая помощь: 112
• Кризисная психологическая помощь: 8-495-989-50-50

Не оставайтесь один на один с проблемой. Ваша жизнь бесценна.
"""

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logging.error(f"Update {update} caused error {context.error}")
        try:
            await update.message.reply_text("❌ Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.")
        except:
            pass

def main():
    """Запуск бота"""
    # Проверяем обязательные переменные окружения
    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        logging.error("Missing required environment variables: TELEGRAM_TOKEN or OPENAI_API_KEY")
        return
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Создаем экземпляр бота-психолога
    bot = PsychologistBot()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.VOICE, bot.handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    application.add_error_handler(bot.error_handler)
    
    # Запускаем бота
    port = int(os.environ.get('PORT', 10000))
    webhook_url = os.environ.get('WEBHOOK_URL')
    
    if webhook_url:
        # Используем webhook для продакшена
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TELEGRAM_TOKEN,
            webhook_url=f"{webhook_url}/{TELEGRAM_TOKEN}"
        )
        logging.info("Bot started with webhook")
    else:
        # Используем polling для разработки
        application.run_polling()
        logging.info("Bot started with polling")

if __name__ == '__main__':
    main()

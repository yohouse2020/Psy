import os
import logging
import tempfile
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import speech_recognition as sr
from gtts import gTTS
import openai
import requests
import io

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Конфигурация из переменных окружения
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

class PsychologistBot:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_text = """
👋 Добро пожаловать в кабинет психологической помощи!

Я - ваш виртуальный психолог, готовый выслушать и помочь. Вы можете:
• Отправлять голосовые сообщения
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
            voice_content = await voice_file.download_as_bytearray()
            
            # Используем временный файл
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_ogg:
                temp_ogg.write(voice_content)
                temp_ogg_path = temp_ogg.name

            # Распознавание речи напрямую из OGG
            text = await self.speech_to_text_ogg(temp_ogg_path)
            
            # Очистка временного файла
            os.unlink(temp_ogg_path)

            if text:
                await update.message.reply_text(f"🎤 Я услышал: _{text}_", parse_mode='Markdown')
                
                # Генерируем ответ психолога
                psychologist_response = await self.generate_psychologist_response(text)
                
                # Отправляем текстовый ответ
                await update.message.reply_text(psychologist_response)
                
            else:
                await update.message.reply_text("❌ Не удалось распознать речь. Попробуйте еще раз или напишите текстом.")

        except Exception as e:
            logging.error(f"Error processing voice: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке голосового сообщения. Попробуйте написать текстом.")

    async def speech_to_text_ogg(self, audio_path: str) -> str:
        """Преобразование речи в текст из OGG формата"""
        try:
            # Используем альтернативный метод распознавания
            import speech_recognition as sr
            
            # Создаем временный WAV файл без использования aifc
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name
            
            # Конвертируем используя системный ffmpeg
            os.system(f'ffmpeg -i "{audio_path}" "{temp_wav_path}" -y 2>/dev/null')
            
            with sr.AudioFile(temp_wav_path) as source:
                audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio, language='ru-RU')
            
            # Очистка
            if os.path.exists(temp_wav_path):
                os.unlink(temp_wav_path)
                
            return text
            
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            logging.error(f"Speech recognition error: {e}")
            return ""
        except Exception as e:
            logging.error(f"Audio processing error: {e}")
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
        """Генерация ответа в стиле психолога с использованием OpenAI"""
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
            return "Благодарю вас за доверие. Я внимательно вас выслушал и хочу отметить, что обращение за помощью - это важный шаг. Давайте вместе подумаем, как мы можем работать с этой ситуацией. Что вы чувствуете в данный момент?"

    async def check_crisis_situation(self, text: str) -> bool:
        """Проверка на кризисные ситуации"""
        crisis_keywords = ['суицид', 'самоубийство', 'умру', 'покончить', 'кризис', 'хочу умереть']
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in crisis_keywords)

    def get_crisis_response(self) -> str:
        """Ответ для кризисных ситуаций"""
        return """
🚨 Я понимаю, что вы переживаете тяжелые чувства. 

Пожалуйста, обратитесь за немедленной помощью:
• Телефон доверия: 8-800-2000-122 (круглосуточно)
• Экстренная психологическая помощь: 112
• Не оставайтесь один на один с проблемой

Ваша жизнь бесценна, и есть люди, которые готовы помочь.
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
            webhook_url=f"{webhook_url}/{TELEGRAM_TOKEN}",
            secret_token='WEBHOOK_SECRET'
        )
    else:
        # Используем polling для разработки
        print("🤖 Бот-психолог запущен в режиме polling...")
        application.run_polling()

if __name__ == '__main__':
    main()

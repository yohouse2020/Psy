import os
import logging
import tempfile
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import speech_recognition as sr
from gtts import gTTS
import openai
import io

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Конфигурация
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"

# Инициализация OpenAI
openai.api_key = OPENAI_API_KEY

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
            voice = update.message.voice
            voice_file = await voice.get_file()
            
            # Скачиваем голосовое сообщение
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_ogg:
                await voice_file.download_to_drive(temp_ogg.name)
                temp_ogg_path = temp_ogg.name

            # Конвертируем в WAV
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                temp_wav_path = temp_wav.name

            # Конвертация формата
            os.system(f'ffmpeg -i {temp_ogg_path} {temp_wav_path} -y')
            
            # Распознавание речи
            text = self.speech_to_text(temp_wav_path)
            
            # Очистка временных файлов
            os.unlink(temp_ogg_path)
            os.unlink(temp_wav_path)

            if text:
                await update.message.reply_text(f"🎤 Я услышал: _{text}_", parse_mode='Markdown')
                
                # Генерируем ответ психолога
                psychologist_response = await self.generate_psychologist_response(text)
                
                # Отправляем текстовый ответ
                await update.message.reply_text(psychologist_response)
                
                # Генерируем и отправляем голосовой ответ
                await self.send_voice_response(update, psychologist_response)
                
            else:
                await update.message.reply_text("❌ Не удалось распознать речь. Попробуйте еще раз.")

        except Exception as e:
            logging.error(f"Error processing voice: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке голосового сообщения.")

    def speech_to_text(self, audio_path: str) -> str:
        """Преобразование речи в текст"""
        try:
            with sr.AudioFile(audio_path) as source:
                audio = self.recognizer.record(source)
                text = self.recognizer.recognize_google(audio, language='ru-RU')
                return text
        except sr.UnknownValueError:
            return ""
        except sr.RequestError as e:
            logging.error(f"Speech recognition error: {e}")
            return ""

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        user_text = update.message.text
        
        # Генерируем ответ психолога
        response = await self.generate_psychologist_response(user_text)
        
        await update.message.reply_text(response)

    async def generate_psychologist_response(self, user_message: str) -> str:
        """Генерация ответа в стиле психолога с использованием OpenAI"""
        try:
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
            
            response = openai.ChatCompletion.create(
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

    async def send_voice_response(self, update: Update, text: str):
        """Преобразование текста в речь и отправка голосового сообщения"""
        try:
            # Ограничиваем длину текста для TTS
            if len(text) > 1000:
                text = text[:1000] + "..."
            
            # Создаем временный файл для аудио
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
                # Генерируем речь с помощью gTTS
                tts = gTTS(text=text, lang='ru', slow=False)
                tts.save(temp_audio.name)
                
                # Отправляем голосовое сообщение
                with open(temp_audio.name, 'rb') as audio_file:
                    await update.message.reply_voice(voice=audio_file)
                
                # Удаляем временный файл
                os.unlink(temp_audio.name)
                
        except Exception as e:
            logging.error(f"TTS error: {e}")
            # В случае ошибки TTS просто отправляем текстовый ответ

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logging.error(f"Update {update} caused error {context.error}")
        await update.message.reply_text("❌ Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже.")

def main():
    """Запуск бота"""
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
    print("🤖 Бот-психолог запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()

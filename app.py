import os
import logging
import tempfile
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import openai
import requests
import base64

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Конфигурация
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
ASSEMBLYAI_API_KEY = os.environ.get('ASSEMBLYAI_API_KEY')  # Опционально

class PsychologistBot:
    def __init__(self):
        pass
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = """
👋 Добро пожаловать в кабинет психологической помощи!

Я - ваш виртуальный психолог с поддержкой голосовых сообщений.

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

            # Конвертируем в MP3
            mp3_path = await self.convert_ogg_to_mp3(ogg_path)
            
            if mp3_path:
                # Распознаем речь используя разные методы
                text = await self.speech_to_text_alternative(mp3_path)
                
                # Удаляем временные файлы
                os.unlink(ogg_path)
                os.unlink(mp3_path)
                
                if text:
                    await update.message.reply_text(f"🎤 Я услышал: _{text}_", parse_mode='Markdown')
                    response = await self.generate_psychologist_response(text)
                    await update.message.reply_text(response)
                else:
                    await update.message.reply_text("❌ Не удалось распознать речь. Напишите текстом.")
            else:
                await update.message.reply_text("❌ Ошибка конвертации аудио.")

        except Exception as e:
            logging.error(f"Voice processing error: {e}")
            await update.message.reply_text("❌ Ошибка. Напишите текстом.")

    async def convert_ogg_to_mp3(self, ogg_path: str) -> str:
        """Конвертация OGG в MP3"""
        try:
            mp3_path = ogg_path.replace('.ogg', '.mp3')
            import subprocess
            result = subprocess.run([
                'ffmpeg', '-i', ogg_path, '-codec:a', 'libmp3lame', 
                '-qscale:a', '2', mp3_path, '-y'
            ], capture_output=True, text=True)
            return mp3_path if result.returncode == 0 else None
        except Exception as e:
            logging.error(f"Conversion error: {e}")
            return None

    async def speech_to_text_alternative(self, audio_path: str) -> str:
        """Альтернативное распознавание речи"""
        try:
            # Метод 1: Пробуем использовать Whisper через OpenAI
            return await self.speech_to_text_whisper(audio_path)
        except Exception as e:
            logging.error(f"Whisper failed: {e}")
            # Метод 2: Fallback на простую обработку
            return ""

    async def speech_to_text_whisper(self, audio_path: str) -> str:
        """Используем Whisper API для распознавания"""
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            with open(audio_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ru",
                    response_format="text"
                )
            return transcript
        except Exception as e:
            logging.error(f"Whisper API error: {e}")
            return ""

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        user_text = update.message.text
        response = await self.generate_psychologist_response(user_text)
        await update.message.reply_text(response)

    async def generate_psychologist_response(self, user_message: str) -> str:
        """Генерация ответа психолога"""
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты опытный психолог. Отвечай поддерживающе и профессионально."},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=500,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"OpenAI error: {e}")
            return "Спасибо за ваше сообщение. Я готов вас выслушать."

def main():
    if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
        logging.error("Missing environment variables")
        return
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    bot = PsychologistBot()
    
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(MessageHandler(filters.VOICE, bot.handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    
    port = int(os.environ.get('PORT', 10000))
    webhook_url = os.environ.get('WEBHOOK_URL')
    
    if webhook_url:
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TELEGRAM_TOKEN,
            webhook_url=f"{webhook_url}/{TELEGRAM_TOKEN}"
        )
    else:
        application.run_polling()

if __name__ == '__main__':
    main()

import os
import logging
import tempfile
import subprocess
import telebot
from telebot.types import Message
import openai

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# Создаем бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

class PsychologistBot:
    def __init__(self):
        pass

    def convert_ogg_to_wav(self, ogg_path: str):
        try:
            wav_path = ogg_path.replace('.ogg', '.wav')
            result = subprocess.run([
                'ffmpeg', '-i', ogg_path, wav_path, '-y'
            ], capture_output=True, timeout=30)
            return wav_path if result.returncode == 0 else None
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            return None

    def speech_to_text(self, wav_path: str):
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio = recognizer.record(source)
                return recognizer.recognize_google(audio, language='ru-RU')
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            return ""

    def generate_psychologist_response(self, user_message: str):
        try:
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты опытный психолог. Отвечай поддерживающе и профессионально."},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=400,
                temperature=0.7
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return "Благодарю за ваше сообщение. Я готов вас выслушать и поддержать."

psychologist = PsychologistBot()

@bot.message_handler(commands=['start'])
def start_handler(message: Message):
    welcome_text = """
👋 Добро пожаловать в кабинет психологической помощи!

Я - ваш виртуальный психолог. Вы можете:
• Отправлять голосовые сообщения 🎤
• Писать текстовые сообщения
• Получать профессиональную поддержку

Расскажите, что вас беспокоит...
    """
    bot.reply_to(message, welcome_text)

@bot.message_handler(content_types=['voice'])
def voice_handler(message: Message):
    try:
        bot.reply_to(message, "🎤 Обрабатываю ваше сообщение...")
        
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_ogg:
            temp_ogg.write(downloaded_file)
            ogg_path = temp_ogg.name

        wav_path = psychologist.convert_ogg_to_wav(ogg_path)
        
        if wav_path:
            text = psychologist.speech_to_text(wav_path)
            
            os.unlink(ogg_path)
            os.unlink(wav_path)
            
            if text and len(text.strip()) > 5:
                bot.reply_to(message, f"🎤 Я услышал: _{text}_", parse_mode='Markdown')
                response = psychologist.generate_psychologist_response(text)
                bot.reply_to(message, response)
            else:
                bot.reply_to(message, "❌ Не удалось распознать речь. Напишите текстом.")
        else:
            bot.reply_to(message, "❌ Ошибка конвертации аудио.")

    except Exception as e:
        logger.error(f"Voice error: {e}")
        bot.reply_to(message, "❌ Ошибка. Напишите текстом.")

@bot.message_handler(content_types=['text'])
def text_handler(message: Message):
    user_text = message.text
    
    crisis_keywords = ['суицид', 'самоубийство', 'умру', 'покончить']
    if any(keyword in user_text.lower() for keyword in crisis_keywords):
        crisis_response = """
🚨 Обратитесь за помощью:
• Телефон доверия: 8-800-2000-122
• Экстренная помощь: 112
"""
        bot.reply_to(message, crisis_response)
        return
    
    response = psychologist.generate_psychologist_response(user_text)
    bot.reply_to(message, response)

if __name__ == '__main__':
    logger.info("Starting bot...")
    bot.infinity_polling()

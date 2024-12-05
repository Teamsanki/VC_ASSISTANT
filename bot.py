import telebot
import openai
import pymongo
import pyttsx3
import tempfile
from google.cloud import speech_v1p1beta1 as speech
from pymongo import MongoClient
from config import TELEGRAM_TOKEN, MONGODB_URI, AI_API_KEY, GOOGLE_APPLICATION_CREDENTIALS

# MongoDB connection
client = MongoClient(MONGODB_URI)
db = client["telegram_bot"]
collection = db["conversations"]

# Set up the Telegram bot
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Setup OpenAI API for AI responses
openai.api_key = AI_API_KEY

# Google Cloud Speech-to-Text setup (ensure you've set up Google Cloud credentials)
speech_client = speech.SpeechClient.from_service_account_json(GOOGLE_APPLICATION_CREDENTIALS)

# Handle text messages from users
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    user_message = message.text

    # Save the conversation to MongoDB
    collection.insert_one({"user_id": user_id, "message": user_message})

    # Respond with AI-generated reply
    response = openai.Completion.create(
        model="gpt-3.5-turbo",
        prompt=user_message,
        max_tokens=150
    )
    ai_response = response.choices[0].text.strip()

    # Convert AI response to speech (Text-to-Speech)
    voice_file = text_to_speech(ai_response)

    # Send the voice message back to the user
    with open(voice_file, 'rb') as audio_file:
        bot.send_voice(message.chat.id, audio_file)

    # Save AI response to DB
    save_to_db(user_id, user_message, ai_response)

# Handle voice messages in VC
@bot.message_handler(content_types=['voice'])
def handle_voice(message):
    user_id = message.from_user.id
    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    # Transcribe the audio to text using Google Speech-to-Text
    transcribed_text = transcribe_audio(downloaded_file)

    # Save the conversation to MongoDB
    collection.insert_one({"user_id": user_id, "message": transcribed_text})

    # Get AI response
    response = openai.Completion.create(
        model="gpt-3.5-turbo",
        prompt=transcribed_text,
        max_tokens=150
    )
    ai_response = response.choices[0].text.strip()

    # Convert AI response to speech (Text-to-Speech)
    voice_file = text_to_speech(ai_response)

    # Send the voice message back to the VC (or to user if in DM)
    with open(voice_file, 'rb') as audio_file:
        bot.send_voice(message.chat.id, audio_file)

    # Save AI response to DB
    save_to_db(user_id, transcribed_text, ai_response)

# Convert text to speech and save it to a temporary file
def text_to_speech(text):
    engine = pyttsx3.init()
    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        tmp_file.close()
        engine.save_to_file(text, tmp_file.name)
        engine.runAndWait()
        return tmp_file.name

# Transcribe audio to text using Google Cloud Speech-to-Text
def transcribe_audio(audio_data):
    audio = speech.RecognitionAudio(content=audio_data)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
        sample_rate_hertz=16000,
        language_code="hi-IN",
    )

    response = speech_client.recognize(config=config, audio=audio)
    if response.results:
        return response.results[0].alternatives[0].transcript
    return "Sorry, I couldn't understand that."

# Save conversation to MongoDB
def save_to_db(user_id, message, response):
    collection.insert_one({
        "user_id": user_id,
        "message": message,
        "response": response
    })

# Start the bot
bot.polling()

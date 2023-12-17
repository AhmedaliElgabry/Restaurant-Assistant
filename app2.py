from flask import Flask, request, jsonify, send_from_directory, render_template
import openai
import os
import uuid
import time

app = Flask(__name__)

api_key = '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'
assistant_id = "asst_Z1OETDB8woLiHyzZyboXojBF"
openai.api_key = api_key

AUDIO_DIR = 'audio_responses'
RECORDS_DIR = 'records'
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(RECORDS_DIR, exist_ok=True)

client = openai.OpenAI(api_key=api_key)
thread = None
thread_active = False

def create_thread(client):
    global thread, thread_active
    thread = client.beta.threads.create()
    thread_active = True
    return thread

def send_message(client, thread_id, message_content):
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=message_content
    )

def get_response(client, thread_id, assistant_id):
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions="Answer the question as accurately as possible."
    )

    while True:
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )
        if run.status in ["completed", "succeeded"]:
            break
        else:
            print("Waiting for response...")
            time.sleep(1)

    messages = client.beta.threads.messages.list(
        thread_id=thread_id
    )
    return messages

def generate_corrected_transcript(temperature, system_prompt, transcript_):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # Ensure this is the correct model you want to use
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": transcript_
            }
        ]
    )
    return response.choices[0].message.content
@app.route('/message', methods=['POST'])
def message():
    global thread, thread_active

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    record_file_name = uuid.uuid4().hex + '.mp3'
    record_file_path = os.path.join(RECORDS_DIR, record_file_name)
    file.save(record_file_path)

    # Assuming transcription and assistant interaction is handled here
    # ...
    
# Transcribe the audio file using Whisper
    transcript = client.audio.transcriptions.create(
        model="whisper-1", 
        file=open(record_file_path, 'rb'),  # Open the file in binary read mode
        response_format="text"
    )

    user_input = transcript

    # Generate corrected transcript
    system_prompt = "Correct the following transcript:"
    user_input = generate_corrected_transcript(0.7, system_prompt, transcript)

    # Optionally remove the audio file after processing
    # os.remove(record_file_path)

    # Check if the thread is active, if not, create a new one
    if not thread_active:
        create_thread(client)

    send_message(client, thread.id, user_input)
    messages = get_response(client, thread.id, assistant_id)

    assistant_responses = []
    for msg in messages.data:
        if msg.role == "assistant":
            if isinstance(msg.content, list):
                for content in msg.content:
                    if hasattr(content, 'text'):
                        assistant_responses.append(content.text.value)
            else:
                if hasattr(msg.content, 'text'):
                    assistant_responses.append(msg.content.text.value)

    # Generate TTS audio from the first response
    if assistant_responses:
        text = assistant_responses[0]
        speech_file_name = f"{uuid.uuid4().hex}.mp3"

        # Assuming the OpenAI API provides a streaming response
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=assistant_response_text
        )

        # The response object might provide a method to write the stream to a file
        speech_file_path = os.path.join(AUDIO_DIR, speech_file_name)
        with open(speech_file_path, 'wb') as speech_file:
            for chunk in response.iter_content(chunk_size=4096):
                speech_file.write(chunk)



    return jsonify({
        "transcription": "Transcription would go here",
        "response_text": text,
        "audio_url": f"/audio/{speech_file_name}"
    })

@app.route('/audio/<filename>')
def get_audio(filename):
    return send_from_directory(AUDIO_DIR, filename)

@app.route('/')
def index():
    return render_template('intro.html')

@app.route('/end-thread', methods=['POST'])
def end_thread():
    global thread_active
    thread_active = False
    return "Conversation ended."

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

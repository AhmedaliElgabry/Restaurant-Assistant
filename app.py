from flask import Flask, request, jsonify, render_template
import openai
from tempfile import NamedTemporaryFile
from io import BytesIO
import os
import time 



app = Flask(__name__)

api_key = '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'
assistant_id = "asst_Z1OETDB8woLiHyzZyboXojBF"
openai.api_key = api_key

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


@app.route('/')
def index():
    return render_template('intro.html')


@app.route('/message', methods=['POST'])
def message():
    global thread, thread_active

    if not request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    print(file)
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Define the path where the file will be saved
    save_path = os.path.join('records', file.filename)

    # Ensure 'records' directory exists
    if not os.path.exists('records'):
        os.makedirs('records')

    # Save the file to the 'records' directory
    file.save(save_path)
    
    print(save_path)
    # Transcribe the audio file using Whisper
    transcript = client.audio.transcriptions.create(
        model="whisper-1", 
        file=open(save_path, 'rb'),  # Open the file in binary read mode
        response_format="text"
    )

    # Generate corrected transcript
    system_prompt = "Correct the following transcript:"
    corrected_transcript = generate_corrected_transcript(0.7, system_prompt, transcript)


    # Print the transcript in the terminal
    print("Transcript:", transcript)

    # Print the corrected transcript in the terminal
    print("Corrected Transcript:", corrected_transcript)

    
    print(type(transcript))
    user_input = corrected_transcript
    # Delete the file after processing
    #os.remove(save_path)

    # Check if the thread is active, if not, create a new one
    if not thread_active:
        create_thread(client)

    send_message(client, thread.id, user_input)
    # Process your messages
    messages = get_response(client, thread.id, assistant_id)

    # Initialize an empty list to hold the responses
    assistant_responses = []

    # Iterate over each message
    for msg in messages.data:
        if msg.role == "assistant":
            # Check if msg.content is a list and iterate over it
            if isinstance(msg.content, list):
                for content in msg.content:
                    if hasattr(content, 'text'):
                        assistant_responses.append(content.text.value)
            else:
                # Fallback for non-list content
                if hasattr(msg.content, 'text'):
                    assistant_responses.append(msg.content.text.value)

    return jsonify({
        "transcript": transcript, 
        "corrected_transcript": corrected_transcript,
        "responses": assistant_responses})

    return jsonify({"responses": assistant_responses})



@app.route('/end-thread', methods=['POST'])
def end_thread():
    global thread_active
    thread_active = False  # Mark the current thread as inactive
    return "Conversation ended."

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, request, jsonify, render_template
import tempfile
import requests
import os
from datetime import datetime
import uuid

app = Flask(__name__)

# In-memory storage for transcriptions (replace with database in production)
transcription_storage = {}

class SpeechToTextProcessor:
    def __init__(self, language="english"):
        """
        Initialize the speech to text processor.
        
        Args:
            language (str): Language for transcription (e.g., "english", "hindi")
        """
        self.language = language
        self.api_url = "https://asr.iitm.ac.in/internal/asr/decode"
    
    def transcribe_audio_file(self, audio_file_path):
        """Send audio file to ASR API and get transcription."""
        if not os.path.exists(audio_file_path):
            return {"status": "error", "message": f"File {audio_file_path} does not exist"}
            
        try:
            files = {
                'file': open(audio_file_path, 'rb'),
                'language': (None, self.language),
            }
            
            response = requests.post(self.api_url, files=files)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    return {
                        "status": "success", 
                        "transcript": result.get('transcript', ''),
                        "time_taken": result.get('time_taken', 0)
                    }
                else:
                    return {"status": "error", "message": result.get('reason', 'Unknown API error')}
            else:
                return {"status": "error", "message": f"HTTP Error: {response.status_code}"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}


@app.route('/')
def index():
    """Render the main application page."""
    return render_template('index.html')


@app.route('/api/transcribe', methods=['POST'])
def transcribe_audio():
    """
    Endpoint to transcribe uploaded audio file
    
    Request: 
        - Multipart form with 'audio_file' and 'language' field
    Response:
        - JSON with transcription result
    """
    if 'audio_file' not in request.files:
        return jsonify({"status": "error", "message": "No audio file provided"}), 400
    
    audio_file = request.files['audio_file']
    language = request.form.get('language', 'english')
    
    # Save the uploaded file temporarily
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_filename = temp_file.name
    temp_file.close()
    
    try:
        audio_file.save(temp_filename)
        
        # Process the audio file with the specified language
        processor = SpeechToTextProcessor(language=language)
        result = processor.transcribe_audio_file(temp_filename)
        
        # If successful, store the transcription
        if result["status"] == "success" and result.get("transcript"):
            transcription_id = str(uuid.uuid4())
            transcription_storage[transcription_id] = {
                'text': result["transcript"],
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'language': language
            }
            result["transcription_id"] = transcription_id
            result["language"] = language
        
        return jsonify(result)
    
    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_filename)
        except:
            pass


@app.route('/api/search', methods=['GET'])
def search_transcriptions():
    """
    Endpoint to search through stored transcriptions
    
    Request:
        - Query parameter 'q' for search term
    Response:
        - JSON with matching transcriptions
    """
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify({"status": "error", "message": "No search query provided"}), 400
    
    results = []
    for id, item in transcription_storage.items():
        if query in item['text'].lower():
            results.append({
                "id": id,
                "text": item['text'],
                "timestamp": item['timestamp'],
                "language": item['language']
            })
    
    return jsonify({
        "status": "success",
        "query": query,
        "count": len(results),
        "results": results
    })


@app.route('/api/transcriptions', methods=['GET'])
def get_all_transcriptions():
    """
    Endpoint to get all stored transcriptions
    
    Response:
        - JSON with all transcriptions
    """
    results = []
    for id, item in transcription_storage.items():
        results.append({
            "id": id,
            "text": item['text'],
            "timestamp": item['timestamp'],
            "language": item['language']
        })
    
    return jsonify({
        "status": "success",
        "count": len(results),
        "results": results
    })


@app.route('/api/transcriptions/<transcription_id>', methods=['GET'])
def get_transcription(transcription_id):
    """
    Endpoint to get a specific transcription by ID
    
    Response:
        - JSON with the transcription details
    """
    if transcription_id not in transcription_storage:
        return jsonify({"status": "error", "message": "Transcription not found"}), 404
    
    item = transcription_storage[transcription_id]
    return jsonify({
        "status": "success",
        "id": transcription_id,
        "text": item['text'],
        "timestamp": item['timestamp'],
        "language": item['language']
    })


if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    app.run(debug=True, port=5000) 
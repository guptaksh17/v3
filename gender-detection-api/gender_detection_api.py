import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
import base64
import json
from typing import Dict, Any
from datetime import datetime
import os
import tensorflow as tf
from tensorflow.keras.preprocessing.image import img_to_array
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:8081", "http://localhost:8082", "http://localhost:8083", "http://localhost:8084", "http://localhost:8085", "http://localhost:8086", "http://127.0.0.1:58857", "http://127.0.0.1:49724", "http://127.0.0.1:49965", "http://127.0.0.1:52288", "http://127.0.0.1:53967", "http://127.0.0.1:55193", "http://127.0.0.1:59233", "http://127.0.0.1:49327"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def create_model():
    model = Sequential([
        Conv2D(32, (3, 3), activation='relu', input_shape=(64, 64, 3)),
        MaxPooling2D((2, 2)),
        Conv2D(64, (3, 3), activation='relu'),
        MaxPooling2D((2, 2)),
        Flatten(),
        Dense(128, activation='relu'),
        Dropout(0.5),
        Dense(1, activation='sigmoid')  # Single output: 1 = female, 0 = male
    ])
    return model

# Load the pre-trained model
try:
    model = create_model()
    model.load_weights("gender_model.h5")
    logger.info("Model loaded successfully")
except Exception as e:
    logger.error(f"Error loading model: {e}")
    raise

# Initialize face detection cascade classifier
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def detect_faces(image):
    # Convert to grayscale for face detection
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # More lenient face detection parameters
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.2,  # More lenient scale factor (was 1.1)
        minNeighbors=3,   # Reduced from 5 to 3
        minSize=(60, 60)  # Slightly smaller minimum face size
    )
    
    if len(faces) == 0:
        return None
    
    # Get the largest face
    largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
    x, y, w, h = largest_face
    
    # Add padding around the face (20%)
    padding_x = int(w * 0.2)
    padding_y = int(h * 0.2)
    
    # Ensure padded coordinates are within image bounds
    start_x = max(x - padding_x, 0)
    start_y = max(y - padding_y, 0)
    end_x = min(x + w + padding_x, image.shape[1])
    end_y = min(y + h + padding_y, image.shape[0])
    
    face_img = image[start_y:end_y, start_x:end_x]
    return face_img if face_img.size > 0 else None

def preprocess_image(face):
    """Preprocess image for gender detection."""
    try:
        # Resize to match model's expected input
        face_resized = cv2.resize(face, (64, 64))
        
        # Normalize pixel values
        face_array = face_resized.astype("float32") / 255.0
        
        # Convert to array and add batch dimension
        face_array = img_to_array(face_array)
        face_array = np.expand_dims(face_array, axis=0)
        
        return face_array
    except Exception as e:
        return None

def base64_to_image(data):
    try:
        # Decode base64 image
        img_data = base64.b64decode(data.split(',')[1])
        nparr = np.frombuffer(img_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return frame
    except Exception as e:
        return None

def predict_gender(processed_face):
    """Predict gender from preprocessed face image."""
    try:
        # Get prediction
        prediction = model.predict(processed_face, verbose=0)
        female_confidence = float(prediction[0][0])
        male_confidence = 1.0 - female_confidence
        
        logger.info("=" * 50)
        logger.info("Gender Prediction Results:")
        logger.info(f"Female confidence: {female_confidence:.4f} ({female_confidence*100:.1f}%)")
        logger.info(f"Male confidence: {male_confidence:.4f} ({male_confidence*100:.1f}%)")
        
        # Strict verification rules
        is_female = female_confidence > 0.7 and male_confidence < 0.3
        logger.info(f"Verification rules:")
        logger.info(f"- Female confidence > 0.7: {female_confidence > 0.7}")
        logger.info(f"- Male confidence < 0.3: {male_confidence < 0.3}")
        logger.info(f"Final result: {'✅ VERIFIED' if is_female else '❌ NOT VERIFIED'}")
        logger.info("=" * 50)
        
        if is_female:
            return True, None
        else:
            return False, f"Unable to verify as female user (Female: {female_confidence*100:.1f}%, Male: {male_confidence*100:.1f}%)"
            
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        return False, f"Error predicting gender: {str(e)}"

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        client_id = str(datetime.now().timestamp())
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected. Total connections: {len(self.active_connections)}")
        return client_id

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected. Total connections: {len(self.active_connections)}")

    async def send_message(self, client_id: str, message: Dict[str, Any]):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to client {client_id}: {e}")
                await self.disconnect(client_id)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    last_process_time = 0
    min_interval = 0.5  # Minimum 0.5 seconds between processing frames
    
    try:
        while True:
            data = await websocket.receive_text()
            
            # Skip processing if it's too soon since last frame
            current_time = time.time()
            if current_time - last_process_time < min_interval:
                continue
                
            if data == "start_stream":
                continue
                
            try:
                # Process frame
                frame = base64_to_image(data)
                if frame is None:
                    logger.error("Invalid image data received")
                    await websocket.send_json({"error": "Invalid image data"})
                    continue
                    
                # Detect face
                face = detect_faces(frame)
                if face is None:
                    logger.info("No face detected in frame")
                    await websocket.send_json({"error": "No face detected - please ensure your face is clearly visible and well-lit"})
                    continue
                    
                # Preprocess for model
                processed_face = preprocess_image(face)
                if processed_face is None:
                    logger.error("Error preprocessing face image")
                    await websocket.send_json({"error": "Error processing image"})
                    continue
                    
                # Get prediction
                is_female, error_msg = predict_gender(processed_face)
                
                # Update last process time
                last_process_time = current_time
                
                # Send response
                response = {"success": is_female}
                if not is_female:
                    response["error"] = error_msg
                    
                logger.info(f"Sending response: {response}")
                await websocket.send_json(response)
                    
            except Exception as e:
                logger.error(f"Error processing frame: {str(e)}")
                await websocket.send_json({"error": "Error processing image"})
                
    except WebSocketDisconnect:
        logger.info("Client disconnected")

# Start the server
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8001)
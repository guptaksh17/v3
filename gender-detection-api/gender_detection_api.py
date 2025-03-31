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
    """Detect faces in the image using OpenCV's DNN face detector"""
    # Convert to grayscale for face detection
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Load the face detection model
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    # Detect faces with more lenient parameters
    faces = face_cascade.detectMultiScale(
        gray,
        scaleFactor=1.1,  # More precise scaling
        minNeighbors=5,   # Increased for better accuracy
        minSize=(80, 80), # Increased minimum face size
        flags=cv2.CASCADE_SCALE_IMAGE
    )
    
    face_images = []
    for (x, y, w, h) in faces:
        # Add more padding around the face
        padding = int(min(w, h) * 0.3)  # 30% padding
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(image.shape[1], x + w + padding)
        y2 = min(image.shape[0], y + h + padding)
        
        face = image[y1:y2, x1:x2]
        face_images.append(face)
    
    return face_images

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

def predict_gender(face_image):
    """Predict gender from face image"""
    try:
        # Preprocess the image
        processed_image = preprocess_image(face_image)
        
        # Get prediction
        prediction = model.predict(processed_image, verbose=0)[0][0]
        female_confidence = float(prediction)
        male_confidence = float(1 - prediction)
        
        # Log detailed prediction results
        logger.info("==================================================")
        logger.info("Gender Prediction Results:")
        logger.info(f"Female confidence: {female_confidence:.4f} ({female_confidence*100:.1f}%)")
        logger.info(f"Male confidence: {male_confidence:.4f} ({male_confidence*100:.1f}%)")
        
        # More balanced verification rules
        logger.info("Verification rules:")
        logger.info(f"- Female confidence > 0.6: {female_confidence > 0.6}")
        
        # Simplified verification rule with 60% threshold
        is_female = female_confidence > 0.6
        
        logger.info(f"Final result: {'✅ VERIFIED' if is_female else '❌ NOT VERIFIED'}")
        logger.info("==================================================")
        
        return is_female, female_confidence, male_confidence
        
    except Exception as e:
        logger.error(f"Error in gender prediction: {str(e)}")
        return False, 0.0, 0.0

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
    logger.info("connection open")
    
    try:
        last_process_time = 0
        while True:
            try:
                # Receive frame data
                data = await websocket.receive_text()
                
                # Skip if not enough time has passed since last process
                current_time = time.time()
                if current_time - last_process_time < 0.5:  # Process every 500ms
                    continue
                
                # Decode base64 image
                try:
                    # Remove data URL prefix if present
                    if data.startswith('data:image/jpeg;base64,'):
                        data = data.split(',')[1]
                    
                    # Decode base64 to bytes
                    image_data = base64.b64decode(data)
                    nparr = np.frombuffer(image_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if frame is None:
                        logger.error("Failed to decode image")
                        continue
                        
                except Exception as e:
                    logger.error(f"Error decoding image: {str(e)}")
                    continue
                
                # Detect face
                faces = detect_faces(frame)
                if not faces:
                    logger.info("No faces detected in frame")
                    await websocket.send_json({"error": "No face detected - please ensure your face is clearly visible and well-lit"})
                    continue
                
                # Get prediction
                is_female, female_confidence, male_confidence = predict_gender(faces[0])
                
                # Update last process time
                last_process_time = current_time
                
                # Send response
                response = {
                    "success": is_female,
                    "female_confidence": female_confidence,
                    "male_confidence": male_confidence
                }
                
                if not is_female:
                    response["error"] = f"Unable to verify as female user (Female: {female_confidence*100:.1f}%, Male: {male_confidence*100:.1f}%)"
                
                logger.info(f"Sending response: {response}")
                await websocket.send_json(response)
                    
            except WebSocketDisconnect:
                logger.info("Client disconnected")
                break
            except Exception as e:
                logger.error(f"Error processing frame: {str(e)}")
                await websocket.send_json({"error": f"Error processing frame: {str(e)}"})
                continue
                
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        logger.info("connection closed")

# Start the server
if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8005)
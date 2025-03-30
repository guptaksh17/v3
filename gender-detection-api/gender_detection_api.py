import os
import cv2
import numpy as np
import tensorflow as tf
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Load the trained model
model_path = os.path.join(os.path.dirname(__file__), "gender_model.h5")
model = tf.keras.models.load_model(model_path)

# Load OpenCV face detector
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:58857", "http://127.0.0.1:49724"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def predict_gender(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)

    if len(faces) == 0:
        return {"error": "No face detected"}

    for (x, y, w, h) in faces:
        face = frame[y:y+h, x:x+w]
        face = cv2.resize(face, (64, 64))
        face = face / 255.0
        face = np.expand_dims(face, axis=0)

        prediction = model.predict(face, verbose=0)[0][0]
        gender = "female" if prediction > 0.5 else "male"
        confidence = prediction if prediction > 0.5 else 1 - prediction
        
        return {
            "gender": gender,
            "confidence": float(confidence)
        }

@app.post("/predict")
async def detect_gender(file: UploadFile = File(...)):
    image = await file.read()
    result = predict_gender(image)
    return result

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
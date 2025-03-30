from gender_detection import create_model

# Create and save an empty model with the same architecture
model = create_model()
model.save('gender_model.h5')
print("Created empty model file 'gender_model.h5'. Please copy your trained model weights to this file.")

import face_recognition

image = face_recognition.load_image_file("test.jpg")
locations = face_recognition.face_locations(image)
encodings = face_recognition.face_encodings(image, locations)

print("Faces found:", len(locations))

if encodings:
    print("Encoding length:", len(encodings[0]))
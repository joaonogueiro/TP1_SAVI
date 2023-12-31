#!/usr/bin/env python3
# Sistemas Avançados de Visão Industrial (SAVI 23-24)
# Grupo 6, DEM, UA
# Afonso Miranda, nMec100090
# João Nogueiro, nMec111807
# Ricardo Bastos, nMec103983

import copy
import face_recognition
import cv2
import numpy as np
from track import Detection, Track, computeIOU
import os
import pyttsx3
import threading
from random import randint

# Console menu to Add or Edit a person to the Database
def menu():
        print("""
        (1) Add Person to Database
        (2) Edit Names of Database
        (q) Exit
          """)
        
        while True:
            op = input("\nOption: ")

            # Adds unknown face to Database 
            if op == '1':
                if len(Unknown_face_names) == 0:
                    print("No unknown faces saved")
                    continue

                print("Who do you want to add to the database?\n")

                # Print the Unknown names
                for i in range(len(Unknown_face_names)):
                    print(f"({i}) {Unknown_face_names[i]}")
                
                print("\n")

                # Select the idx of person who what add database
                person_idx = input("Index: ")

                while int(person_idx) not in range(len(Unknown_face_names)):
                    print("Out of range")
                    person_idx = input("Person: ")
                    if person_idx == 'e':
                        break

                name = input("What is your name? ")

                # Exception Handling to avoid "corrupted" detections
                try:
                    cv2.imwrite("Database/" + name + ".jpg", Unknown_image[int(person_idx)])
                    image = face_recognition.load_image_file("Database/" + name + ".jpg")
                    image_encoding = face_recognition.face_encodings(image)[0]
                    known_face_encodings.append(image_encoding)
                    known_face_names.append(name)
                    database_photos.append(image)

                    Unknown_face_names.pop(int(person_idx)) 
                    Unknown_face_encodings.pop(int(person_idx))
                    Unknown_image.pop(int(person_idx))

                except cv2.error:
                    print("Corrupted Face Detection. Deleting Detection...")
                    Unknown_face_names.pop(int(person_idx)) 
                    Unknown_face_encodings.pop(int(person_idx))
                    Unknown_image.pop(int(person_idx))

                except IndexError:
                    print("Corrupted Face Detection. Deleting Detection...")
                    Unknown_face_names.pop(int(person_idx)) 
                    Unknown_face_encodings.pop(int(person_idx))
                    Unknown_image.pop(int(person_idx))
            
            # Edits unknown face to Database 
            elif op == '2':

                if len(known_face_names) == 0:
                    print("No known faces saved")
                    continue

                print("What name do you want to change?")
                
                for i in range(len(known_face_names)):
                    print(f"  ({i}) {known_face_names[i]}")

                while True:
                    person_idx = int(input("Index: "))
                    if person_idx in range(len(known_face_names)):
                        break
                    else:
                        print("Out of range")

                new_name = str(input("Press 'q' if you want to cancel\nNew name? "))
                if new_name == 'q':
                    break
                old_name = known_face_names[person_idx]
                known_face_names[person_idx] = new_name

                old_file = f"Database/{old_name}.jpg"
                new_file = f"Database/{new_name}.jpg"
                os.rename(old_file, new_file)

            elif op == 'q':
                print("Exit program...")
                break
            
            else:
                print("Invalid option. Try again.")


def main():

    # --------------------------------------
    # Initialization
    # --------------------------------------

    cap = cv2.VideoCapture(0)   # Initializing webcam

    # Global variables
    global known_face_names
    global known_face_encodings
    global Unknown_face_names
    global Unknown_face_encodings
    global Unknown_image
    global database_photos
    global data_show
    global engine
    global hellos
    
    # Create arrays of known and Unknown face encodings and their names
    known_face_encodings = []
    known_face_names = []
    Unknown_face_encodings = []
    Unknown_face_names = []
    Unknown_image = []
    database_photos = []
    tracks = []

    # Parameters
    deactivate_threshold = 5.0 # secs
    iou_threshold = 0.3
    person_count = 0
 
    # Read database of saved images
    directory_path = "Database"
    if len(os.listdir(directory_path)) != 0:
        for file in os.listdir(directory_path):
            if len(os.listdir(directory_path)) == 0:
                break

            if file.endswith(".jpg"):
                image = face_recognition.load_image_file("Database/" + file)
                image_encoding = face_recognition.face_encodings(image)[0]
                known_face_encodings.append(image_encoding)
                known_face_names.append(file.rsplit('.', 1)[0].capitalize())
                database_photos.append(image)

    # Initialize some variables
    face_locations = []
    face_encodings = []
    face_names = []
    process_this_frame = True
    len_old_database = 0
    Unknown_num = 0
    old_known_face_names = []
    video_frame_number = 0
    
    # Initialization voice greeting
    hellos = []
    engine = pyttsx3.init()

    print("""
    ################################## 
         TP1_SAVI - Face Tracker       

    Afonso Simões, nMec100090
    João Nogueiro, nMec111807
    Ricardo Bastos, nMec103983
    ###################################
          """)
    
    # Initialitazion Menu - Threading
    menu_thread = threading.Thread(target=menu, args=())
    menu_thread.start()

    # --------------------------------------
    # Execution
    # --------------------------------------
    while(cap.isOpened()): # iterate video frames
        
        # Grab a single frame of video
        result, image_rgb = cap.read() # Capture frame-by-frame
        if result is False:
            break

        frame_stamp = round(float(cap.get(cv2.CAP_PROP_POS_MSEC))/1000,2)
        height, width, _ = image_rgb.shape
        image_gui = copy.deepcopy(image_rgb) # good practice to have a gui image for drawing
        
        # ------------------------------------------------------
        # Detect people using Face Recognition
        # ------------------------------------------------------

        # Only process every other frame of video to save time
        if process_this_frame:
            # Resize frame of video to 1/2 size for faster face recognition processing
            small_frame = cv2.resize(image_rgb, (0, 0), fx=0.5, fy=0.5)

            # Convert the image from BGR color (which OpenCV uses) to RGB color (which face_recognition uses)
            rgb_small_frame = np.ascontiguousarray(small_frame[:, :, ::-1])     #Invert the color channels

            # Find all the faces and face encodings in the current frame of video
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations) # "Return the 128-dimension face encoding for each face in the image"

            face_names = []

            # Checks if found faces locations are of known faces
            for idx, face_encoding in enumerate(face_encodings):
                
                name = None
                
                # See if the face is a match for the known face(s)
                if len(known_face_encodings) != 0:
                
                    matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.7)
                    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                    best_match_index = np.argmin(face_distances)
                    
                    if matches[best_match_index]:
                        name = known_face_names[best_match_index]
                        if name not in hellos:
                            engine.say("Hello " + name)
                            engine.runAndWait()
                            hellos.append(name)

                if len(Unknown_face_encodings) != 0:
                 
                    matches = face_recognition.compare_faces(Unknown_face_encodings, face_encoding, tolerance=0.7)
                    face_distances = face_recognition.face_distance(Unknown_face_encodings, face_encoding)
                    best_match_index = np.argmin(face_distances)
               
                    if matches[best_match_index]:
                        name = Unknown_face_names[best_match_index]


                if name == None:
                    name = "Unknown_" + str(Unknown_num)
                    Unknown_image.append(small_frame[face_locations[idx][0]-30:face_locations[idx][2]+30, face_locations[idx][3]-30:face_locations[idx][1]+30])
                    Unknown_face_encodings.append(face_encoding)
                    Unknown_face_names.append(name)
                    Unknown_num +=1

                face_names.append(name)

        process_this_frame = not process_this_frame 

        # ------------------------------------------------------
        # Create list of detections
        # ------------------------------------------------------

        detections = []
        detection_idx = 0
        for top, right, bottom, left in face_locations:
            name_detec = face_names[detection_idx] 
            detection_id = str(video_frame_number) + '_' +  str(detection_idx)
            detection = Detection(left, right, top, bottom, detection_id, frame_stamp, name_detec)
            detections.append(detection)
            detection_idx += 1

        all_detections = copy.deepcopy(detections)

         # ------------------------------------------------------
        # Association step. Associate detections with tracks
        # ------------------------------------------------------
        idxs_detections_to_remove = []
        for idx_detection, detection in enumerate(detections):
            for track in tracks:
                if not track.active:
                    continue
  
                # --------------------------------------
                # Using IOU 
                # --------------------------------------
                iou = computeIOU(detection, track.detections[-1])
          
                if iou > iou_threshold: # This detection belongs to this tracker!!!
                    track.update(detection) # add detection to track
                    idxs_detections_to_remove.append(idx_detection)
                    break # do not test this detection with any other track

        idxs_detections_to_remove.reverse()

        # --------------------------------------
        # Create new trackers
        # --------------------------------------
        for detection in detections:
            color = (randint(0, 255), randint(0, 255), randint(0, 255))
            track = Track('T' + str(person_count), detection, color=color)
            tracks.append(track)
            person_count += 1

        # --------------------------------------
        # Deactivate tracks if last detection has been seen a long time ago
        # --------------------------------------
        for track in tracks:
            time_since_last_detection = frame_stamp - track.detections[-1].stamp
            if time_since_last_detection > deactivate_threshold:
                track.active = False
   
        # --------------------------------------
        # Visualization
        # --------------------------------------
        
        # Draw list of all detections (including those associated with the tracks)
        for detection in all_detections:
            detection.draw(image_gui, (255,0,0))

            # Draw list of tracks
        for track in tracks:
            if not track.active:
                continue
            track.draw(image_gui)

        # Show database in new window
        if len(database_photos) > len_old_database or old_known_face_names != known_face_names:

            if len(database_photos) == 0:
                break

            cv2.namedWindow('Database',cv2.WINDOW_NORMAL)
            cv2.moveWindow('Database', 0, int(height)+30)
                        
            images = copy.deepcopy(database_photos)
            max_height = max(image.shape[0] for image in database_photos)

            for i, image in enumerate(images):
                # Height adjustment according to the minimum height
                if image.shape[0] < max_height:
                    scale_factor = max_height / image.shape[0]

                    images[i] = cv2.resize(image, (int(image.shape[1] * scale_factor), max_height))
        
            combined_width = sum(image.shape[1] for image in images)
            combined_image = np.zeros((max_height, combined_width, 3), dtype=np.uint8)
            
            # Put the names in each the database image 
            for i in range(len(images)):
                cv2.rectangle(images[i], (0,0), (120,20), (0, 0, 0), cv2.FILLED)
                cv2.putText(images[i], str(known_face_names[i]), (5,20), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 1, cv2.LINE_AA)

            current_width = 0
            for image in images:
                combined_image[:image.shape[0], current_width:current_width + image.shape[1]] = image
                current_width += image.shape[1]

            data_show = np.ascontiguousarray(combined_image[:, :, ::-1])
                        
            cv2.resizeWindow('Database', int(width), 300)
            cv2.imshow('Database', data_show)
            len_old_database = len(database_photos)
            old_known_face_names = copy.deepcopy(known_face_names)

        # Initialize main window
        if video_frame_number == 0:
            cv2.namedWindow('FaceTracker',cv2.WINDOW_NORMAL)
            cv2.resizeWindow('FaceTracker', int(width), int(height))

        # Add frame number and time to top left corner
        cv2.putText(image_gui, 'Frame ' + str(video_frame_number) + ' Time ' + str(frame_stamp) + ' secs',
                    (10,40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2, cv2.LINE_AA)

        # Display the resulting image
        cv2.imshow('FaceTracker',image_gui)
        cv2.moveWindow('FaceTracker', 0, 0)
        
        # Hit 'q' on the keyboard to quit
        if cv2.waitKey(1) & 0xFF == ord('q') :
            break

        video_frame_number += 1
    
if __name__ == "__main__":
    main()
import cv2
import mediapipe as mp
from collections import deque
import numpy as np
from pymongo import MongoClient

mp_hands = mp.solutions.hands
hands = mp_hands.Hands()

# Colors for drawing
colors = [(0, 0, 255), (0, 255, 0), (255, 0, 0), (255, 255, 0), (0, 255, 255)]
color_names = ["Red", "Green", "Blue", "Cyan", "Yellow"]

class VideoCamera(object):
    def __init__(self):
        # Initialize variables for drawing
        self.bpoints = [deque(maxlen=512)]
        self.gpoints = [deque(maxlen=512)]
        self.rpoints = [deque(maxlen=512)]
        self.cpoints = [deque(maxlen=512)]
        self.ypoints = [deque(maxlen=512)]
        self.undopoints = [deque(maxlen=512)]
        self.blue_index = self.green_index = self.red_index = self.yellow_index = self.cyan_index = self.all_index = 0
        
        self.colorIndex = 0
        self.drawing_color = (0, 0, 0)
        
        self.last_draw_point = None
        self.is_drawing = False
        
        # Get the default window size
        self.window_width = 0
        self.window_height = 0
        self.sidebar_width = 0
        self.color_block_height = 0

        # Initialize video capture object
        self.video = None

    def __del__(self):
        if self.video is not None:
            self.video.release()

    def get_frame(self):
        if self.video is None:
            # Initialize video capture object if not already initialized
            try:
                self.video = cv2.VideoCapture(0)  # Use -1 or 0 as camera index
                if not self.video.isOpened():
                    raise ValueError("Error: Unable to open webcam")
                
                # Get the default window size
                self.window_width = int(self.video.get(cv2.CAP_PROP_FRAME_WIDTH))
                self.window_height = int(self.video.get(cv2.CAP_PROP_FRAME_HEIGHT))
                self.sidebar_width = int(self.window_width // 5)
                self.color_block_height = int(self.window_height // len(colors))

                
            except Exception as e:
                print("Error initializing camera:", e)
                return None

        ret, frame = self.video.read()
        if not ret:
            return None

        frame = cv2.flip(frame, 1)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Find hand landmarks
        results = hands.process(frame_rgb)

        # Draw sidebar with color options
        for i, color in enumerate(colors):
            cv2.rectangle(frame, (int(self.window_width - self.sidebar_width), int(i * self.color_block_height)),
                        (int(self.window_width), int((i + 1) * self.color_block_height)), color, cv2.FILLED)
            cv2.putText(frame, color_names[i], (int(self.window_width - self.sidebar_width + 10),
                                                int((i + 1) * self.color_block_height - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Add 'clear' button
        clear_button_x = 20  # Adjust position as needed
        clear_button_y = 20
        cv2.rectangle(frame, (clear_button_x, clear_button_y - 20), (clear_button_x + 80, clear_button_y + 40), (128, 128, 128), cv2.FILLED)
        cv2.putText(frame, 'Clear', (clear_button_x + 5, clear_button_y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        # Reset drawing when thumb and index finger are far apart
        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            index_finger_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
            thumb_landmark = hand_landmarks.landmark[mp_hands.HandLandmark.THUMB_TIP]
            thumb_x, thumb_y = int(thumb_landmark.x * self.window_width), int(thumb_landmark.y * self.window_height)
            index_x, index_y = int(index_finger_landmark.x * self.window_width), int(index_finger_landmark.y * self.window_height)

            # Check if thumb and index finger are touching
            distance = np.sqrt((thumb_x - index_x) ** 2 + (thumb_y - index_y) ** 2)

            if index_x is not None and index_y is not None:
                # Check for 'undo' button activation
                if clear_button_x <= index_x <= clear_button_x + 60 and clear_button_y - 20 <= index_y <= clear_button_y + 20:
                    self.clear_drawing()

                
            # Select color
            if index_x > self.window_width - self.sidebar_width:
                self.colorIndex = int((index_y - 1) / self.color_block_height)

            # Draw circle on index finger with selected color
            cv2.circle(frame, (index_x, index_y), 10, colors[self.colorIndex], cv2.FILLED)

            # Start or stop drawing based on thumb and index finger proximity
            if distance < 30:
                if not self.is_drawing:
                    self.last_draw_point = (index_x, index_y)  # Store last drawing point
                self.is_drawing = True
                if self.drawing_color == (0, 0, 0):
                    self.drawing_color = colors[self.colorIndex]
            else:
                if self.is_drawing:
                    self.last_draw_point = None  # Reset last drawing point if drawing was ongoing
                self.is_drawing = False
                self.drawing_color = (0, 0, 0)

            # Draw when drawing is enabled
            if self.drawing_color != (0, 0, 0):
                if self.colorIndex == 0:
                    self.bpoints[self.blue_index].appendleft((index_x, index_y))
                elif self.colorIndex == 1:
                    self.gpoints[self.green_index].appendleft((index_x, index_y))
                elif self.colorIndex == 2:
                    self.rpoints[self.red_index].appendleft((index_x, index_y))
                elif self.colorIndex == 3:
                    self.cpoints[self.cyan_index].appendleft((index_x, index_y))
                elif self.colorIndex == 4:
                    self.ypoints[self.yellow_index].appendleft((index_x, index_y))
                self.undopoints[self.all_index].appendleft((index_x, index_y))

        # Draw lines for each color
        points = [self.bpoints, self.gpoints, self.rpoints, self.cpoints, self.ypoints]
        for i in range(len(points)):
            for j in range(len(points[i])):
                for k in range(1, len(points[i][j])):
                    if points[i][j][k - 1] is None or points[i][j][k] is None:
                        continue
                    cv2.line(frame, points[i][j][k - 1], points[i][j][k], colors[i], 2)
            
        ret, jpeg = cv2.imencode('.jpg', frame)
        return jpeg.tobytes()

    def clear_drawing(self):
        # Clear all drawing points
        self.bpoints = [deque(maxlen=512)]
        self.gpoints = [deque(maxlen=512)]
        self.rpoints = [deque(maxlen=512)]
        self.cpoints = [deque(maxlen=512)]
        self.ypoints = [deque(maxlen=512)]

    def save_to_mongodb(self, screenshot):
        client = MongoClient('mongodb://localhost:27017/')
        db = client['AirCanvas']
        collection = db['drawings']
        drawing_data = {
            'bpoints': list(self.bpoints[0]),  # Convert deque to list
            'gpoints': list(self.gpoints[0]),  # Convert deque to list
            'rpoints': list(self.rpoints[0]),  # Convert deque to list
            'cpoints': list(self.cpoints[0]),  # Convert deque to list
            'ypoints': list(self.ypoints[0]),  # Convert deque to list
            'blue_index': self.blue_index,
            'green_index': self.green_index,
            'red_index': self.red_index,
            'cyan_index': self.cyan_index,
            'yellow_index': self.yellow_index,
            'screenshot': screenshot
        }
        id = collection.insert_one(drawing_data).inserted_id
from flask import Flask, jsonify, render_template, Response, request
from camera import VideoCamera
from pymongo import MongoClient

app = Flask(__name__)
client = MongoClient('mongodb://localhost:27017/')
db = client['AirCanvas']
collection = db['drawings']

gcamera = None  # Global variable to hold camera object

def get_camera():
    global gcamera
    if gcamera is None and request.endpoint == 'video_feed':
        gcamera = VideoCamera()
    return gcamera

@app.route('/dashboard')
def index():
    return render_template('dashboard.html')

def gen(camera):
    while True:
        frame = camera.get_frame()
        if frame is None:
            break
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

@app.route('/video_feed')
def video_feed():
    camera = get_camera()
    return Response(gen(camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/clear_drawing', methods=['POST'])
def clear_drawing():
    camera = get_camera()
    # Call a method in VideoCamera to clear drawing
    camera.clear_drawing()
    return '', 204

@app.route('/undo_drawing', methods=['POST'])
def undo_drawing():
    camera = get_camera()
    # Call a method in VideoCamera to undo last drawing step
    camera.undo_drawing()
    return '', 204

@app.route('/save_drawing', methods=['POST'])
def save_drawing():
    # Save the drawing data to MongoDB
    data = request.json
    screenshot = data.get('screenshot')
    camera = get_camera()
    camera.save_to_mongodb(screenshot)
    return '', 204
    
@app.route('/new_screen')
def new_camera():
    return render_template('new_page.html')

@app.route('/recent_drawings')
def recent_drawing_page():
    return render_template('recent_drawings.html')

@app.route('/get_recent_drawings', methods=['GET'])
def recent_drawing_list():
    data = list(collection.find({}, {'_id': 0}))
    context = {
        'drawing_list': data
    }
    return jsonify(context)  

if __name__ == '__main__':
    app.run(host='0.0.0.0', port='7070', debug=True)

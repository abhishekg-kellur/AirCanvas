import json
from flask import Flask, jsonify, render_template, Response, request, send_file, session, redirect, url_for, sessions
from camera import VideoCamera
from pymongo import MongoClient
import flask_mysqldb
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
import base64
import os

app = Flask(__name__)
secret_key = os.urandom(24)
app.secret_key = secret_key

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'iq123'
app.config['MYSQL_DB'] = 'AirCanvas'
mysql = flask_mysqldb.MySQL(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

client = MongoClient('mongodb://localhost:27017/')
db = client['AirCanvas']
collection = db['drawings']

gcamera = None  # Global variable to hold camera object

def get_camera():
    global gcamera
    if gcamera is None and request.endpoint == 'video_feed':
        gcamera = VideoCamera()
    return gcamera

class User(UserMixin):
    pass

@login_manager.user_loader
def load_user(user_id):
    user = User()
    user.id = user_id
    return user

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        user = cursor.fetchone()
        cursor.close()
        if user:
            user_obj = User()
            user_obj.id = username
            login_user(user_obj)
            return redirect(url_for('dashboard'))
        else:
            return 'Invalid username or password'
    if gcamera is not None:
        gcamera.delete()
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def index():
    if gcamera is not None:
        gcamera.delete()
    return render_template('dashboard.html')

def gen(camera):
    while True:
        frame = camera.get_frame()
        if frame is None:
            break
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

@app.route('/image/<path:image_path>')
def get_image(image_path):
    full_path = '/home/abhishekg/Downloads/' + image_path
    return send_file(full_path, mimetype='image/png') 

@app.route('/video/<path:video_path>')
def get_video(video_path):
    full_path = '/home/abhishekg/Downloads/' + video_path
    return send_file(full_path, mimetype='video/webm') 

@app.route('/video_feed')
def video_feed():
    camera = get_camera()
    return Response(gen(camera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
    
@app.route('/drafted_video_feed')
def drafted_video_feed():
    bpoints = request.args.get('bpoints')
    gpoints = request.args.get('gpoints')
    rpoints = request.args.get('rpoints')
    cpoints = request.args.get('cpoints')
    ypoints = request.args.get('ypoints')

    # Create an instance of VideoCamera with points data
    dcamera = VideoCamera(bpoints, gpoints, rpoints, cpoints, ypoints)
    return Response(gen(dcamera),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/clear_drawing', methods=['POST'])
def clear_drawing():
    camera = get_camera()
    # Call a method in VideoCamera to clear drawing
    camera.clear_drawing()
    return '', 204

@app.route('/save_drawing', methods=['POST'])
def save_drawing():
    # Save the drawing data to MongoDB
    data = request.json
    filename = data.get('filename')
    videofile = data.get('videofile')
    camera = get_camera()
    camera.save_to_mongodb(filename, videofile)
    return '', 204
    
@app.route('/new_screen')
@login_required
def new_camera():
    if gcamera is not None:
        gcamera.delete()
    return render_template('new_page.html')

@app.route('/recent_drawings')
@login_required
def recent_drawing_page():
    if gcamera is not None:
        gcamera.delete()
    return render_template('recent_drawings.html')

@app.route('/export_sharing')
@login_required
def export_sharing():
    if gcamera is not None:
        gcamera.delete()
    # Logic for exporting and sharing drawings
    return render_template('export_sharing.html')

@app.route('/activity_feed')
@login_required
def activity_feed():
    if gcamera is not None:
        gcamera.delete()
    # Logic for displaying activity feed
    return render_template('activity_feed.html')

@app.route('/get_recent_drawings', methods=['GET'])
def recent_drawing_list():
    if gcamera is not None:
        gcamera.delete()
    data = list(collection.find({}, {'_id': 0}))
    
    # Construct image URLs for each drawing item
    for item in data:
        item['image_url'] = f'/image/{item["screenshot"]}'
    print("Actual data: ", data)
    context = {
        'drawing_list': data
    }
    return jsonify(context)

@app.route('/drafted_page')
def drafted_page():
    bpoints = session.get('bpoints')
    gpoints = session.get('gpoints')
    rpoints = session.get('rpoints')
    cpoints = session.get('cpoints')
    ypoints = session.get('ypoints')

    print("contents on click--------")
    print(bpoints, "\n", gpoints, "\n", rpoints, "\n", cpoints, "\n", ypoints)
    # Process the points data as needed

    return render_template('draft_page.html', bpoints=bpoints, gpoints=gpoints, rpoints=rpoints, cpoints=cpoints, ypoints=ypoints)


@app.route('/get_recent_recordings', methods=['GET'])
def recent_recording_list():
    if gcamera is not None:
        gcamera.delete()
    data = list(collection.find({}, {'_id': 0, 'videofile': 1}))
    print("data:", data)
    passingData = {}
    # Construct image URLs for each drawing item
    for item in data:
        if item:
            passingData['video_url'] = f'/video/{item["videofile"]}'
    context = {
        'video_list': [passingData]
    }
    return jsonify(context)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port='7070', debug=True)

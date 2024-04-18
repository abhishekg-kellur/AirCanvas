import json
from flask import Flask, jsonify, render_template, Response, request, send_file, session, redirect, url_for, session
from camera import VideoCamera
from pymongo import MongoClient
import flask_mysqldb
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required
from datetime import datetime, timedelta, timezone
import threading
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

def update_activity():
    if 'start_time' in session:
        print("Current time:", datetime.now().strftime("%H:%M:%S"))
        print("Session time:", session['start_time'])
        current_time_obj = datetime.strptime(datetime.now().strftime("%H:%M:%S"), "%H:%M:%S")
        start_time_obj = datetime.strptime(session['start_time'], "%H:%M:%S")
        elapsed_time = current_time_obj - start_time_obj
        return elapsed_time
        
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        user = cursor.fetchone()
        print("user:", user)
        if user:
            user_obj = User()
            user_obj.id = username
            login_user(user_obj)
            session['user_id'] = user[0]
            session['start_time'] = datetime.now().strftime("%H:%M:%S")
            print("type:", type(session['start_time']))
            cursor.close()
            
            return redirect('dashboard')
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
    objectid = request.args.get('docid')
    # Create an instance of VideoCamera with points data
    dcamera = VideoCamera(objectid)
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
    elapsed_time_formatted = update_activity()
    cursor = mysql.connection.cursor()
    cursor.execute(f"SELECT activity FROM users WHERE id = {session['user_id']}")
    dbTime = cursor.fetchone()
    print("dbTime:", dbTime)
    if dbTime[0]:
        elapsed_time_formatted += dbTime[0]
    return render_template('activity_feed.html', elapsed_time=elapsed_time_formatted)

@app.route('/get_recent_drawings', methods=['GET'])
def recent_drawing_list():
    if gcamera is not None:
        gcamera.delete()
    print("dsefsdf")
    user_data = list(collection.find({}))
    print("afterfbcjsddc")
    data = [{'id': str(doc['_id']), **doc} for doc in user_data]
    # Construct image URLs for each drawing item
    for item in data:
        del item['_id']
        item['image_url'] = f'/image/{item["screenshot"]}'
    print("Actual data: ", data)
    context = {
        'drawing_list': data
    }
    return jsonify(context)

@app.route('/drafted_page')
def drafted_page():
    objectid = request.args.get('objectid')
    print("contents on click--------")
    # Process the points data as needed
    return render_template('draft_page.html', objectid=objectid)


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
    if 'start_time' in session:
        elapsed_time_formatted = update_activity()
        cursor = mysql.connection.cursor()
        cursor.execute(f"SELECT activity FROM users WHERE id = {session['user_id']}")
        dbTime = cursor.fetchone()
        if dbTime[0]:
            elapsed_time_formatted += dbTime[0]
        cursor.execute('UPDATE users SET activity = %s WHERE id = %s', (str(elapsed_time_formatted), session['user_id']))
        mysql.connection.commit()
        cursor.close()
        session.pop('start_time')
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port='7070', debug=True)

from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
import re
import requests
from werkzeug.utils import secure_filename
import subprocess
import time
from main import main
import threading


app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
YOUTUBE_V3_KEY = os.getenv("YOUTUBE_V3_KEY")

# 首页，选择语言并展示上传页面
@app.route('/')
def index():
    return render_template('index.html')

# 处理上传或者YouTube链接
@app.route('/upload', methods=['POST'])
def upload():
    if 'youtube_link' in request.form and request.form['youtube_link'].strip():  # 处理YouTube链接
        youtube_link = request.form['youtube_link']
        pattern = r"v=([^&]+)"
        match = re.search(pattern, youtube_link).group(1)
        url = 'https://youtube.googleapis.com/youtube/v3/videos'
        params = {
            'part': 'snippet',
            'id': match,
            'key': YOUTUBE_V3_KEY
        }
        response = requests.request("GET", url, params=params, headers={'Accept': 'application/json'}, proxies={"http": None, "https": None})
        data = response.json()
        print(data)
        title = data["items"][0]["snippet"]["title"] + ".mp4"
        thumbnail_url = f'https://img.youtube.com/vi/{match}/sddefault.jpg'
        return redirect(url_for('result', video_name=title, video_thumbnail=thumbnail_url, url=youtube_link))
    elif 'file' in request.files:  # 处理文件上传
        file = request.files['file']
        filename = secure_filename(file.filename)
        print(filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        temp_dir = "temp"
        os.makedirs(temp_dir, exist_ok=True)
        timestamp = time.time()
        thumbnail_path = os.path.join(temp_dir, f"temp_{timestamp}.jpg")
        subprocess.run([
            'ffmpeg',
            '-i', filepath,
            '-ss', "00:00:01",
            '-vframes', '1',
            '-q:v', '2',
            thumbnail_path
        ], check=True)
        return redirect(url_for('result', video_name=filename, video_thumbnail=thumbnail_path, url=filepath))
# 结果页面
@app.route('/result')
def result():
    video_name = request.args.get('video_name')
    video_thumbnail = request.args.get('video_thumbnail')
    url = request.args.get('url')
    return render_template('result.html', video_name=video_name, video_thumbnail=video_thumbnail, url=url)

@app.route('/runCode', methods=['POST'])
def run_code():
    second = request.form.get('second')
    youtube_link = request.form.get('youtube_link')
    email_link = request.form.get('email_link')

    # 将数据传递给 main 方法
    thread = threading.Thread(target=main, args=(second, youtube_link, email_link))
    thread.start()

    # 跳转到 thanks 页面
    return redirect(url_for('thanks'))

@app.route('/thanks')
def thanks():
    return render_template('thanks.html')

VIDEO_FOLDER = os.path.join(os.getcwd(), 'Video_generated')

@app.route('/videos/<path:filename>')
def download_file(filename):
    return send_from_directory(VIDEO_FOLDER, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

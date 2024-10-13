import os
import re
import requests
import subprocess
import threading
import time
from celery_local import celery
from flask import Flask, render_template, jsonify, request, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename

from main import main
# from audio import create_audio_only

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
    print(request.form)
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
        response = requests.request("GET", url, params=params, headers={'Accept': 'application/json'},
                                    proxies={"http": None, "https": None})
        data = response.json()
        print(data)
        title = data["items"][0]["snippet"]["title"] + ".mp4"
        thumbnail_url = f'https://img.youtube.com/vi/{match}/sddefault.jpg'
        return jsonify({'video_name': title, 'video_thumbnail': thumbnail_url, 'url': youtube_link})
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
        return jsonify({'video_name': filename, 'video_thumbnail': thumbnail_path, 'url': filepath})


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
    sound_id = request.form.get('soundId')
    language = request.form.get('language')
    with_srt = 2

    main.delay(second, youtube_link, email_link, sound_id, language, with_srt)

    # 跳转到 thanks 页面
    return redirect(url_for('thanks'))

@app.route('/runCodeByUrl', methods=['POST'])
def run_code_by_url():
    second = request.form.get('second')
    youtube_link = request.form.get('youtube_link')
    email_link = request.form.get('email_link')
    sound_id = request.form.get('soundId')
    language = request.form.get('language')
    with_srt = 2

    main.delay(second, youtube_link, email_link, sound_id, language, with_srt)

    message = ""
    if language == "zh":
        message = "我们会将翻译好的视频发送到您的邮箱"
    elif language == "ja":
        message = "翻訳されたビデオをメールに送信します"
    else:
        message = "We will send the translated video to your email in several minutes"

    return message


@app.route('/thanks')
def thanks():
    return render_template('thanks.html')


# @ app.route('/audio')
# def audio():
#     data = request.json
#     message = data.get('message')
#     email = data.get('email')
#     thread = threading.Thread(target=main, args=(message, email))
#     thread.start()
#
#
# @app.route('/audio_creator')
# def audio_creator():
#     return render_template('only_audio.html')


VIDEO_FOLDER = os.path.join(os.getcwd(), 'Video_generated')
TEMP_FOLDER = os.path.join(os.getcwd(), 'temp')
ICON_FOLDER = os.path.join(os.getcwd(), 'icon')


@app.route('/videos/<path:filename>')
def download_file(filename):
    return send_from_directory(VIDEO_FOLDER, filename)


@app.route('/temp/<path:filename>')
def show_image(filename):
    return send_from_directory(TEMP_FOLDER, filename)


@app.route('/icon/<path:filename>')
def show_icon(filename):
    return send_from_directory(ICON_FOLDER, filename)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)

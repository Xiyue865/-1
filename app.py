from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import os
import time
import datetime
import threading
import uuid
import json
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 启用CORS，允许跨域请求

# 配置上传目录和允许的文件类型
UPLOAD_FOLDER = 'uploads'
AUDIO_FOLDER = 'uploads/audio'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav', 'ogg', 'flac'}

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AUDIO_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 存储上传进度的字典
upload_progress = {}

def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_audio_file(filename):
    """检查是否为音频文件"""
    audio_extensions = {'mp3', 'wav', 'ogg', 'flac'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in audio_extensions

@app.route('/')
def index():
    """渲染主页"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        # 生成唯一文件名
        filename = secure_filename(file.filename)
        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        
        # 创建上传进度条目
        upload_id = str(uuid.uuid4())
        upload_progress[upload_id] = {
            'filename': filename,
            'progress': 0,
            'status': 'uploading',
            'start_time': time.time(),
            'size': 0,
            'uploaded': 0
        }
        
        # 获取文件大小
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        upload_progress[upload_id]['size'] = file_size
        
        # 保存文件
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # 如果是音频文件，保存到音频文件夹
        if is_audio_file(filename):
            save_path = os.path.join(AUDIO_FOLDER, unique_filename)
        
        # 分块写入文件并更新进度
        chunk_size = 4096
        total_bytes = 0
        
        with open(save_path, 'wb') as f:
            while True:
                chunk = file.stream.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                total_bytes += len(chunk)
                progress = min(100, int((total_bytes / file_size) * 100))
                upload_progress[upload_id]['progress'] = progress
                upload_progress[upload_id]['uploaded'] = total_bytes
        
        # 记录上传完成时间
        upload_progress[upload_id]['end_time'] = time.time()
        upload_progress[upload_id]['status'] = 'completed'
        
        # 构建文件元数据
        file_metadata = {
            'id': unique_filename,
            'original_name': filename,
            'upload_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'size': file_size,
            'is_audio': is_audio_file(filename),
            'unique_filename': unique_filename
        }
        
        # 保存文件元数据
        metadata_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_filename}.meta")
        with open(metadata_path, 'w') as f:
            json.dump(file_metadata, f)
        
        return jsonify({
            'success': True,
            'upload_id': upload_id,
            'file_id': unique_filename,
            'message': 'File uploaded successfully'
        })
    else:
        return jsonify({'error': 'Invalid file type'}), 400

@app.route('/progress/<upload_id>')
def get_progress(upload_id):
    """获取上传进度"""
    progress = upload_progress.get(upload_id, {'progress': 0, 'status': 'unknown'})
    return jsonify(progress)

@app.route('/files')
def list_files():
    """列出所有上传的文件"""
    files = []
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if filename.endswith('.meta'):
            try:
                metadata_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                with open(metadata_path, 'r') as f:
                    file_data = json.load(f)
                    files.append(file_data)
            except Exception as e:
                print(f"Error loading metadata for {filename}: {e}")
    
    # 按上传日期排序，最新的在前
    files.sort(key=lambda x: x['upload_date'], reverse=True)
    return jsonify(files)

@app.route('/download/<file_id>')
def download_file(file_id):
    """下载文件"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], file_id)

@app.route('/audio/<file_id>')
def serve_audio(file_id):
    """提供音频文件访问"""
    return send_from_directory(AUDIO_FOLDER, file_id)

@app.route('/delete/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    """删除文件"""
    try:
        # 删除文件
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # 删除元数据文件
        meta_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}.meta")
        if os.path.exists(meta_path):
            os.remove(meta_path)
        
        return jsonify({'success': True, 'message': 'File deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)    
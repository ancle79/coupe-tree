from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
from datetime import datetime
import socket
import re

app = Flask(__name__)
CORS(app)

USERS_FILE = 'users.json'
POST_LIMIT = 200
DATA_DIR = 'data'

# Ensure data directory exists
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

PUBLIC_PARTITIONS = ["静苔之隅", "暖絮集", "风息岗", "萤语匣", "雾隐渡"]

def safe_filename(name):
    """Sanitize nickname or partition name for filesystem."""
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def get_posts_file_path(area, partition=None, nickname=None):
    if area == 'public':
        p = safe_filename(partition or PUBLIC_PARTITIONS[0])
        return os.path.join(DATA_DIR, f'posts_public_{p}.json')
    else:
        n = safe_filename(nickname or "unknown")
        return os.path.join(DATA_DIR, f'posts_personal_{n}.json')

def load_data(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_data(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Data Migration from old posts.json to separate files
def migrate_data():
    old_posts_file = 'posts.json'
    if os.path.exists(old_posts_file):
        print("发现旧数据文件 posts.json，开始迁移...")
        with open(old_posts_file, 'r', encoding='utf-8') as f:
            try:
                all_posts = json.load(f)
            except:
                all_posts = []
        
        for post in all_posts:
            area = post.get('area', 'public')
            partition = post.get('partition')
            nickname = post.get('nickname')
            
            # Ensure required fields for separate files
            if area == 'public' and not partition:
                partition = PUBLIC_PARTITIONS[0]
                post['partition'] = partition
            
            file_path = get_posts_file_path(area, partition, nickname)
            posts = load_data(file_path)
            
            # Check if post already exists in the new file (by ID, though not foolproof)
            if not any(p.get('id') == post.get('id') for p in posts):
                posts.append(post)
                save_data(file_path, posts)
        
        # Rename old file to mark migration as complete
        os.rename(old_posts_file, old_posts_file + '.migrated')
        print("迁移完成！")

migrate_data()

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    nickname = data.get('nickname')

    if not username or not password or not nickname:
        return jsonify({'error': '用户名、密码和昵称不能为空'}), 400

    users = load_data(USERS_FILE)
    if any(u['username'] == username for u in users):
        return jsonify({'error': '用户名已存在'}), 400
    if any(u['nickname'] == nickname for u in users):
        return jsonify({'error': '昵称已存在'}), 400

    new_user = {
        'id': len(users) + 1,
        'username': username,
        'password': password,
        'nickname': nickname,
        'notifications': []
    }
    users.append(new_user)
    save_data(USERS_FILE, users)
    return jsonify({'message': '注册成功', 'user': {'nickname': nickname, 'id': new_user['id']}}), 201

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    users = load_data(USERS_FILE)
    user = next((u for u in users if u['username'] == username and u['password'] == password), None)

    if user:
        return jsonify({'message': '登录成功', 'user': {'nickname': user['nickname'], 'id': user['id']}})
    return jsonify({'error': '用户名或密码错误'}), 401

@app.route('/api/posts', methods=['GET'])
def get_posts():
    area = request.args.get('area', 'public')
    partition = request.args.get('partition')
    nickname = request.args.get('nickname')

    file_path = get_posts_file_path(area, partition, nickname)
    filtered_posts = load_data(file_path)

    filtered_posts.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify(filtered_posts)

@app.route('/api/posts', methods=['POST'])
def add_post():
    data = request.json
    content = data.get('content')
    nickname = data.get('nickname', '匿名小树')
    user_id = data.get('user_id')
    area = data.get('area', 'public') # 'public' or 'personal'
    partition = data.get('partition')
    
    if not content:
        return jsonify({'error': '内容不能为空'}), 400
    
    if area == 'public' and partition not in PUBLIC_PARTITIONS:
        return jsonify({'error': '无效的分区'}), 400

    file_path = get_posts_file_path(area, partition, nickname)
    posts = load_data(file_path)
    
    # Check limit for the specific file
    if len(posts) >= POST_LIMIT:
        limit_msg = f'该分区帖子数量已达上限 ({POST_LIMIT}条)' if area == 'public' else f'您的个人区域帖子数量已达上限 ({POST_LIMIT}条)'
        return jsonify({'error': limit_msg}), 400

    new_post = {
        'id': int(datetime.now().timestamp() * 1000), # Use timestamp for more unique ID
        'nickname': nickname,
        'user_id': user_id,
        'content': content,
        'area': area,
        'partition': partition if area == 'public' else None,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'comments': []
    }
    posts.append(new_post)
    save_data(file_path, posts)
    
    return jsonify(new_post), 201

@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify({'error': '未提供用户ID'}), 400
    
    users = load_data(USERS_FILE)
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    return jsonify(user.get('notifications', []))

@app.route('/api/notifications/clear', methods=['POST'])
def clear_notifications():
    data = request.json
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': '未提供用户ID'}), 400
    
    users = load_data(USERS_FILE)
    user = next((u for u in users if u['id'] == user_id), None)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    user['notifications'] = []
    save_data(USERS_FILE, users)
    return jsonify({'message': '通知已清空'})

@app.route('/api/posts/<int:post_id>/comments', methods=['POST'])
def add_comment(post_id):
    data = request.json
    content = data.get('content')
    nickname = data.get('nickname', '匿名小树')
    # For comments, we need to know WHICH file the post belongs to.
    # The simplest way is to pass area and partition/nickname in the request.
    area = data.get('area', 'public')
    partition = data.get('partition')
    owner_nickname = data.get('owner_nickname')

    if not content:
        return jsonify({'error': '评论内容不能为空'}), 400

    file_path = get_posts_file_path(area, partition, owner_nickname)
    posts = load_data(file_path)
    post = next((p for p in posts if p['id'] == post_id), None)

    if not post:
        return jsonify({'error': '帖子不存在'}), 404
    
    if post.get('area') != 'public':
        return jsonify({'error': '个人区域帖子不支持评论'}), 403

    comment = {
        'id': len(post['comments']) + 1,
        'nickname': nickname,
        'content': content,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    post['comments'].append(comment)
    save_data(file_path, posts)

    # 发送通知给原作者
    author_id = post.get('user_id')
    if author_id and author_id != data.get('user_id'): # 如果有作者且评论者不是作者本人
        users = load_data(USERS_FILE)
        author = next((u for u in users if u['id'] == author_id), None)
        if author:
            if 'notifications' not in author:
                author['notifications'] = []
            
            # 限制通知数量，只保留最近的10条
            new_notification = {
                'id': int(datetime.now().timestamp() * 1000),
                'from_nickname': nickname,
                'post_content': post['content'][:20] + ('...' if len(post['content']) > 20 else ''),
                'comment_content': content[:30] + ('...' if len(content) > 30 else ''),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'partition': partition
            }
            author['notifications'].insert(0, new_notification)
            author['notifications'] = author['notifications'][:10]
            save_data(USERS_FILE, users)
    
    return jsonify(comment), 201

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == '__main__':
    local_ip = get_local_ip()
    print(f"\n" + "="*50)
    print(f"树洞服务器已就绪！")
    print(f"本地访问地址: http://127.0.0.1:5000")
    print(f"局域网内其他设备访问地址: http://{local_ip}:5000")
    print(f"异地外网访问: 请使用 ngrok 穿透 5000 端口")
    print("="*50 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False)

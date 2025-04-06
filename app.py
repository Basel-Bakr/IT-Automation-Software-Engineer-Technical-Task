from flask import Flask, request, jsonify
import sqlite3, hashlib
from datetime import datetime

app = Flask(__name__)
DATABASE = 'app.db'

# Utility: Get a connection to the database.
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Enable name-based access to columns.
    return conn

# Utility: Hash passwords using SHA-256.
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Helper: Check if a user exists by user_id.
def user_exists(user_id):
    with get_db_connection() as conn:
        user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    return user is not None

# Initialize the database and create tables if they do not exist.
def init_db():
    with get_db_connection() as conn:
        # Users table with username, email, and password.
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')
        # Tasks table with the required fields.
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                start_date TEXT,
                due_date TEXT,
                completion_date TEXT,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        # Subscriptions table for report subscriptions.
        conn.execute('''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                frequency TEXT CHECK(frequency IN ('daily', 'weekly', 'monthly')) NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        # Deleted tasks table to support restore functionality.
        conn.execute('''
            CREATE TABLE IF NOT EXISTS deleted_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                start_date TEXT,
                due_date TEXT,
                completion_date TEXT,
                status TEXT,
                deletion_time TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        conn.commit()
    print("Database initialized.")

# Initialize the DB on startup.
init_db()

# ---------------------------
# User Authentication Routes
# ---------------------------
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not username or not email or not password:
        return jsonify({'error': 'Username, email, and password are required'}), 400

    hashed = hash_password(password)
    try:
        with get_db_connection() as conn:
            conn.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                         (username, email, hashed))
            conn.commit()
        return jsonify({'message': 'User created'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'User already exists or email is already in use'}), 409

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not username or not email or not password:
        return jsonify({'error': 'Username, email, and password are required'}), 400

    hashed = hash_password(password)
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ? AND email = ? AND password = ?",
                            (username, email, hashed)).fetchone()

    if user:
        return jsonify({'message': 'Login successful', 'user_id': user['id']}), 200
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

# ---------------------------
# Task Management Routes (Authentication Required)
# ---------------------------
# All task endpoints require the header "X-User-Id" for authentication.

@app.route('/tasks', methods=['POST'])
def create_task():
    # Retrieve the authenticated user id from header.
    auth_user_id = request.headers.get('X-User-Id')
    if not auth_user_id:
        return jsonify({'error': 'Authentication required via X-User-Id header'}), 401
    try:
        auth_user_id = int(auth_user_id)
    except ValueError:
        return jsonify({'error': 'Invalid X-User-Id header'}), 400
    if not user_exists(auth_user_id):
        return jsonify({'error': 'User does not exist'}), 401

    data = request.get_json()
    title = data.get('title')
    description = data.get('description', '')
    start_date = data.get('start_date')  # Expected as ISO 8601 string.
    due_date = data.get('due_date')      # Expected as ISO 8601 string.
    completion_date = data.get('completion_date')  # Expected as ISO 8601 string, or null.
    status = data.get('status', 'pending')
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400

    with get_db_connection() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (user_id, title, description, start_date, due_date, completion_date, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (auth_user_id, title, description, start_date, due_date, completion_date, status)
        )
        conn.commit()
        task_id = cur.lastrowid
    return jsonify({'message': 'Task created', 'task_id': task_id}), 201

@app.route('/tasks', methods=['GET'])
def fetch_tasks():
    auth_user_id = request.headers.get('X-User-Id')
    if not auth_user_id:
        return jsonify({'error': 'Authentication required via X-User-Id header'}), 401
    try:
        auth_user_id = int(auth_user_id)
    except ValueError:
        return jsonify({'error': 'Invalid X-User-Id header'}), 400

    # Optional query parameters.
    status_filter = request.args.get('status')  # e.g., pending, completed, overdue.
    date_from = request.args.get('date_from')     # due_date lower bound.
    date_to = request.args.get('date_to')         # due_date upper bound.

    query = "SELECT * FROM tasks WHERE user_id = ?"
    params = [auth_user_id]

    if status_filter:
        status_filter = status_filter.lower()
        if status_filter in ['pending', 'completed']:
            query += " AND status = ?"
            params.append(status_filter)
        elif status_filter == 'overdue':
            now = datetime.now().isoformat()
            query += " AND due_date < ? AND status != 'completed'"
            params.append(now)
        else:
            return jsonify({'error': 'Invalid status filter'}), 400

    if date_from:
        query += " AND due_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND due_date <= ?"
        params.append(date_to)

    with get_db_connection() as conn:
        tasks = conn.execute(query, params).fetchall()

    tasks_list = []
    for task in tasks:
        tasks_list.append({
            'id': task['id'],
            'user_id': task['user_id'],
            'title': task['title'],
            'description': task['description'],
            'start_date': task['start_date'],
            'due_date': task['due_date'],
            'completion_date': task['completion_date'],
            'status': task['status']
        })
    return jsonify({'tasks': tasks_list}), 200

@app.route('/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id):
    auth_user_id = request.headers.get('X-User-Id')
    if not auth_user_id:
        return jsonify({'error': 'Authentication required via X-User-Id header'}), 401
    try:
        auth_user_id = int(auth_user_id)
    except ValueError:
        return jsonify({'error': 'Invalid X-User-Id header'}), 400

    with get_db_connection() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if task['user_id'] != auth_user_id:
        return jsonify({'error': 'Unauthorized: You do not have permission to view this task'}), 403

    return jsonify({
        'id': task['id'],
        'user_id': task['user_id'],
        'title': task['title'],
        'description': task['description'],
        'start_date': task['start_date'],
        'due_date': task['due_date'],
        'completion_date': task['completion_date'],
        'status': task['status']
    }), 200

@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    auth_user_id = request.headers.get('X-User-Id')
    if not auth_user_id:
        return jsonify({'error': 'Authentication required via X-User-Id header'}), 401
    try:
        auth_user_id = int(auth_user_id)
    except ValueError:
        return jsonify({'error': 'Invalid X-User-Id header'}), 400

    with get_db_connection() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if task['user_id'] != auth_user_id:
        return jsonify({'error': 'Unauthorized: You do not have permission to update this task'}), 403

    data = request.get_json()
    title = data.get('title')
    description = data.get('description')
    start_date = data.get('start_date')
    due_date = data.get('due_date')
    completion_date = data.get('completion_date')
    status = data.get('status')
    
    if not any([title, description, start_date, due_date, completion_date, status]):
        return jsonify({'error': 'No update data provided'}), 400

    with get_db_connection() as conn:
        conn.execute(
            "UPDATE tasks SET title = COALESCE(?, title), description = COALESCE(?, description), start_date = COALESCE(?, start_date), due_date = COALESCE(?, due_date), completion_date = COALESCE(?, completion_date), status = COALESCE(?, status) WHERE id = ?",
            (title, description, start_date, due_date, completion_date, status, task_id)
        )
        conn.commit()
    return jsonify({'message': 'Task updated'}), 200

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    auth_user_id = request.headers.get('X-User-Id')
    if not auth_user_id:
        return jsonify({'error': 'Authentication required via X-User-Id header'}), 401
    try:
        auth_user_id = int(auth_user_id)
    except ValueError:
        return jsonify({'error': 'Invalid X-User-Id header'}), 400

    with get_db_connection() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if task['user_id'] != auth_user_id:
        return jsonify({'error': 'Unauthorized: You do not have permission to delete this task'}), 403

    # Insert the deleted task into deleted_tasks with current timestamp.
    deletion_time = datetime.now().isoformat()
    with get_db_connection() as conn:
        conn.execute('''
            INSERT INTO deleted_tasks (user_id, title, description, start_date, due_date, completion_date, status, deletion_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (task['user_id'], task['title'], task['description'], task['start_date'], task['due_date'], task['completion_date'], task['status'], deletion_time))
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
    return jsonify({'message': 'Task deleted'}), 200

# ---------------------------
# Batch Delete & Restore Endpoints
# ---------------------------
@app.route('/tasks/batch_delete', methods=['DELETE'])
def batch_delete_tasks():
    auth_user_id = request.headers.get('X-User-Id')
    if not auth_user_id:
        return jsonify({'error': 'Authentication required via X-User-Id header'}), 401
    try:
        auth_user_id = int(auth_user_id)
    except ValueError:
        return jsonify({'error': 'Invalid X-User-Id header'}), 400
    if not user_exists(auth_user_id):
        return jsonify({'error': 'User does not exist'}), 401

    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not start_date or not end_date:
        return jsonify({'error': 'Both start_date and end_date are required'}), 400

    try:
        start_date_obj = datetime.fromisoformat(start_date)
        end_date_obj = datetime.fromisoformat(end_date)
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use ISO 8601 format: YYYY-MM-DDTHH:MM:SS'}), 400

    if start_date_obj > end_date_obj:
        return jsonify({'error': 'start_date must be before end_date'}), 400

    deletion_time = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Copy tasks to deleted_tasks table.
        cursor.execute('''
            INSERT INTO deleted_tasks (user_id, title, description, start_date, due_date, completion_date, status, deletion_time)
            SELECT user_id, title, description, start_date, due_date, completion_date, status, ?
            FROM tasks
            WHERE user_id = ? AND due_date BETWEEN ? AND ?
        ''', (deletion_time, auth_user_id, start_date, end_date))
        # Delete the tasks.
        cursor.execute('''
            DELETE FROM tasks
            WHERE user_id = ? AND due_date BETWEEN ? AND ?
        ''', (auth_user_id, start_date, end_date))
        conn.commit()
        deleted_count = cursor.rowcount

    return jsonify({'message': f'{deleted_count} tasks deleted successfully'}), 200

@app.route('/tasks/restore_last', methods=['POST'])
def restore_last_deleted_task():
    auth_user_id = request.headers.get('X-User-Id')
    if not auth_user_id:
        return jsonify({'error': 'Authentication required via X-User-Id header'}), 401
    try:
        auth_user_id = int(auth_user_id)
    except ValueError:
        return jsonify({'error': 'Invalid X-User-Id header'}), 400

    with get_db_connection() as conn:
        # Get the last deleted task for the authenticated user, based on deletion_time.
        deleted_task = conn.execute('''
            SELECT * FROM deleted_tasks 
            WHERE user_id = ? 
            ORDER BY datetime(deletion_time) DESC
            LIMIT 1
        ''', (auth_user_id,)).fetchone()

        if not deleted_task:
            return jsonify({'error': 'No deleted tasks found to restore'}), 404

        # Reinsert the task into the tasks table.
        cur = conn.execute('''
            INSERT INTO tasks (user_id, title, description, start_date, due_date, completion_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            deleted_task['user_id'],
            deleted_task['title'],
            deleted_task['description'],
            deleted_task['start_date'],
            deleted_task['due_date'],
            deleted_task['completion_date'],
            deleted_task['status']
        ))
        conn.commit()
        new_task_id = cur.lastrowid
        # Remove the restored task from deleted_tasks.
        conn.execute("DELETE FROM deleted_tasks WHERE id = ?", (deleted_task['id'],))
        conn.commit()

    return jsonify({'message': 'Task restored', 'new_task_id': new_task_id}), 200

# ---------------------------
# Subscription API Routes
# ---------------------------
@app.route('/subscribe', methods=['POST'])
def subscribe():
    data = request.get_json()
    user_id = data.get('user_id')
    frequency = data.get('frequency')
    if not user_id or frequency not in ['daily', 'weekly', 'monthly']:
        return jsonify({'error': 'Invalid subscription data; user_id and frequency (daily, weekly, monthly) required'}), 400

    with get_db_connection() as conn:
        conn.execute("INSERT INTO subscriptions (user_id, frequency) VALUES (?, ?)", (user_id, frequency))
        conn.commit()
    return jsonify({'message': 'Subscribed successfully'}), 201

@app.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    data = request.get_json()
    user_id = data.get('user_id')
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    with get_db_connection() as conn:
        conn.execute("DELETE FROM subscriptions WHERE user_id = ?", (user_id,))
        conn.commit()
    return jsonify({'message': 'Unsubscribed successfully'}), 200

if __name__ == '__main__':
    app.run(debug=True)

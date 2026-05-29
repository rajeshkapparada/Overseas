from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import db

app = Flask(__name__)
app.secret_key = 'overseas_portal_2024'

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name        = request.form['name']
        email       = request.form['email']
        password    = generate_password_hash(request.form['password'])
        student_id  = request.form['student_id']
        study_level = request.form['study_level']
        country     = request.form['country']
        course      = request.form['course']

        image_path = None
        file = request.files.get('image')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = filename

        conn = db.get_connection()
        cur = conn.cursor()
        try:
            cur.execute('''
                INSERT INTO students (name, email, password, student_id, study_level, country, course, image_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (name, email, password, student_id, study_level, country, course, image_path))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception:
            conn.rollback()
            flash('Email already exists or an error occurred.', 'error')
        finally:
            cur.close()
            conn.close()

    return render_template('register.html')


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']

        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM students WHERE email = %s', (email,))
        student = cur.fetchone()
        cur.close()
        conn.close()

        if student and check_password_hash(student[3], password):
            session['student_id']   = student[0]
            session['student_name'] = student[1]
            flash(f'Welcome, {student[1]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('login.html')


@app.route('/dashboard')
def dashboard():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    query = request.args.get('q', '').strip()
    field = request.args.get('field', 'name')
    students = []
    searched = False

    allowed_fields = {
        'name':        ('name ILIKE %s',                  f'%{query}%'),
        'email':       ('email ILIKE %s',                 f'%{query}%'),
        'student_id':  ('CAST(student_id AS TEXT) = %s',  query),
        'course':      ('course ILIKE %s',                f'%{query}%'),
        'study_level': ('study_level ILIKE %s',           f'%{query}%'),
        'country':     ('country ILIKE %s',               f'%{query}%'),
    }

    if query and field in allowed_fields:
        searched = True
        condition, value = allowed_fields[field]
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute(f'''
            SELECT id, name, email, student_id, study_level, country, course, image_path, created_at
            FROM students
            WHERE {condition}
            ORDER BY created_at DESC
        ''', (value,))
        students = cur.fetchall()
        cur.close()
        conn.close()

    return render_template('dashboard.html', students=students, query=query, field=field, searched=searched)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


def api_login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'student_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


# ── Auth APIs ──────────────────────────────────────────────────────────────────

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    required = ['name', 'email', 'password', 'student_id', 'study_level', 'country', 'course']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing fields: {", ".join(missing)}'}), 400

    password = generate_password_hash(data['password'])
    conn = db.get_connection()
    cur = conn.cursor()
    try:
        cur.execute('''
            INSERT INTO students (name, email, password, student_id, study_level, country, course)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
        ''', (data['name'], data['email'], password, data['student_id'],
              data['study_level'], data['country'], data['course']))
        new_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({'message': 'Registration successful', 'id': new_id}), 201
    except Exception:
        conn.rollback()
        return jsonify({'error': 'Email already exists or a database error occurred'}), 409
    finally:
        cur.close()
        conn.close()


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'email and password required'}), 400

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM students WHERE email = %s', (data['email'],))
    student = cur.fetchone()
    cur.close()
    conn.close()

    if student and check_password_hash(student[3], data['password']):
        session['student_id']   = student[0]
        session['student_name'] = student[1]
        return jsonify({
            'message': f'Welcome, {student[1]}!',
            'student': {
                'id': student[0], 'name': student[1], 'email': student[2],
                'student_id': student[4], 'study_level': student[5],
                'country': student[6], 'course': student[7],
                'image_path': student[8]
            }
        }), 200

    return jsonify({'error': 'Invalid email or password'}), 401


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200


# ── Student APIs ───────────────────────────────────────────────────────────────

@app.route('/api/profile', methods=['GET'])
@api_login_required
def api_profile():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, name, email, student_id, study_level, country, course, image_path, created_at
        FROM students WHERE id = %s
    ''', (session['student_id'],))
    s = cur.fetchone()
    cur.close()
    conn.close()

    if not s:
        return jsonify({'error': 'Student not found'}), 404

    return jsonify({
        'id': s[0], 'name': s[1], 'email': s[2], 'student_id': s[3],
        'study_level': s[4], 'country': s[5], 'course': s[6],
        'image_path': s[7], 'created_at': str(s[8])
    }), 200


@app.route('/api/students', methods=['GET'])
@api_login_required
def api_get_students():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, name, email, student_id, study_level, country, course, image_path, created_at
        FROM students ORDER BY created_at DESC
    ''')
    rows = cur.fetchall()
    cur.close()
    conn.close()

    students = [
        {'id': r[0], 'name': r[1], 'email': r[2], 'student_id': r[3],
         'study_level': r[4], 'country': r[5], 'course': r[6],
         'image_path': r[7], 'created_at': str(r[8])}
        for r in rows
    ]
    return jsonify(students), 200


@app.route('/api/students/<int:student_id>', methods=['GET'])
@api_login_required
def api_get_student(student_id):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, name, email, student_id, study_level, country, course, image_path, created_at
        FROM students WHERE id = %s
    ''', (student_id,))
    s = cur.fetchone()
    cur.close()
    conn.close()

    if not s:
        return jsonify({'error': 'Student not found'}), 404

    return jsonify({
        'id': s[0], 'name': s[1], 'email': s[2], 'student_id': s[3],
        'study_level': s[4], 'country': s[5], 'course': s[6],
        'image_path': s[7], 'created_at': str(s[8])
    }), 200


@app.route('/api/students/<int:student_id>', methods=['PUT'])
@api_login_required
def api_update_student(student_id):
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    fields = ['name', 'study_level', 'country', 'course']
    updates = {f: data[f] for f in fields if f in data}
    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    set_clause = ', '.join(f'{k} = %s' for k in updates)
    values = list(updates.values()) + [student_id]

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(f'UPDATE students SET {set_clause} WHERE id = %s', values)
    conn.commit()
    updated = cur.rowcount
    cur.close()
    conn.close()

    if updated == 0:
        return jsonify({'error': 'Student not found'}), 404
    return jsonify({'message': 'Student updated successfully'}), 200


@app.route('/api/students/<int:student_id>', methods=['DELETE'])
@api_login_required
def api_delete_student(student_id):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM students WHERE id = %s', (student_id,))
    conn.commit()
    deleted = cur.rowcount
    cur.close()
    conn.close()

    if deleted == 0:
        return jsonify({'error': 'Student not found'}), 404
    return jsonify({'message': 'Student deleted successfully'}), 200


if __name__ == '__main__':
    db.create_table()
    app.run(debug=True)
import psycopg2

DB_CONFIG = {
    'host': 'localhost',
    'database': 'student_portal',
    'user': 'postgres',
    'password': 'Rajesh@7778',
    'port': '5432'
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)

def create_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            student_id INT,
            study_level VARCHAR(50),
            country VARCHAR(100),
            course VARCHAR(100),
            image_path VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

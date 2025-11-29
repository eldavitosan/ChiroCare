from mysql.connector import Error
from datetime import date
from utils.date_manager import to_frontend_str

def add_patient(connection, id_dr, fecha, comoentero, nombre, apellidop, apellidom,
                nacimiento, direccion, estadocivil, hijos, ocupacion,
                telcasa, cel, correo, emergencia, contacto, parentesco):
    cursor = None
    try:
        cursor = connection.cursor()
        query = """
            INSERT INTO datos_personales
            (id_dr, fecha, comoentero, nombre, apellidop, apellidom, nacimiento,
             direccion, estadocivil, hijos, ocupacion, telcasa, cel, correo,
             emergencia, contacto, parentesco)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (id_dr, fecha, comoentero, nombre, apellidop, apellidom, nacimiento,
                  direccion, estadocivil, hijos, ocupacion, telcasa, cel, correo,
                  emergencia, contacto, parentesco)
        cursor.execute(query, values)
        connection.commit()
        return cursor.lastrowid
    except Error as e:
        print(f"Error añadiendo paciente: {e}")
        return None
    finally:
        if cursor: cursor.close()

def get_patient_by_id(connection, patient_id):
    cursor = None
    try:
        query = "SELECT * FROM datos_personales WHERE id_px = %s"
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        data = cursor.fetchone()
        if data and data.get('nacimiento'):
            data['nacimiento'] = to_frontend_str(data['nacimiento'])
        return data
    except Error: return None
    finally: 
        if cursor: cursor.close()

def search_patients_by_name(connection, search_term):
    cursor = None
    try:
        pattern = f"%{search_term}%"
        query = """
            SELECT id_px, nombre, apellidop, apellidom
            FROM datos_personales
            WHERE nombre LIKE %s OR apellidop LIKE %s OR apellidom LIKE %s
            ORDER BY apellidop, apellidom, nombre LIMIT 50
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (pattern, pattern, pattern))
        return cursor.fetchall()
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_recent_patients(connection, limit=5):
    cursor = None
    try:
        query = "SELECT id_px, nombre, apellidop, apellidom FROM datos_personales ORDER BY id_px DESC LIMIT %s"
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (limit,))
        return cursor.fetchall()
    except Error: return []
    finally: 
        if cursor: cursor.close()

def update_patient_details(connection, patient_data):
    cursor = None
    if 'id_px' not in patient_data: return False
    updatable = ['comoentero', 'nombre', 'apellidop', 'apellidom', 'nacimiento',
                 'direccion', 'estadocivil', 'hijos', 'ocupacion', 'telcasa', 'cel',
                 'correo', 'emergencia', 'contacto', 'parentesco']
    set_parts, values = [], []
    for col in updatable:
        if col in patient_data:
            set_parts.append(f"`{col}`=%s")
            values.append(patient_data[col])
    
    if not set_parts: return True
    try:
        cursor = connection.cursor()
        query = f"UPDATE datos_personales SET {', '.join(set_parts)} WHERE id_px=%s"
        values.append(patient_data['id_px'])
        cursor.execute(query, tuple(values))
        return True
    except Error as e:
        print(f"Error update patient: {e}")
        return False
    finally: 
        if cursor: cursor.close()

def count_total_pacientes(connection):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) as total FROM datos_personales")
        return cursor.fetchone()['total']
    except Error: return 0
    finally: 
        if cursor: cursor.close()

def get_patients_by_recent_followup(connection, limit=10):
    cursor = None
    try:
        query = """
            SELECT dp.id_px, dp.nombre, dp.apellidop, dp.apellidom, MAX(q.fecha) AS fecha_ultimo_seguimiento
            FROM datos_personales dp
            JOIN quiropractico q ON dp.id_px = q.id_px
            GROUP BY dp.id_px, dp.nombre, dp.apellidop, dp.apellidom
            ORDER BY fecha_ultimo_seguimiento DESC, dp.id_px DESC LIMIT %s;
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (limit,))
        patients = cursor.fetchall()
        if patients:
            for p in patients:
                p['fecha_ultimo_seguimiento'] = to_frontend_str(p.get('fecha_ultimo_seguimiento'))
        return patients or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

# Notas Generales
def get_unseen_notes_for_patient(connection, patient_id):
    cursor = None
    try:
        query = "SELECT id_nota, fecha, notas FROM notas_generales WHERE id_px = %s AND (visto = 0 OR visto IS NULL) ORDER BY fecha ASC"
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        notes = cursor.fetchall()
        if notes:
            for note in notes:
                if isinstance(note['fecha'], date):
                    note['fecha'] = note['fecha'].strftime('%d/%m/%Y')
        return notes or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def mark_notes_as_seen(connection, note_ids_list):
    if not note_ids_list: return 0
    cursor = None
    try:
        safe_ids = [int(i) for i in note_ids_list if str(i).isdigit()]
        if not safe_ids: return 0
        placeholders = ', '.join(['%s'] * len(safe_ids))
        query = f"UPDATE notas_generales SET visto = 1 WHERE id_nota IN ({placeholders})"
        cursor = connection.cursor()
        cursor.execute(query, tuple(safe_ids))
        return cursor.rowcount
    except Error: raise
    finally: 
        if cursor: cursor.close()

def add_general_note(connection, id_px, notas_text):
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO notas_generales (id_px, fecha, notas, visto) VALUES (%s, CURDATE(), %s, 0)", (id_px, notas_text))
        return cursor.lastrowid
    except Error: raise
    finally: 
        if cursor: cursor.close()

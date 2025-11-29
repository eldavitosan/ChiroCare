from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash

def add_user(connection, nombre, usuario, password_plain, centro):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        query_check = "SELECT id_dr FROM dr WHERE usuario = %s"
        cursor.execute(query_check, (usuario,))
        if cursor.fetchone():
            return "exists"

        hashed_password = generate_password_hash(password_plain, method='pbkdf2:sha256')
        query_insert = """
            INSERT INTO dr (nombre, usuario, contraseña, centro, esta_activo)
            VALUES (%s, %s, %s, %s, 1) 
        """
        cursor.execute(query_insert, (nombre, usuario, hashed_password, centro))
        return cursor.lastrowid or True
    except Error as e:
        print(f"Error en add_user: {e}")
        return False
    finally:
        if cursor: cursor.close()

def verify_login(connection, usuario, contraseña):
    cursor = None
    try:
        query = "SELECT id_dr, nombre, contraseña, centro, usuario, esta_activo FROM dr WHERE usuario = %s"
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (usuario,))
        doctor_data = cursor.fetchone()

        if doctor_data and check_password_hash(doctor_data.get('contraseña', ''), contraseña):
            del doctor_data['contraseña']
            return doctor_data
        return None
    except Exception:
        return None
    finally:
        if cursor: cursor.close()

def get_all_doctors(connection, include_inactive=True, filter_by_centro_id=None):
    cursor = None
    try:
        query_base = "SELECT id_dr, nombre, usuario, centro, esta_activo FROM dr"
        conditions, params = [], []

        if not include_inactive:
            conditions.append("esta_activo = 1")
        if filter_by_centro_id is not None:
            conditions.append("centro = %s")
            params.append(filter_by_centro_id)

        if conditions:
            query_base += " WHERE " + " AND ".join(conditions)
        
        query_base += " ORDER BY nombre ASC"
        
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query_base, tuple(params))
        doctores = cursor.fetchall()
        if doctores:
            for dr in doctores:
                dr['esta_activo'] = bool(dr.get('esta_activo', 0))
                dr['is_admin_role'] = (dr.get('centro') == 0) 
        return doctores or []
    except Error as e:
        print(f"Error obteniendo doctores: {e}")
        return []
    finally:
        if cursor: cursor.close()

def get_doctor_by_id(connection, id_dr):
    cursor = None
    try:
        query = "SELECT id_dr, nombre, usuario, contraseña, centro, esta_activo FROM dr WHERE id_dr = %s"
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_dr,))
        doctor = cursor.fetchone()
        if doctor:
            doctor['esta_activo'] = bool(doctor.get('esta_activo', 0))
            doctor['is_admin_role'] = (doctor.get('centro') == 0)
        return doctor
    except Error as e:
        print(f"Error obteniendo doctor {id_dr}: {e}")
        return None
    finally:
        if cursor: cursor.close()

def update_doctor_details(connection, data):
    cursor = None
    if 'id_dr' not in data: return False
    updatable = ['nombre', 'usuario', 'centro', 'esta_activo']
    set_parts, values = [], []

    for col in updatable:
        if col in data:
            set_parts.append(f"`{col}`=%s")
            val = int(data[col]) if isinstance(data[col], bool) and col == 'esta_activo' else data[col]
            values.append(val)

    if not set_parts: return True

    try:
        cursor = connection.cursor()
        query = f"UPDATE dr SET {', '.join(set_parts)} WHERE id_dr=%s"
        values.append(data['id_dr'])
        cursor.execute(query, tuple(values))
        return True
    except Error as e:
        if e.errno == 1062: raise ValueError(f"El usuario '{data.get('usuario')}' ya existe.")
        return False
    finally:
        if cursor: cursor.close()

def update_doctor_password(connection, id_dr, new_password_plain):
    cursor = None
    try:
        cursor = connection.cursor()
        hashed = generate_password_hash(new_password_plain, method='pbkdf2:sha256')
        cursor.execute("UPDATE dr SET contraseña = %s WHERE id_dr = %s", (hashed, id_dr))
        return cursor.rowcount > 0
    except Error as e:
        print(f"Error password update: {e}")
        return False
    finally:
        if cursor: cursor.close()

def set_doctor_active_status(connection, id_dr, status):
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE dr SET esta_activo = %s WHERE id_dr = %s", (1 if status else 0, id_dr))
        return cursor.rowcount > 0
    except Error:
        return False
    finally:
        if cursor: cursor.close()

def count_total_doctores(connection):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) as total FROM dr")
        return cursor.fetchone()['total']
    except Error:
        return 0
    finally:
        if cursor: cursor.close()

# Funciones de Centro (Clinicas)
def get_all_centros(connection):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id_centro, nombre, direccion, cel, tel FROM centro ORDER BY nombre ASC")
        return cursor.fetchall() or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_centro_by_id(connection, id_centro):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id_centro, nombre, direccion, cel, tel FROM centro WHERE id_centro = %s", (id_centro,))
        return cursor.fetchone()
    except Error: return None
    finally: 
        if cursor: cursor.close()

def add_centro(connection, data):
    cursor = None
    try:
        cursor = connection.cursor()
        query = "INSERT INTO centro (nombre, direccion, cel, tel) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (data['nombre'], data.get('direccion'), data.get('cel'), data.get('tel')))
        return cursor.lastrowid
    except Error: return None
    finally:
        if cursor: cursor.close()

def update_centro(connection, data):
    cursor = None
    try:
        cursor = connection.cursor()
        query = "UPDATE centro SET nombre=%s, direccion=%s, cel=%s, tel=%s WHERE id_centro=%s"
        cursor.execute(query, (data['nombre'], data.get('direccion'), data.get('cel'), data.get('tel'), data['id_centro']))
        return cursor.rowcount > 0
    except Error: return False
    finally: 
        if cursor: cursor.close()

def get_doctor_profile(connection, id_dr):
    """Obtiene los datos del perfil del doctor, incluyendo configuraciones."""
    try:
        cursor = connection.cursor(dictionary=True)
        # Ajusta 'doctores' y 'id_doctor' según tu tabla real
        query = "SELECT id_dr, nombre, usuario, config_redireccion_seguimiento FROM dr WHERE id_dr = %s"
        cursor.execute(query, (id_dr,))
        return cursor.fetchone()
    except Exception as e:
        print(f"Error obteniendo perfil doctor: {e}")
        return None

def update_doctor_preferences(connection, id_dr, config_valor):
    """Actualiza la preferencia de redirección."""
    try:
        cursor = connection.cursor()
        query = "UPDATE dr SET config_redireccion_seguimiento = %s WHERE id_dr = %s"
        cursor.execute(query, (config_valor, id_dr))
        connection.commit()
        return True
    except Exception as e:
        print(f"Error actualizando preferencias: {e}")
        return False
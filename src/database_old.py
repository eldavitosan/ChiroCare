# src/database.py
import mysql.connector
from mysql.connector import Error, IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
from utils.date_manager import to_db_str, to_frontend_str, calculate_age, parse_date
import os
from dotenv import load_dotenv
from datetime import timedelta
from dateutil.relativedelta import relativedelta

load_dotenv() # Carga variables del archivo .env en el entorno
# Configuración de la base de datos leída desde variables de entorno
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME'),
    'port': int(os.environ.get('DB_PORT', 3306)) # Convertir a int, default 3306
}
if not DB_CONFIG['user'] or not DB_CONFIG['database']: # Ya no verificamos DB_PASSWORD aquí
    raise ValueError("Faltan variables de configuración de la base de datos (DB_USER, DB_NAME) en el archivo .env. DB_PASSWORD puede estar vacía si así está configurado.")


def connect_to_db():
    try:
        connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            port=DB_CONFIG['port'], # Añadir puerto
            autocommit=True # Mantener autocommit si así lo tenías
        )
        if connection.is_connected():
            print("Connected to MySQL database successfully!")
            return connection
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None
    return None # Asegurar que siempre devuelva algo
def add_user(connection, nombre, usuario, password_plain, centro):
    """
    Añade un nuevo doctor/usuario a la tabla 'dr'.
    Hashea la contraseña antes de guardarla.
    Verifica si el usuario ya existe.
    Devuelve el ID del nuevo usuario si es exitoso, "exists" si ya existe, o False si hay error.
    NO HACE COMMIT.
    """
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True) # Usar dictionary=True puede ser útil

        # 1. Verificar si el nombre de usuario ya existe
        query_check = "SELECT id_dr FROM dr WHERE usuario = %s"
        cursor.execute(query_check, (usuario,))
        existing_user = cursor.fetchone()
        if existing_user:
            print(f"Intento de registrar usuario '{usuario}' que ya existe.")
            return "exists" # Devolver string específico para este caso

        # 2. Hashear la contraseña
        # Asegúrate de que generate_password_hash esté importado de werkzeug.security
        hashed_password = generate_password_hash(password_plain, method='pbkdf2:sha256')

        # 3. Insertar el nuevo usuario
        # Asumimos que la columna 'esta_activo' existe y por defecto queremos que sea 1 (activo)
        query_insert = """
            INSERT INTO dr (nombre, usuario, contraseña, centro, esta_activo)
            VALUES (%s, %s, %s, %s, 1) 
        """
        values_insert = (nombre, usuario, hashed_password, centro)
        
        cursor.execute(query_insert, values_insert)
        new_user_id = cursor.lastrowid # Obtener el ID del registro insertado

        if new_user_id:
            print(f"Usuario '{usuario}' añadido con ID: {new_user_id}")
            return new_user_id # Éxito, devuelve el ID del nuevo usuario (valor "Truthy")
        else:
            # Esto podría pasar si el INSERT fue exitoso pero lastrowid no se obtuvo (raro con autocommit)
            # o si la tabla 'dr' no tiene un PK auto-incrementable llamado 'id_dr'
            # O si el commit no se hizo (con autocommit=True no debería ser problema inmediato para lastrowid)
            print(f"Usuario '{usuario}' podría haber sido añadido, pero lastrowid es {new_user_id}. Asumiendo éxito si no hubo excepción.")
            # Para estar seguros y evitar el 'else' en main.py, si no hay error, devolvemos True
            # si no tenemos un ID (aunque tener el ID es mejor).
            # Si la tabla tiene un PK auto_increment, lastrowid debería funcionar.
            # Si no, esta función necesitaría una lógica diferente para confirmar la inserción.
            # Por ahora, si llega aquí sin error, asumimos que el INSERT funcionó.
            return True # Indica éxito general si no se obtuvo lastrowid pero no hubo error SQL

    except Error as e:
        print(f"Error en add_user: {e}")
        # El rollback se maneja en la ruta Flask si no hay autocommit
        return False # Devolver False en caso de error de BD
    finally:
        if cursor:
            cursor.close()

def verify_login(connection, usuario, contraseña):
    """Verifica credenciales y devuelve datos del usuario."""
    cursor = None
    try:
        query = "SELECT id_dr, nombre, contraseña, centro, usuario, esta_activo FROM dr WHERE usuario = %s"
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (usuario,))
        doctor_data = cursor.fetchone()

        if doctor_data:
            stored_hash = doctor_data.get('contraseña', '')
            password_match = check_password_hash(stored_hash, contraseña)

            if password_match:
                # Eliminar la contraseña del diccionario antes de devolverlo
                del doctor_data['contraseña']
                return doctor_data # Devuelve el diccionario con los datos del usuario
            else:
                return None # Contraseña incorrecta
        else:
            return None # Usuario no encontrado
    except Error as e:
        return None
    except Exception as ex:
        return None
    finally:
        if cursor:
            cursor.close()

def add_patient(connection, id_dr, fecha, comoentero, nombre, apellidop, apellidom,
                nacimiento, direccion, estadocivil, hijos, ocupacion,
                telcasa, cel, correo, emergencia, contacto, parentesco):
    """Añade un nuevo paciente a la tabla datos_personales."""
    cursor = None
    try:
        cursor = connection.cursor()
        # Asumiendo que municipio, estado, cp no se están usando en el form actual
        query = """
            INSERT INTO datos_personales
            (id_dr, fecha, comoentero, nombre, apellidop, apellidom, nacimiento,
             direccion, estadocivil, hijos, ocupacion, telcasa, cel, correo,
             emergencia, contacto, parentesco)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        values = (
            id_dr, fecha, comoentero, nombre, apellidop, apellidom, nacimiento,
            direccion, estadocivil, hijos, ocupacion, telcasa, cel, correo,
            emergencia, contacto, parentesco
        )
        cursor.execute(query, values)
        connection.commit()
        new_patient_id = cursor.lastrowid
        print(f"Paciente '{nombre} {apellidop}' añadido exitosamente (ID_PX: {new_patient_id}).")
        return new_patient_id
    except Error as e:
        print(f"Error añadiendo paciente: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_patient_by_id(connection, patient_id):
    """Obtiene los datos personales de un paciente por su ID."""
    cursor = None
    try:
        query = """
            SELECT id_px, id_dr, fecha, comoentero, nombre, apellidop, apellidom, nacimiento,
                   direccion, estadocivil, hijos, ocupacion, telcasa, cel, correo,
                   emergencia, contacto, parentesco
            FROM datos_personales
            WHERE id_px = %s
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        patient_data = cursor.fetchone()
        
        # Convertir fechas para el frontend
        if patient_data and patient_data.get('nacimiento'):
            patient_data['nacimiento'] = to_frontend_str(patient_data['nacimiento'])
            
        return patient_data
    except Error as e:
        print(f"Error buscando paciente por ID: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def search_patients_by_name(connection, search_term):
    """Busca pacientes por nombre o apellido."""
    cursor = None
    try:
        search_pattern = f"%{search_term}%"
        query = """
            SELECT id_px, nombre, apellidop, apellidom
            FROM datos_personales
            WHERE nombre LIKE %s OR apellidop LIKE %s OR apellidom LIKE %s
            ORDER BY apellidop, apellidom, nombre
            LIMIT 50
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (search_pattern, search_pattern, search_pattern))
        results = cursor.fetchall()
        return results
    except Error as e:
        print(f"Error buscando pacientes: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_recent_patients(connection, limit=5):
    """Obtiene los 'limit' pacientes más recientes."""
    cursor = None
    try:
        query = """
            SELECT id_px, nombre, apellidop, apellidom
            FROM datos_personales
            ORDER BY id_px DESC
            LIMIT %s
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (limit,))
        recent_patients = cursor.fetchall()
        return recent_patients
    except Error as e:
        print(f"Error obteniendo pacientes recientes: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

# --- Funciones para Antecedentes ---

def get_antecedentes_summary(connection, patient_id):
    """Obtiene lista de diccionarios [{'fecha': F, 'id_antecedente': ID}]
       para un paciente, ordenado por fecha descendente."""
    cursor = None
    summary_list = []
    try:
        query = """
            SELECT id_antecedente, fecha
            FROM antecedentes
            WHERE id_px = %s
            ORDER BY fecha DESC, id_antecedente DESC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        summary_list = cursor.fetchall()
        return summary_list
    except Error as e:
        print(f"Error obteniendo resumen de antecedentes: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_specific_antecedente(connection, id_antecedente):
    """Obtiene los datos de un registro de antecedentes específico por su ID único."""
    cursor = None
    try:
        query = """
            SELECT id_antecedente, id_px, fecha, peso, altura, calzado, condiciones_generales,
                   condicion_diagnosticada, presion_alta, trigliceridos, diabetes, agua, notas
            FROM antecedentes
            WHERE id_antecedente = %s
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_antecedente,))
        antecedente_data = cursor.fetchone()
        if antecedente_data and antecedente_data.get('calzado'):
             try: antecedente_data['calzado'] = float(antecedente_data['calzado'])
             except (TypeError, ValueError): antecedente_data['calzado'] = 0.0
        return antecedente_data
    except Error as e:
        print(f"Error obteniendo antecedente específico por ID {id_antecedente}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_specific_antecedente_by_date(connection, patient_id, fecha_str):
    """Obtiene los datos y el ID del antecedente para un paciente en una fecha específica."""
    cursor = None
    try:
        fecha_sql = parse_date(fecha_str)
        query = """
            SELECT id_antecedente, id_px, fecha, peso, altura, calzado, condiciones_generales,
                   condicion_diagnosticada, presion_alta, trigliceridos, diabetes, agua, notas
            FROM antecedentes
            WHERE id_px = %s AND fecha = %s
            ORDER BY id_antecedente DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id, fecha_sql))
        antecedente_data = cursor.fetchone()
        if antecedente_data and antecedente_data.get('calzado'):
             try: antecedente_data['calzado'] = float(antecedente_data['calzado'])
             except (TypeError, ValueError): antecedente_data['calzado'] = 0.0
        return antecedente_data
    except ValueError as ve:
        print(f"Error de fecha en get_specific_antecedente_by_date: {ve}")
        return None
    except Error as e:
        print(f"Error obteniendo antecedente específico (px:{patient_id}, fecha:{fecha_str}): {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def save_antecedentes(connection, data):
    """Guarda (INSERT o UPDATE) los antecedentes.
       Determina acción basado en si 'id_antecedente' está en 'data'.
       'data' DEBE contener 'id_px' y 'fecha'.
       *** CORREGIDO: Ya no intenta insertar id_dr/id_anamnesis_inicial ***
    """
    cursor = None
    required_keys = ['id_px', 'fecha']
    if not all(key in data and data[key] is not None for key in required_keys):
         print("Error: Faltan id_px o fecha en los datos a guardar.")
         return False

    # Columnas REALES de la tabla 'antecedentes' (excluyendo PK)
    data_columns = [
        'peso', 'altura', 'calzado', 'condiciones_generales',
        'condicion_diagnosticada', 'presion_alta', 'trigliceridos',
        'diabetes', 'agua', 'notas'
    ]

    try:
        cursor = connection.cursor()
        id_to_update = data.get('id_antecedente')
        saved_id = None # Para devolver el ID afectado

        # Asegurar que todas las claves esperadas existan en 'data'
        for col in data_columns:
            if col not in data:
                # Usar .get con un valor default apropiado si la columna lo permite
                # Si la columna es NOT NULL, deberías asegurar que el valor exista antes
                data[col] = data.get(col) # O data.get(col, '') si son strings, data.get(col, 0) si son números, etc.

        # Parsear fecha
        try:
            fecha_sql = parse_date(data.get('fecha'))
        except ValueError as ve:
            print(f"Error fatal (save_antecedentes): {ve}")
            return False

        if id_to_update:
            # --- UPDATE ---
            set_parts = [
                "`fecha`=%s" 
            ]
            values_list = [fecha_sql] # Empezamos la lista de valores con la fecha

            for col in data_columns:
                set_parts.append(f"`{col}`=%s")
                values_list.append(data.get(col))
            
            set_clause = ", ".join(set_parts)
            query = f"UPDATE antecedentes SET {set_clause} WHERE id_antecedente=%s"
            
            values_list.append(id_to_update) # Añadimos el ID al final para el WHERE
            values = tuple(values_list)
            
            print(f"Actualizando antecedentes para ID_ANTECEDENTE: {id_to_update}")
            cursor.execute(query, values)
            saved_id = id_to_update
        else:
            # --- INSERT ---
            # Columnas para INSERT (id_px + las data_columns + fecha)
            insert_columns = ['id_px', 'fecha'] + data_columns
            column_names = ", ".join([f"`{col}`" for col in insert_columns])
            placeholders = "%s, %s, " + ", ".join(['%s'] * len(data_columns))
            
            query = f"INSERT INTO antecedentes ({column_names}) VALUES ({placeholders})"
            
            values_list = [data['id_px'], fecha_sql] # id_px y fecha primero
            for col in data_columns:
                values_list.append(data.get(col))
            
            values = tuple(values_list)

            print(f"Insertando nuevos antecedentes para ID_PX: {data.get('id_px')} en Fecha: {fecha_sql}")
            cursor.execute(query, values)
            saved_id = cursor.lastrowid

        # connection.commit() # Mantenemos autocommit=True por ahora
        print("Antecedentes guardados/actualizados exitosamente.")
        return True # Devolver True en éxito como antes (aunque devolver saved_id podría ser útil)

    except Error as e:
        print(f"Error guardando/actualizando antecedentes: {e}")
        # connection.rollback() # No necesario con autocommit
        return False
    finally:
        if cursor:
            cursor.close()

# --- Funciones para Anamnesis ---

def get_anamnesis_summary(connection, patient_id):
    """Obtiene lista de diccionarios [{'fecha': F, 'id_anamnesis': ID}]
       para un paciente, ordenado por fecha/ID descendente."""
    cursor = None
    summary_list = []
    try:
        query = """
            SELECT id_anamnesis, 
                   DATE_FORMAT(fecha, '%d/%m/%Y') as fecha, 
                   condicion1, condicion2, condicion3
            FROM anamnesis
            WHERE id_px = %s
            ORDER BY fecha DESC, id_anamnesis DESC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        summary_list = cursor.fetchall()
        # print(f"Resumen de Anamnesis encontrado para paciente {patient_id}: {summary_list}") # Debug opcional
        return summary_list
    except Error as e:
        print(f"Error obteniendo resumen de anamnesis: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_specific_anamnesis(connection, id_anamnesis):
    """Obtiene los datos de un registro de anamnesis específico por su ID único."""
    cursor = None
    try:
        # Selecciona todas las columnas EXCEPTO diagrama, lesión, historia
        query = """
            SELECT id_anamnesis, id_px, fecha, condicion1, calif1, condicion2, calif2,
                   condicion3, calif3, como_comenzo, primera_vez, alivia, empeora,
                   como_ocurrio, actividades_afectadas, dolor_intenso, tipo_dolor, diagrama, historia 
            FROM anamnesis
            WHERE id_anamnesis = %s
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_anamnesis,))
        anamnesis_data = cursor.fetchone()
        return anamnesis_data # Devuelve diccionario o None
    except Error as e:
        print(f"Error obteniendo anamnesis específica por ID {id_anamnesis}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_specific_anamnesis_by_date(connection, patient_id, fecha_str):
    """Obtiene los datos y el ID del registro de anamnesis para un paciente en una fecha específica."""
    cursor = None
    try:
        fecha_sql = parse_date(fecha_str)
        # Selecciona todas las columnas EXCEPTO diagrama, lesión, historia
        query = """
            SELECT id_anamnesis, id_px, fecha, condicion1, calif1, condicion2, calif2,
                   condicion3, calif3, como_comenzo, primera_vez, alivia, empeora,
                   como_ocurrio, actividades_afectadas, dolor_intenso, tipo_dolor, diagrama, historia 
            FROM anamnesis
            WHERE id_px = %s AND fecha = %s
            ORDER BY id_anamnesis DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id, fecha_sql))
        anamnesis_data = cursor.fetchone()
        return anamnesis_data # Devuelve diccionario con id_anamnesis o None
    except ValueError as ve:
        print(f"Error de fecha en get_specific_anamnesis_by_date: {ve}")
        return None
    except Error as e:
        print(f"Error obteniendo anamnesis específica por fecha (px:{patient_id}, fecha:{fecha_str}): {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def save_anamnesis(connection, data):
    """Guarda (INSERT o UPDATE) los datos de anamnesis.
       Determina acción basado en si 'id_anamnesis' está en 'data'.
       'data' DEBE contener 'id_px' y 'fecha'. Omite 'diagrama', 'lesion', 'historia'.
    """
    cursor = None
    required_keys = ['id_px', 'fecha']
    if not all(key in data and data[key] is not None for key in required_keys):
         print("Error: Faltan id_px o fecha en los datos de anamnesis a guardar.")
         return False

    # Columnas de datos a insertar/actualizar (quitando lesión e historia)
    data_columns = [
        'condicion1', 'calif1', 'condicion2', 'calif2', 'condicion3', 'calif3',
        'como_comenzo', 'primera_vez', 'alivia', 'empeora', 'como_ocurrio',
        'actividades_afectadas', 'dolor_intenso', 'tipo_dolor', 'diagrama', 'historia' 
    ]

    try:
        cursor = connection.cursor()
        id_to_update = data.get('id_anamnesis')

        # Parsear fecha
        try:
            fecha_sql = parse_date(data.get('fecha'))
        except ValueError as ve:
            print(f"Error fatal (save_anamnesis): {ve}")
            return False

        if id_to_update:
            # UPDATE
            set_parts = [
                "`fecha`=%s"  
            ]
            values_list = [fecha_sql] 

            for col in data_columns:
                set_parts.append(f"`{col}`=%s")
                values_list.append(data.get(col))

            set_clause = ", ".join(set_parts)
            query = f"UPDATE anamnesis SET {set_clause} WHERE id_anamnesis=%s"
            values_list.append(id_to_update)
            values = tuple(values_list)
            print(f"Actualizando anamnesis (con historia) para ID_ANAMNESIS: {id_to_update}")
        else:
            # INSERT
            insert_columns = ['id_px', 'fecha'] + data_columns
            column_names = ", ".join([f"`{col}`" for col in insert_columns])
            placeholders = "%s, %s, " + ", ".join(['%s'] * len(data_columns))
            
            query = f"INSERT INTO anamnesis ({column_names}) VALUES ({placeholders})"
            
            values_list = [data['id_px'], fecha_sql] # id_px y fecha primero
            for col in data_columns:
                values_list.append(data.get(col))
            values = tuple(values_list)
            print(f"Insertando nueva anamnesis (con historia) para ID_PX: {data.get('id_px')} en Fecha: {fecha_sql}")

        cursor.execute(query, values)
        connection.commit()
        print("Anamnesis guardada/actualizada exitosamente.")
        return True
    except IntegrityError as ie:
        # Verifica si el error es específicamente por la restricción UNIQUE que creamos
        if 'uq_anamnesis_paciente_fecha' in str(ie):
            print(f"ERROR (save_anamnesis): Intento de duplicar registro para paciente {data.get('id_px')} en fecha {data.get('fecha')}.")
            # Devuelve un valor especial para indicar duplicado
            return "duplicate" 
        else:
            # Si es otro error de integridad, regístralo y devuelve False
            print(f"ERROR (save_anamnesis): Error de Integridad no esperado: {ie}")
            return False
    except Error as e:
        # Captura otros errores de la base de datos
        print(f"ERROR (save_anamnesis): Error de Base de Datos: {e}")
        return False
    except Exception as ex:
         # Captura cualquier otro error inesperado
         print(f"ERROR (save_anamnesis): Error inesperado: {ex}")
         return False
    finally:
        if cursor:
            cursor.close()

def get_latest_antecedente(connection, patient_id):
    """Obtiene el registro de antecedentes más reciente para un paciente."""
    cursor = None
    try:
        # Ordena por fecha descendente (convirtiendo el varchar) y luego por ID descendente
        # para obtener el último registro para la fecha más reciente.
        query = """
            SELECT id_antecedente, id_px, fecha, peso, altura, calzado, condiciones_generales,
                   condicion_diagnosticada, presion_alta, trigliceridos, diabetes, agua, notas
            FROM antecedentes
            WHERE id_px = %s
            ORDER BY fecha DESC, id_antecedente DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        antecedente_data = cursor.fetchone()
        # Formatear calzado si existe
        if antecedente_data and antecedente_data.get('calzado'):
             try: antecedente_data['calzado'] = float(antecedente_data['calzado'])
             except (TypeError, ValueError): antecedente_data['calzado'] = 0.0
        return antecedente_data # Devuelve diccionario o None
    except Error as e:
        print(f"Error obteniendo el último antecedente para paciente {patient_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_latest_anamnesis(connection, patient_id):
    """Obtiene el registro de anamnesis más reciente para un paciente."""
    cursor = None
    try:
        # Ordena igual que antecedentes para obtener el último
        query = """
            SELECT id_anamnesis, id_px, fecha, condicion1, calif1, condicion2, calif2,
                   condicion3, calif3, como_comenzo, primera_vez, alivia, empeora,
                   como_ocurrio, actividades_afectadas, dolor_intenso, tipo_dolor,
                   diagrama, historia
            FROM anamnesis
            WHERE id_px = %s
            ORDER BY fecha DESC, id_anamnesis DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        anamnesis_data = cursor.fetchone()
        return anamnesis_data # Devuelve diccionario o None
    except Error as e:
        print(f"Error obteniendo la última anamnesis para paciente {patient_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_postura_summary(connection, patient_id):
    """Obtiene fechas de registros existentes en la tabla 'postura'."""
    cursor = None
    try:
        # Seleccionar solo fechas distintas, ordenadas
        query = """
            SELECT DISTINCT fecha
            FROM postura
            WHERE id_px = %s
            ORDER BY fecha DESC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        
        results = cursor.fetchall()
        dates = []
        
        # 2. Formateamos la fecha usando Python, no SQL
        for row in results:
            if row['fecha']:
                dates.append(row['fecha'].strftime('%d/%m/%Y'))
              
        return dates
    except Error as e:
        print(f"Error obteniendo resumen de postura: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

 
def get_specific_postura_by_date(connection, patient_id, fecha_str):
    """Obtiene los datos de 'postura' para una fecha específica.
       *** ACTUALIZADO: Incluye pies_frontal y pies_trasera, quita rx original. ***
    """
    cursor = None
    try:
        fecha_sql_str = parse_date(fecha_str)
    except ValueError as e:
        print(f"Error (get_specific_postura_by_date): {e}")
        return None
    
    try:
        # 2. Modificar la consulta para usar la comparación de string directa
        query = """
            SELECT id_postura, id_px, fecha, frente, lado, postura_extra, pies,
                   pies_frontal, pies_trasera, 
                   pie_cm, zapato_cm, tipo_calzado, termografia,
                   fuerza_izq, fuerza_der, oxigeno,
                   notas_plantillas, notas_pruebas_ortoneuro
            FROM postura
            WHERE id_px = %s AND fecha = %s  -- <-- ¡YA NO USA STR_TO_DATE!
            ORDER BY id_postura DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id, fecha_sql_str))
        postura_data = cursor.fetchone()
        # ... (conversión de decimales igual que antes) ...
        if postura_data:
             for key in ['pie_cm', 'zapato_cm', 'fuerza_izq', 'fuerza_der']:
                 if key in postura_data and postura_data[key] is not None:
                     try: postura_data[key] = float(postura_data[key])
                     except (TypeError, ValueError): postura_data[key] = 0.0
        return postura_data
    except Error as e:
        print(f"Error obteniendo postura específica (px:{patient_id}, fecha:{fecha_str}): {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def save_postura(connection, data):
    cursor = None
    required_keys = ['id_px', 'fecha']
    if not all(key in data for key in required_keys): print("Error save_postura: Faltan claves."); return None

    # --- Lista COMPLETA de columnas (sin PK) ---
    data_columns = [
        'fecha', 
        'frente', 'lado', 'postura_extra', 'pies',
        'pies_frontal', 'pies_trasera',
        'pie_cm', 'zapato_cm', 'tipo_calzado',
        'termografia', 'fuerza_izq', 'fuerza_der', 'oxigeno',
        'notas_plantillas', 'notas_pruebas_ortoneuro'
    ]

    try:
        # Obtener ID existente si no se pasó explícitamente 'id_postura'
        id_to_update = data.get('id_postura')
        existing_data = {}
        if not id_to_update:
            # Buscar por paciente y fecha para ver si actualizamos o insertamos
            existing_by_date = get_specific_postura_by_date(connection, data['id_px'], data['fecha'])
            if existing_by_date:
                id_to_update = existing_by_date.get('id_postura')
                existing_data = existing_by_date # Guardar datos originales para UPDATE
        elif id_to_update: # Si se pasó un ID, intentar cargar esos datos por si faltan en 'data'
             existing_data_temp = get_specific_postura_by_date(connection, data['id_px'], data['fecha']) # Podríamos usar un get_by_id si existiera
             if existing_data_temp and existing_data_temp.get('id_postura') == id_to_update:
                  existing_data = existing_data_temp
             else: # Inconsistencia si el ID pasado no coincide con la fecha/paciente
                  print(f"WARN: ID de postura {id_to_update} no coincide con paciente/fecha {data['id_px']}/{data['fecha']}")
                  # Podrías lanzar un error aquí o continuar bajo riesgo
                  existing_data = {}


        cursor = connection.cursor()
        saved_id_postura = None

        # Asegurar que todas las columnas tengan un valor (nuevo o existente)
        for col in data_columns:
            if col not in data: # Si el dato no viene del form
                data[col] = existing_data.get(col) # Usar el existente (será None si no había o era nuevo)

        if id_to_update:
            # UPDATE
            update_columns = [col for col in data_columns if col != 'fecha']
            set_clause = ", ".join([f"`{col}`=%s" for col in update_columns])
            query = f"UPDATE postura SET {set_clause} WHERE id_postura=%s"
            values = tuple(data.get(col) for col in update_columns) + (id_to_update,)
            print(f"Actualizando postura para ID_POSTURA: {id_to_update}")
            cursor.execute(query, values)
            saved_id_postura = id_to_update
        else:
            # INSERT 
            
            # 1. Obtenemos la fecha 'dd/mm/YYYY' que nos llega
            fecha_str_ddmmyyyy = data.get('fecha')
            fecha_str_yyyymmdd = None
            
            # 2. La convertimos a 'YYYY-MM-DD' usando Python
            try:
                fecha_str_yyyymmdd = to_db_str(fecha_str_ddmmyyyy)
            except ValueError as e:
                print(f"Error fatal (save_postura): {e}")
                raise Error(f"La fecha '{fecha_str_ddmmyyyy}' tiene un formato inválido.")

            # 3. Separamos 'fecha' del resto de columnas
            data_columns_no_fecha = [col for col in data_columns if col != 'fecha']
            
            # 4. Construimos las columnas: id_px, fecha, ...resto
            insert_columns = ['id_px', 'fecha'] + data_columns_no_fecha
            column_names = ", ".join([f"`{col}`" for col in insert_columns])
            
            # 5. Construimos los placeholders: %s para todo, ¡ya no usamos STR_TO_DATE!
            placeholders_list = ['%s'] * len(insert_columns)
            placeholders = ", ".join(placeholders_list)
            
            query = f"INSERT INTO postura ({column_names}) VALUES ({placeholders})"

            # 6. Construimos los valores en el orden correcto
            values_list_insert = [data['id_px'], fecha_str_yyyymmdd] # id_px y la fecha YYYY-MM-DD
            for col in data_columns_no_fecha:
                values_list_insert.append(data.get(col)) # El resto de valores
            
            values = tuple(values_list_insert)
            
            print(f"Insertando nueva postura (Python-side) para ID_PX: {data.get('id_px')} en Fecha: {fecha_str_yyyymmdd}")
            
            cursor.execute(query, values)
            # --- !! FIN DEL NUEVO BLOQUE CORREGIDO !! ---
            saved_id_postura = cursor.lastrowid

        # NO Commit (se hace en la ruta)
        print(f"Operación en 'postura' lista para commit. ID afectado/nuevo: {saved_id_postura}")
        return saved_id_postura

    except Error as e:
        print(f"Error en save_postura: {e}")
        return None
    finally:
        if cursor: cursor.close()


def get_radiografias_for_postura(connection, id_postura):
    """Obtiene todas las radiografías asociadas a un id_postura."""
    cursor = None
    try:
        query = """
            SELECT id_radiografia, id_postura, fecha_carga, ruta_archivo
            FROM radiografias
            WHERE id_postura = %s
            ORDER BY fecha_carga DESC, id_radiografia DESC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_postura,))
        rx_list = cursor.fetchall()
        return rx_list if rx_list else [] # Devolver lista vacía si no hay nada
    except Error as e:
        print(f"Error obteniendo radiografías para id_postura {id_postura}: {e}")
        return [] # Devolver lista vacía en caso de error
    finally:
        if cursor:
            cursor.close()

def insert_radiografia(connection, id_postura, ruta_archivo):
    """Inserta un nuevo registro de radiografía."""
    cursor = None
    try:
        cursor = connection.cursor()
        query = """
            INSERT INTO radiografias (id_postura, ruta_archivo)
            VALUES (%s, %s)
        """
        values = (id_postura, ruta_archivo)
        cursor.execute(query, values)
        # No necesitamos commit aquí si se hace después de todas las inserciones en la ruta
        print(f"Insertado registro en radiografias para id_postura {id_postura}, ruta: {ruta_archivo}")
        return cursor.lastrowid
    except Error as e:
        print(f"Error insertando radiografía: {e}")
        raise # Re-lanzar para que la ruta haga rollback si es necesario
    finally:
        if cursor:
            cursor.close()

def get_revaloraciones_summary(connection, patient_id):
    """Obtiene lista de IDs y fechas de revaloraciones para un paciente."""
    # --- SIN CAMBIOS ---
    cursor = None
    summary_list = []
    try:
        query = """
            SELECT id_revaloracion, fecha
            FROM revaloraciones
            WHERE id_px = %s
            ORDER BY fecha DESC, id_revaloracion DESC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        summary_list = cursor.fetchall()
        return summary_list
    except Error as e:
        print(f"Error obteniendo resumen de revaloraciones: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_specific_revaloracion(connection, id_revaloracion):
    """Obtiene los datos de un registro de revaloración específico por su ID único.
       *** ACTUALIZADO: Incluye nuevas columnas de imagen. ***
    """
    cursor = None
    try:
        # Seleccionar TODAS las columnas, incluyendo las nuevas de imagen (aliased desde postura)
        query = """
            SELECT r.id_revaloracion, r.id_px, r.id_dr, r.fecha, r.id_anamnesis_inicial,
                   r.id_postura_asociado,
                   r.calif1_actual, r.calif2_actual, r.calif3_actual,
                   r.mejora_subjetiva_pct,
                   r.notas_adicionales_reval,
                   r.diagrama_actual,
                   r.fecha_registro,
                   -- Columnas de imagen desde postura (aliased para compatibilidad)
                   p.frente AS frente_path,
                   p.lado AS lado1_path,
                   p.postura_extra AS lado2_path,
                   p.pies AS pies_path,
                   p.termografia AS termografia_path,
                   p.pies_frontal AS pies_frontal_path,
                   p.pies_trasera AS pies_trasera_path
            FROM revaloraciones r
            LEFT JOIN postura p ON r.id_postura_asociado = p.id_postura
            WHERE r.id_revaloracion = %s
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_revaloracion,))
        revaloracion_data = cursor.fetchone()
        return revaloracion_data # Devuelve diccionario o None
    except Error as e:
        print(f"Error obteniendo revaloración específica por ID {id_revaloracion}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_specific_revaloracion_by_date(connection, patient_id, fecha_str):
    """Obtiene el registro de revaloración más reciente para un paciente en una fecha específica.
       *** ACTUALIZADO: Convierte fecha_str (dd/mm/yyyy) a YYYY-MM-DD en Python. ***
    """
    cursor = None
    
    # --- !! INICIO DE LA CORRECCIÓN !! ---
    try:
        fecha_sql_str = parse_date(fecha_str)
    except ValueError as e:
        print(f"Error (get_specific_revaloracion_by_date): {e}")
        return None
    # --- !! FIN DE LA CORRECCIÓN !! ---

    try:
        # 2. Modificar la consulta (ya no necesita STR_TO_DATE)
        query = """
            SELECT id_revaloracion, id_px, id_dr, fecha, id_anamnesis_inicial,
                   id_postura_asociado,
                   calif1_actual, calif2_actual, calif3_actual,
                   mejora_subjetiva_pct,
                   notas_adicionales_reval,
                   diagrama_actual,
                   fecha_registro
            FROM revaloraciones
            WHERE id_px = %s AND fecha = %s  -- <-- Comparación directa
            ORDER BY id_revaloracion DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        
        # 3. Pasar el nuevo string YYYY-MM-DD a la consulta
        cursor.execute(query, (patient_id, fecha_sql_str)) 
        revaloracion_data = cursor.fetchone()
        return revaloracion_data # Devuelve diccionario o None
    except Error as e:
        print(f"Error obteniendo revaloración específica por fecha (px:{patient_id}, fecha:{fecha_str}): {e}")
        return None
    finally:
        if cursor:
            cursor.close()
            
def save_revaloracion(connection, data):
    """Guarda revaloración. Incluye nuevas fotos de pies. NO HACE COMMIT."""
    cursor = None
    required_keys = ['id_px', 'id_dr', 'fecha']
    if not all(key in data for key in required_keys): 
        print("Error save_revaloracion: Faltan claves.")
        return None

    data_columns = [
        'fecha', 'id_anamnesis_inicial', 'id_postura_asociado',
        'calif1_actual', 'calif2_actual',
        'calif3_actual', 'mejora_subjetiva_pct', 'notas_adicionales_reval', 'diagrama_actual'
    ]

    try:
        cursor = connection.cursor()
        id_to_update = data.get('id_revaloracion')
        saved_id = None

        existing_data = {}
        if id_to_update:
            existing_data_temp = get_specific_revaloracion(connection, id_to_update)
            existing_data = existing_data_temp if existing_data_temp else {}

        for col in data_columns:
            if col not in data:
                data[col] = existing_data.get(col) if id_to_update else None

        # --- !! INICIO DE LA CORRECCIÓN DE FECHA !! ---
        
        # 1. Obtenemos la fecha 'dd/mm/YYYY' que nos llega
        fecha_str_ddmmyyyy = data.get('fecha')
        fecha_sql_str = None
        
        try:
            fecha_sql_str = parse_date(fecha_str_ddmmyyyy)
        except ValueError as e:
            print(f"Error fatal (save_revaloracion): {e}")
            raise Error(f"La fecha '{fecha_str_ddmmyyyy}' tiene un formato inválido.")
        
        # --- !! FIN DE LA CORRECCIÓN DE FECHA !! ---


        if id_to_update:
            # UPDATE
            
            # 2. Separamos 'fecha' del resto para el UPDATE
            update_columns_no_fecha = [col for col in data_columns if col != 'fecha']
            
            # Construimos la consulta de UPDATE (incluyendo la fecha YYYY-MM-DD)
            set_parts = [f"`fecha`=%s"] + [f"`{col}`=%s" for col in update_columns_no_fecha]
            set_clause = ", ".join(set_parts)
            
            query = f"UPDATE revaloraciones SET {set_clause} WHERE id_revaloracion=%s"
            
            # Construimos los valores (la fecha YYYY-MM-DD primero)
            values_list_update = [fecha_sql_str] 
            for col in update_columns_no_fecha:
                values_list_update.append(data.get(col))
            values_list_update.append(id_to_update) # El ID al final
            
            values = tuple(values_list_update)
            
            print(f"Actualizando revaloración (Python-side) para ID: {id_to_update}")
            cursor.execute(query, values)
            saved_id = id_to_update
        else:
            # INSERT
            
            # 3. Separamos 'fecha' del resto para el INSERT
            data_columns_no_fecha = [col for col in data_columns if col != 'fecha']
            
            insert_columns = ['id_px', 'id_dr', 'fecha'] + data_columns_no_fecha
            column_names = ", ".join([f"`{col}`" for col in insert_columns])
            
            # 4. Placeholders simples (%s)
            placeholders = ", ".join(['%s'] * len(insert_columns))
            query = f"INSERT INTO revaloraciones ({column_names}) VALUES ({placeholders})"
            
            # 5. Valores (usando la fecha YYYY-MM-DD)
            values_list_insert = [data.get('id_px'), data.get('id_dr'), fecha_sql_str]
            for col_name in data_columns_no_fecha:
                values_list_insert.append(data.get(col_name))
            
            values = tuple(values_list_insert)
            
            print(f"Insertando nueva revaloración (Python-side) para ID_PX: {data['id_px']} en Fecha: {fecha_sql_str}")
            cursor.execute(query, values)
            saved_id = cursor.lastrowid

        print(f"Operación en 'revaloraciones' lista para commit. ID afectado/nuevo: {saved_id}")
        return saved_id
    except Error as e:
        print(f"Error en save_revaloracion: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_latest_revaloracion_on_or_before_date(connection, patient_id, target_date_str):
    """
    Obtiene el registro de revaloración más reciente para un paciente
    en o antes de una fecha específica.
    """
    cursor = None
    try:
        # Convertir la fecha target a formato YYYY-MM-DD para comparación SQL segura
        target_date_obj = datetime.strptime(target_date_str, '%d/%m/%Y')

        # Query para encontrar la revaloración más reciente en o antes de la fecha target
        query = """
            SELECT id_revaloracion, id_px, id_dr, fecha, id_anamnesis_inicial,
                   calif1_actual, calif2_actual, calif3_actual,
                   mejora_subjetiva_pct, -- Se mantiene
                   notas_adicionales_reval, -- <-- AÑADIDA
                   diagrama_actual,
                   frente_path, lado1_path, lado2_path, pies_path, termografia_path,
                   pies_frontal_path, pies_trasera_path,
                   fecha_registro
            FROM revaloraciones
            WHERE id_px = %s
              AND fecha <= %s -- Fecha menor o igual
            ORDER BY fecha DESC, id_revaloracion DESC -- Ordenar por fecha descendente
            LIMIT 1 -- Obtener solo la más reciente que cumpla la condición
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id, target_date_obj.strftime('%Y-%m-%d'))) # Pasar fecha en formato SQL
        revaloracion_data = cursor.fetchone()
        return revaloracion_data # Devuelve diccionario o None
    except ValueError:
        print(f"Error: Formato de fecha inválido '{target_date_str}' al buscar última revaloración.")
        return None
    except Error as e:
        print(f"Error obteniendo última revaloración (px:{patient_id}, hasta fecha:{target_date_str}): {e}")
        return None
    finally:
        if cursor:
            cursor.close()


def get_latest_revaloracion_overall(connection, patient_id):
    """Obtiene el registro de la última revaloración realizada para un paciente."""
    cursor = None
    try:
        query = """
            SELECT r.id_revaloracion, r.id_px, r.id_dr, r.fecha, r.id_anamnesis_inicial,
                   r.calif1_actual, r.calif2_actual, r.calif3_actual,
                   r.mejora_subjetiva_pct,
                   r.notas_adicionales_reval,
                   r.diagrama_actual,
                   r.fecha_registro,
                   -- Columnas de imagen desde postura (aliased)
                   p.frente AS frente_path,
                   p.lado AS lado1_path,
                   p.postura_extra AS lado2_path,
                   p.pies AS pies_path,
                   p.termografia AS termografia_path,
                   p.pies_frontal AS pies_frontal_path,
                   p.pies_trasera AS pies_trasera_path
            FROM revaloraciones r
            LEFT JOIN postura p ON r.id_postura_asociado = p.id_postura
            WHERE r.id_px = %s
            ORDER BY r.fecha DESC, r.id_revaloracion DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        revaloracion_data = cursor.fetchone()
        return revaloracion_data # Devuelve diccionario o None
    except Error as e:
        print(f"Error obteniendo última revaloración general para paciente {patient_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_clinical_dates_with_types(connection, patient_id):
    """
    Obtiene una lista de diccionarios, cada uno con una fecha y booleanos
    indicando qué tipos de registros clínicos existen para esa fecha,
    ordenada por fecha ascendente.
    """
    cursor = None
    dates_info = {}
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)

        # 1. Obtener todas las fechas distintas
        all_dates = set()
        tables_to_check = ['antecedentes', 'anamnesis', 'postura', 'revaloraciones']
        for table in tables_to_check:
            query_dates = f"SELECT DISTINCT fecha FROM {table} WHERE id_px = %s"
            cursor.execute(query_dates, (patient_id,))
            for row in cursor.fetchall():
                 if row and row.get('fecha'):
                    date_val = row['fecha']
                    formatted_date = None
                    
                    if isinstance(date_val, (date, datetime, str)):
                        formatted_date = to_frontend_str(date_val)
                    
                    if formatted_date:
                        all_dates.add(formatted_date)

        # 2. Para cada fecha, verificar registros
        for fecha_str in all_dates:
            info = {
                'fecha': fecha_str,
                'has_antecedentes': False,
                'has_anamnesis': False,
                'has_postura': False,
                'has_revaloracion': False
            }
            
            # Convertir fecha_str (dd/mm/yyyy) a SQL (YYYY-MM-DD) para la consulta
            fecha_sql = to_db_str(fecha_str)
            if not fecha_sql:
                continue

            # Usar "AS flag" para asegurar el nombre de la clave
            query_check = "SELECT EXISTS(SELECT 1 FROM {table} WHERE id_px = %s AND fecha = %s LIMIT 1) AS flag"
            try:
                 cursor.execute(query_check.format(table='antecedentes'), (patient_id, fecha_sql))
                 info['has_antecedentes'] = bool(cursor.fetchone().get('flag', 0))

                 cursor.execute(query_check.format(table='anamnesis'), (patient_id, fecha_sql))
                 info['has_anamnesis'] = bool(cursor.fetchone().get('flag', 0))

                 cursor.execute(query_check.format(table='postura'), (patient_id, fecha_sql))
                 info['has_postura'] = bool(cursor.fetchone().get('flag', 0))

                 cursor.execute(query_check.format(table='revaloraciones'), (patient_id, fecha_sql))
                 info['has_revaloracion'] = bool(cursor.fetchone().get('flag', 0))

                 dates_info[fecha_str] = info
            except Error as check_err:
                 print(f"WARN: Error verificando registros para fecha {fecha_str}: {check_err}")

        # 3. Convertir y ordenar
        if not dates_info: return []
        sorted_list = sorted(dates_info.values(), key=lambda item: to_db_str(item['fecha']))
        return sorted_list

    except Error as e:
        print(f"Error obteniendo fechas clínicas con tipos para paciente {patient_id}: {e}")
        return []
    finally:
        if cursor: cursor.close()

def get_latest_antecedente_on_or_before_date(connection, patient_id, target_date_str):
    """
    Obtiene el registro de antecedentes más reciente para un paciente
    en o antes de una fecha específica.
    """
    cursor = None
    try:
        target_date_obj = datetime.strptime(target_date_str, '%d/%m/%Y')
        query = """
            SELECT id_antecedente, id_px, fecha, peso, altura, calzado, condiciones_generales,
                   condicion_diagnosticada, presion_alta, trigliceridos, diabetes, agua, notas
            FROM antecedentes
            WHERE id_px = %s AND fecha <= %s
            ORDER BY fecha DESC, id_antecedente DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id, target_date_obj.strftime('%Y-%m-%d')))
        data = cursor.fetchone()
        if data and data.get('calzado'): # Formatear decimal
             try: data['calzado'] = float(data['calzado'])
             except (TypeError, ValueError): data['calzado'] = 0.0
        return data
    except ValueError:
        print(f"Error: Formato de fecha inválido '{target_date_str}' al buscar último antecedente.")
        return None
    except Error as e:
        print(f"Error obteniendo último antecedente (px:{patient_id}, hasta fecha:{target_date_str}): {e}")
        return None
    finally:
        if cursor: cursor.close()

def get_latest_anamnesis_on_or_before_date(connection, patient_id, target_date_str):
    """
    Obtiene el registro de anamnesis más reciente para un paciente
    en o antes de una fecha específica.
    """
    cursor = None
    try:
        target_date_db = to_db_str(target_date_str)
        query = """
            SELECT id_anamnesis, id_px, fecha, condicion1, calif1, condicion2, calif2,
                   condicion3, calif3, como_comenzo, primera_vez, alivia, empeora,
                   como_ocurrio, actividades_afectadas, dolor_intenso, tipo_dolor,
                   diagrama, historia
            FROM anamnesis
            WHERE id_px = %s AND fecha <= %s
            ORDER BY fecha DESC, id_anamnesis DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id, target_date_db))
        data = cursor.fetchone()
        return data
    except ValueError:
        print(f"Error: Formato de fecha inválido '{target_date_str}' al buscar última anamnesis.")
        return None
    except Error as e:
        print(f"Error obteniendo última anamnesis (px:{patient_id}, hasta fecha:{target_date_str}): {e}")
        return None
    finally:
        if cursor: cursor.close()

def get_latest_postura_on_or_before_date(connection, patient_id, target_date_str):
    """
    Obtiene el registro de postura/pruebas más reciente para un paciente
    en o antes de una fecha específica (sin la columna 'rx' original).
    """
    cursor = None
    try:
        target_date_obj = datetime.strptime(target_date_str, '%d/%m/%Y')
        query = """
            SELECT id_postura, id_px, fecha, frente, lado, postura_extra, pies,
               pie_cm, zapato_cm, tipo_calzado, termografia,
               fuerza_izq, fuerza_der, oxigeno,
               pies_frontal, pies_trasera, notas_plantillas,
               notas_pruebas_ortoneuro -- <-- AÑADIDA AQUÍ
            FROM postura
            WHERE id_px = %s AND fecha <= %s
            ORDER BY fecha DESC, id_postura DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id, target_date_obj.strftime('%Y-%m-%d')))
        data = cursor.fetchone()
        if data: # Formatear decimales si se encontró registro
            for key in ['pie_cm', 'zapato_cm', 'fuerza_izq', 'fuerza_der']:
                if key in data and data[key] is not None:
                    try: data[key] = float(data[key])
                    except (TypeError, ValueError): data[key] = 0.0
        return data
    except ValueError:
        print(f"Error: Formato de fecha inválido '{target_date_str}' al buscar última postura.")
        return None
    except Error as e:
        print(f"Error obteniendo última postura (px:{patient_id}, hasta fecha:{target_date_str}): {e}")
        return None
    finally:
        if cursor: cursor.close()

def get_seguimiento_summary(connection, patient_id):
    """Obtiene lista de IDs y fechas de seguimientos para un paciente."""
    cursor = None
    try:
        # Usar la nueva clave primaria 'id_seguimiento'
        query = """
            SELECT id_seguimiento, fecha
            FROM quiropractico
            WHERE id_px = %s
            ORDER BY fecha DESC, id_seguimiento DESC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        summary_list = cursor.fetchall()
        return summary_list
    except Error as e:
        print(f"Error obteniendo resumen de seguimiento: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_specific_seguimiento(connection, id_seguimiento):
    """Obtiene los datos de un registro de seguimiento específico por su ID.
       Incluye el nombre del doctor.
    """
    cursor = None
    try:
        # --- CAMBIO: JOIN con la tabla 'dr' para obtener nombre_doctor ---
        query = """
            SELECT 
                q.id_seguimiento, q.id_px, q.fecha, q.occipital, q.atlas, q.axis, 
                q.c3, q.c4, q.c5, q.c6, q.c7,
                q.t1, q.t2, q.t3, q.t4, q.t5, q.t6, q.t7, q.t8, q.t9, q.t10, q.t11, q.t12,
                q.l1, q.l2, q.l3, q.l4, q.l5, q.sacro, q.coxis, q.iliaco_d, q.iliaco_i,
                q.notas, q.terapia, q.pubis,
                q.id_plan_cuidado_asociado, 
                q.id_dr, 
                dr.nombre as nombre_doctor_seguimiento 
            FROM quiropractico q
            LEFT JOIN dr ON q.id_dr = dr.id_dr 
            WHERE q.id_seguimiento = %s
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_seguimiento,))
        seguimiento_data = cursor.fetchone()
        return seguimiento_data
    except Error as e:
        print(f"Error obteniendo seguimiento específico por ID {id_seguimiento}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_specific_seguimiento_by_date(connection, patient_id, fecha_str):
    """Obtiene el registro de seguimiento más reciente para un paciente en una fecha específica.
       Incluye el nombre del doctor.
    """
    cursor = None
    try:
        fecha_sql_str = parse_date(fecha_str)
    except ValueError as e:
        print(f"Error (get_specific_seguimiento_by_date): {e}")
        return None
    try:
        # --- CAMBIO: JOIN con la tabla 'dr' ---
        query = """
            SELECT 
                q.id_seguimiento, q.id_px, q.fecha, q.occipital, q.atlas, q.axis, 
                q.c3, q.c4, q.c5, q.c6, q.c7,
                q.t1, q.t2, q.t3, q.t4, q.t5, q.t6, q.t7, q.t8, q.t9, q.t10, q.t11, q.t12,
                q.l1, q.l2, q.l3, q.l4, q.l5, q.sacro, q.coxis, q.iliaco_d, q.iliaco_i,
                q.notas, q.terapia, q.pubis,
                q.id_plan_cuidado_asociado, 
                q.id_dr,
                dr.nombre as nombre_doctor_seguimiento
            FROM quiropractico q
            LEFT JOIN dr ON q.id_dr = dr.id_dr
            WHERE q.id_px = %s AND q.fecha = %s
            ORDER BY q.id_seguimiento DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id, fecha_sql_str))
        seguimiento_data = cursor.fetchone()
        return seguimiento_data
    except Error as e:
        print(f"Error obteniendo seguimiento específico por fecha (px:{patient_id}, fecha:{fecha_str}): {e}")
        return None
    finally:
        if cursor:
            cursor.close()


def save_seguimiento(connection, data):
    """
    Guarda (INSERT o UPDATE) los datos de seguimiento en la tabla 'quiropractico'.
    Determina acción basado en si 'id_seguimiento' está en 'data'.
    'data' DEBE contener 'id_px' y 'fecha'.
    *** ACTUALIZADO para incluir id_plan_cuidado_asociado ***
    NO HACE COMMIT. Devuelve el ID afectado o None.
    """
    cursor = None
    required_keys = ['id_px', 'id_dr', 'fecha'] 
    if not all(key in data and data[key] is not None for key in required_keys):
         print("Error: Faltan id_px, id_dr o fecha en los datos de seguimiento a guardar.")
         return None

    # Lista completa de columnas de la tabla 'quiropractico' (excepto id_seguimiento, id_px)
    data_columns = [
        'fecha', 'occipital', 'atlas', 'axis', 'c3', 'c4', 'c5', 'c6', 'c7',
        't1', 't2', 't3', 't4', 't5', 't6', 't7', 't8', 't9', 't10', 't11', 't12',
        'l1', 'l2', 'l3', 'l4', 'l5', 'sacro', 'coxis', 'iliaco_d', 'iliaco_i',
        'notas', 'terapia', 'pubis',
        'id_plan_cuidado_asociado','id_dr' # <-- NUEVA COLUMNA AÑADIDA
    ]

    try:
        try:
            fecha_sql_str = parse_date(data.get('fecha'))
        except ValueError as e:
            print(f"Error fatal (save_seguimiento): {e}")
            raise Error(f"La fecha '{data.get('fecha')}' tiene un formato inválido.")

        cursor = connection.cursor()
        id_to_update = data.get('id_seguimiento')
        saved_id = None

        # Asegurar que todas las data_columns existan en el diccionario 'data' o asignarles un valor por defecto
        # para evitar errores al construir la tupla de valores.
        # Usar '' para strings y None para el id_plan_cuidado_asociado si no viene.
        existing_data = {}
        if id_to_update:
            existing_data_temp = get_specific_seguimiento(connection, id_to_update) # Para obtener datos que no vienen del form
            existing_data = existing_data_temp if existing_data_temp else {}

        for col in data_columns:
            if col not in data: # Si el dato no viene del form
                # Mantener el valor original si es una actualización y la clave no viene en 'data'
                data[col] = existing_data.get(col) if id_to_update else (None if col == 'id_plan_cuidado_asociado' else '')


        if id_to_update:
            # --- UPDATE ---
            data_columns_no_fecha = [col for col in data_columns if col != 'fecha']
            set_parts = [f"`fecha`=%s"] + [f"`{col}`=%s" for col in data_columns_no_fecha]
            set_clause = ", ".join(set_parts)
            
            query = f"UPDATE quiropractico SET {set_clause} WHERE id_seguimiento=%s"
            
            values_list_update = [fecha_sql_str] # Usar fecha YYYY-MM-DD
            for col in data_columns_no_fecha:
                values_list_update.append(data.get(col))
            values_list_update.append(id_to_update)
            
            values = tuple(values_list_update)
            print(f"Actualizando seguimiento (Python-side) para ID: {id_to_update}")
        else:
            # --- INSERT ---
            data_columns_no_fecha = [col for col in data_columns if col != 'fecha']
            insert_columns = ['id_px', 'fecha'] + data_columns_no_fecha
            column_names = ", ".join([f"`{col}`" for col in insert_columns])
            placeholders = ", ".join(['%s'] * len(insert_columns))
            query = f"INSERT INTO quiropractico ({column_names}) VALUES ({placeholders})"
            
            values_list_insert = [data['id_px'], fecha_sql_str] # Usar fecha YYYY-MM-DD
            for col_name in data_columns_no_fecha:
                values_list_insert.append(data.get(col_name))
            values = tuple(values_list_insert)
            print(f"Insertando nuevo seguimiento (Python-side) para ID_PX: {data['id_px']} en Fecha: {fecha_sql_str}")

        cursor.execute(query, values)

        if not id_to_update:
            saved_id = cursor.lastrowid
        else:
            saved_id = id_to_update

        print(f"Operación en 'quiropractico' lista para commit. ID afectado/nuevo: {saved_id}")
        return saved_id
    except Error as e:
        print(f"Error guardando/actualizando seguimiento: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_terapias_fisicas(connection):
    """Obtiene la lista de terapias físicas disponibles (adicional=2)."""
    cursor = None
    try:
        # Selecciona ID y nombre de productos donde 'adicional' es 2 (o el valor que uses)
        query = """
            SELECT id_prod, nombre
            FROM productos_servicios
            WHERE adicional = 2
            ORDER BY nombre ASC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query)
        therapies = cursor.fetchall()
        return therapies if therapies else [] # Devuelve lista de diccionarios o lista vacía
    except Error as e:
        print(f"Error obteniendo terapias físicas: {e}")
        return [] # Devuelve lista vacía en caso de error
    finally:
        if cursor:
            cursor.close()

def get_latest_postura_overall(connection, patient_id):
    """
    Obtiene el registro de postura/pruebas más reciente en general para un paciente
    (sin la columna 'rx' original).
    """
    cursor = None
    try:
        query = """
            SELECT id_postura, id_px, fecha, frente, lado, postura_extra, pies,
               pie_cm, zapato_cm, tipo_calzado, termografia,
               fuerza_izq, fuerza_der, oxigeno,
               pies_frontal, pies_trasera, notas_plantillas,
               notas_pruebas_ortoneuro -- <-- AÑADIDA AQUÍ
            FROM postura
            WHERE id_px = %s
            ORDER BY fecha DESC, id_postura DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        data = cursor.fetchone()
        if data: # Formatear decimales si se encontró registro
            for key in ['pie_cm', 'zapato_cm', 'fuerza_izq', 'fuerza_der']:
                if key in data and data[key] is not None:
                    try: data[key] = float(data[key])
                    except (TypeError, ValueError): data[key] = 0.0 # o None
        return data # Devuelve diccionario o None
    except Error as e:
        print(f"Error obteniendo última postura general (px:{patient_id}): {e}")
        return None
    finally:
        if cursor: cursor.close()

def get_latest_radiografias_overall(connection, patient_id, limit=5):
    """
    Obtiene los registros de las 'limit' radiografías más recientes
    para un paciente, ordenadas por fecha de carga descendente.
    """
    cursor = None
    try:
        # Unir con postura para potencialmente obtener la fecha de visita si se quisiera,
        # pero ordenaremos principalmente por la fecha de carga de la radiografía.
        query = """
            SELECT
                rx.id_radiografia,
                rx.id_postura,
                rx.fecha_carga,
                rx.ruta_archivo,
                p.fecha AS fecha_visita_asociada  # Fecha de la visita de postura asociada
            FROM radiografias rx
            JOIN postura p ON rx.id_postura = p.id_postura
            WHERE p.id_px = %s
            ORDER BY rx.fecha_carga DESC, rx.id_radiografia DESC
            LIMIT %s
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id, limit))
        latest_rx = cursor.fetchall()
        return latest_rx if latest_rx else []
    except Error as e:
        print(f"Error obteniendo últimas radiografías generales para paciente {patient_id}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_earliest_anamnesis(connection, patient_id):
    """
    Obtiene el registro completo de la anamnesis más antigua para un paciente,
    considerada como la visita inicial para la comparativa.
    """
    cursor = None
    try:
        # Ordena por fecha ASCENDENTE y luego ID para obtener la primera
        query = """
            SELECT id_anamnesis, id_px, fecha, condicion1, calif1, condicion2, calif2,
                   condicion3, calif3, como_comenzo, primera_vez, alivia, empeora,
                   como_ocurrio, actividades_afectadas, dolor_intenso, tipo_dolor,
                   diagrama, historia
            FROM anamnesis
            WHERE id_px = %s
            ORDER BY fecha ASC, id_anamnesis ASC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        initial_anamnesis_data = cursor.fetchone()
        return initial_anamnesis_data # Devuelve diccionario o None
    except Error as e:
        print(f"Error obteniendo la primera anamnesis para paciente {patient_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_revaloraciones_linked_to_anamnesis(connection, id_anamnesis_inicial):
    """
    Obtiene todos los registros de revaloración vinculados a un id_anamnesis_inicial específico,
    ordenados por fecha ascendente.
    """
    cursor = None
    print(f"DEBUG DB: Entrando a get_revaloraciones_linked_to_anamnesis con id_anamnesis_inicial = {id_anamnesis_inicial} (Tipo: {type(id_anamnesis_inicial)})") # NUEVO
    try:
        query = """
            SELECT id_revaloracion, id_px, id_dr, fecha, id_anamnesis_inicial,
                   id_postura_asociado,  -- <-- AÑADIDO
                   calif1_actual, calif2_actual, calif3_actual,
                   mejora_subjetiva_pct, notas_adicionales_reval,
                   diagrama_actual,
                   fecha_registro
            FROM revaloraciones
            WHERE id_anamnesis_inicial = %s
            ORDER BY fecha ASC, id_revaloracion ASC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        
        # Verificar el tipo del parámetro que se pasa a execute
        param_tuple = (id_anamnesis_inicial,)
        print(f"DEBUG DB: Ejecutando consulta con parámetro: {param_tuple}") # NUEVO

        cursor.execute(query, param_tuple)
        linked_revals = cursor.fetchall()
        
        print(f"DEBUG DB: Resultado de fetchall(): {linked_revals}") # NUEVO (Esto es crucial)
        print(f"DEBUG DB: Número de filas encontradas: {cursor.rowcount}") # NUEVO

        return linked_revals if linked_revals else []
    except Error as e:
        print(f"Error obteniendo revaloraciones vinculadas a anamnesis ID {id_anamnesis_inicial}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_plan_cuidado_summary(connection, patient_id):
    """Obtiene lista de IDs y fechas de planes de cuidado para un paciente."""
    cursor = None
    try:
        query = """
            SELECT id_plan, fecha, pb_diagnostico
            FROM plancuidado
            WHERE id_px = %s
            ORDER BY fecha DESC, id_plan DESC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        summary_list = cursor.fetchall()
        return summary_list if summary_list else []
    except Error as e:
        print(f"Error obteniendo resumen de planes de cuidado: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_specific_plan_cuidado(connection, id_plan):
    """Obtiene los datos de un plan de cuidado específico por su ID único."""
    cursor = None
    try:
        # Seleccionar TODAS las columnas de la tabla plancuidado (estructura nueva)
        query = """
            SELECT id_plan, id_px, id_dr, fecha, pb_diagnostico, plan_descripcion,
                   visitas_qp, visitas_tf, etapa, inversion_total, promocion_pct,
                   ahorro_calculado, adicionales_ids, notas_plan, fecha_registro
            FROM plancuidado
            WHERE id_plan = %s
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_plan,))
        plan_data = cursor.fetchone()
        # Convertir decimales si existen
        if plan_data:
            for key in ['inversion_total', 'ahorro_calculado']:
                 if key in plan_data and plan_data[key] is not None:
                      try: plan_data[key] = float(plan_data[key])
                      except (ValueError, TypeError): plan_data[key] = 0.0
        return plan_data # Devuelve diccionario o None
    except Error as e:
        print(f"Error obteniendo plan de cuidado específico por ID {id_plan}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_specific_plan_cuidado_by_date(connection, patient_id, fecha_str):
    """Obtiene el plan de cuidado más reciente para un paciente en una fecha específica."""
    cursor = None
    try:
        fecha_sql_str = parse_date(fecha_str)
    except ValueError as e:
        print(f"Error (get_specific_plan_cuidado_by_date): {e}")
        return None
    try:
        # Seleccionar TODAS las columnas
        query = """
            SELECT id_plan, id_px, id_dr, fecha, pb_diagnostico, plan_descripcion,
                   visitas_qp, visitas_tf, etapa, inversion_total, promocion_pct,
                   ahorro_calculado, adicionales_ids, notas_plan, fecha_registro
            FROM plancuidado
            WHERE id_px = %s AND fecha = %s
            ORDER BY id_plan DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id, fecha_str))
        plan_data = cursor.fetchone()
        # Convertir decimales
        if plan_data:
            for key in ['inversion_total', 'ahorro_calculado']:
                 if key in plan_data and plan_data[key] is not None:
                      try: plan_data[key] = float(plan_data[key])
                      except (ValueError, TypeError): plan_data[key] = 0.0
        return plan_data # Devuelve diccionario o None
    except Error as e:
        print(f"Error obteniendo plan de cuidado específico por fecha (px:{patient_id}, fecha:{fecha_str}): {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def save_plan_cuidado(connection, data):
    """Guarda (INSERT o UPDATE) los datos del plan de cuidado.
       Determina acción basado en si 'id_plan' está en 'data'.
       'data' DEBE contener 'id_px', 'id_dr', 'fecha'.
       NO HACE COMMIT. Devuelve el ID afectado o None.
    """
    cursor = None
    required_keys = ['id_px', 'id_dr', 'fecha']
    if not all(key in data and data[key] is not None for key in required_keys):
         print("Error: Faltan id_px, id_dr o fecha en los datos del plan a guardar.")
         return None

    # Columnas específicas de la tabla plancuidado (excluyendo PK y timestamp)
    data_columns = [
        'fecha', 'pb_diagnostico', 'visitas_qp', 'visitas_tf',
        'etapa', 'inversion_total', 'promocion_pct', 'ahorro_calculado',
        'adicionales_ids', 'notas_plan'
        # 'id_dr' se maneja aparte en INSERT/UPDATE si se quisiera permitir cambio
    ]

    try:
        try:
            fecha_sql_str = parse_date(data.get('fecha'))
        except ValueError as e:
            print(f"Error fatal (save_plan_cuidado): {e}")
            raise Error(f"La fecha '{data.get('fecha')}' tiene un formato inválido.")
        
        cursor = connection.cursor()
        id_to_update = data.get('id_plan')
        saved_id = None

        # Asegurar que todas las claves esperadas existan en 'data'
        for col in data_columns:
            if col not in data:
                data[col] = None # Asignar None si falta

        if id_to_update:
            # --- UPDATE ---
            data_columns_no_fecha = [col for col in data_columns if col != 'fecha']
            set_parts = [f"`fecha`=%s"] + [f"`{col}`=%s" for col in data_columns_no_fecha]
            set_clause = ", ".join(set_parts)
            
            query = f"UPDATE plancuidado SET {set_clause} WHERE id_plan=%s"
            
            values_list_update = [fecha_sql_str] # Usar fecha YYYY-MM-DD
            for col in data_columns_no_fecha:
                values_list_update.append(data.get(col))
            values_list_update.append(id_to_update)
            
            values = tuple(values_list_update)
            print(f"Actualizando plan de cuidado (Python-side) para ID: {id_to_update}")
        else:
            # --- INSERT ---
            data_columns_no_fecha = [col for col in data_columns if col != 'fecha']
            insert_columns = ['id_px', 'id_dr', 'fecha'] + data_columns_no_fecha
            column_names = ", ".join([f"`{col}`" for col in insert_columns])
            placeholders = ", ".join(['%s'] * len(insert_columns))
            query = f"INSERT INTO plancuidado ({column_names}) VALUES ({placeholders})"

            values_list_insert = [
                data.get('id_px'), data.get('id_dr'), fecha_sql_str, # Usar fecha YYYY-MM-DD
                data.get('pb_diagnostico'), data.get('visitas_qp', 0), data.get('visitas_tf', 0),
                data.get('etapa'), data.get('inversion_total', 0.0), data.get('promocion_pct', 0),
                data.get('ahorro_calculado', 0.0), data.get('adicionales_ids'), data.get('notas_plan')
            ]
            values = tuple(values_list_insert)
            print(f"Insertando nuevo plan de cuidado (Python-side) para ID_PX: {data.get('id_px')} en Fecha: {fecha_sql_str}")

        cursor.execute(query, values)

        if not id_to_update:
            saved_id = cursor.lastrowid
        else:
            saved_id = id_to_update

        # NO HACER COMMIT AQUÍ
        print(f"Operación en 'plancuidado' lista para commit. ID afectado/nuevo: {saved_id}")
        return saved_id
    except Error as e:
        print(f"Error guardando/actualizando plan de cuidado: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_productos_servicios_by_type(connection, tipo_adicional=1):
    """Obtiene productos/servicios filtrados por tipo (ej: 1=Adicionales, 2=Terapia Física)."""
    cursor = None
    try:
        query = """
            SELECT id_prod, nombre, venta as costo # Asumimos que 'venta' es el costo al paciente
            FROM productos_servicios
            WHERE adicional = %s
            ORDER BY nombre ASC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (tipo_adicional,))
        productos = cursor.fetchall()
        # Convertir costo a float por seguridad
        if productos:
            for prod in productos:
                if 'costo' in prod and prod['costo'] is not None:
                     try: prod['costo'] = float(prod['costo'])
                     except (ValueError, TypeError): prod['costo'] = 0.0
        return productos if productos else []
    except Error as e:
        print(f"Error obteniendo productos/servicios (tipo {tipo_adicional}): {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_all_doctors(connection, centro_id=None):
    """Obtiene una lista de doctores (ID y Nombre), opcionalmente filtrada por centro."""
    cursor = None
    try:
        if centro_id is not None:
            # Filtrar por centro si se proporciona
            query = "SELECT id_dr, nombre FROM dr WHERE centro = %s ORDER BY nombre ASC"
            params = (centro_id,)
        else:
            # Obtener todos si no se filtra
            query = "SELECT id_dr, nombre FROM dr ORDER BY nombre ASC"
            params = ()

        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, params)
        doctors = cursor.fetchall()
        return doctors if doctors else []
    except Error as e:
        print(f"Error obteniendo lista de doctores (centro={centro_id}): {e}")
        return []
    finally:
        if cursor:
            cursor.close()

# Asegúrate que get_terapias_fisicas ahora llame a la nueva función genérica:
def get_terapias_fisicas(connection):
    """Obtiene la lista de terapias físicas disponibles (adicional=2)."""
    return get_productos_servicios_by_type(connection, tipo_adicional=2)

def get_productos_by_ids(connection, ids_list):
    """Obtiene detalles de productos/servicios basados en una lista de IDs, incluyendo el costo."""
    cursor = None
    valid_ids = [int(id_str) for id_str in ids_list if id_str and id_str.isdigit() and int(id_str) > 0]
    if not valid_ids:
        return []
    try:
        placeholders = ', '.join(['%s'] * len(valid_ids))
        # --- CAMBIO: Añadir 'costo' a la selección ---
        query = f"""
            SELECT id_prod, nombre, venta, costo
            FROM productos_servicios
            WHERE id_prod IN ({placeholders})
            ORDER BY nombre ASC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, tuple(valid_ids))
        productos = cursor.fetchall()
        if productos:
            for prod in productos:
                if 'venta' in prod and prod['venta'] is not None:
                    try: prod['venta'] = float(prod['venta'])
                    except (ValueError, TypeError): prod['venta'] = 0.0
                # --- CAMBIO: Formatear también el costo ---
                if 'costo' in prod and prod['costo'] is not None:
                    try: prod['costo'] = float(prod['costo'])
                    except (ValueError, TypeError): prod['costo'] = 0.0
                else:
                    prod['costo'] = 0.0
        return productos if productos else []
    except Error as e:
        print(f"Error obteniendo productos por IDs ({valid_ids}): {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_producto_costo_interno(connection, id_prod):
    """Función auxiliar para obtener solo el costo interno de un producto."""
    cursor = None
    try:
        query = "SELECT costo FROM productos_servicios WHERE id_prod = %s"
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_prod,))
        result = cursor.fetchone()
        if result and result['costo'] is not None:
            return float(result['costo'])
        return 0.00 # Default si no se encuentra o el costo es NULL
    except Error as e:
        print(f"Error obteniendo costo interno para producto ID {id_prod}: {e}")
        return 0.00 # Retornar un default en caso de error
    finally:
        if cursor: cursor.close()

def update_patient_details(connection, patient_data):
    """
    Actualiza los datos demográficos de un paciente existente.
    patient_data es un diccionario que DEBE contener 'id_px' y los campos a actualizar.
    """
    cursor = None
    required_keys = ['id_px'] # Solo se necesita el ID para el WHERE
    if 'id_px' not in patient_data:
        print("Error: Falta 'id_px' para actualizar paciente.")
        return False

    # Columnas que se pueden actualizar (excluyendo id_px, id_dr, fecha de registro original)
    updatable_columns = [
        'comoentero', 'nombre', 'apellidop', 'apellidom', 'nacimiento',
        'direccion', 'estadocivil', 'hijos', 'ocupacion', 'telcasa', 'cel',
        'correo', 'emergencia', 'contacto', 'parentesco'
    ]

    # Construir la cláusula SET dinámicamente solo con los campos que vienen en patient_data
    set_parts = []
    values = []

    for col in updatable_columns:
        if col in patient_data: # Solo incluir si el campo está en los datos a actualizar
            set_parts.append(f"`{col}`=%s")
            values.append(patient_data[col])

    if not set_parts: # No hay nada que actualizar
        print("Advertencia: No se proporcionaron campos para actualizar en update_patient_details.")
        return True # Técnicamente no es un error si no se actualizó nada

    try:
        cursor = connection.cursor()
        set_clause = ", ".join(set_parts)
        query = f"UPDATE datos_personales SET {set_clause} WHERE id_px=%s"
        
        values.append(patient_data['id_px']) # Añadir id_px para el WHERE
        
        print(f"DEBUG DB UPDATE Paciente Query: {query}")
        print(f"DEBUG DB UPDATE Paciente Values: {tuple(values)}")

        cursor.execute(query, tuple(values))
        # connection.commit() # Asumiendo autocommit=True o se hace en la ruta
        
        if cursor.rowcount > 0:
            print(f"Datos del paciente ID: {patient_data['id_px']} actualizados exitosamente.")
            return True
        else:
            print(f"No se actualizó ninguna fila para el paciente ID: {patient_data['id_px']} (quizás los datos eran los mismos).")
            return True # O False si quieres que indique que no hubo cambios
            
    except Error as e:
        print(f"Error actualizando datos del paciente ID {patient_data.get('id_px')}: {e}")
        # if connection: connection.rollback() # Si no usas autocommit
        return False
    finally:
        if cursor:
            cursor.close()

def get_productos_servicios_venta(connection):
    """
    Obtiene productos/servicios disponibles para agregar a un recibo.
    (Ej: Todos excepto los de tipo 'Terapia Física Seguimiento').
    Devuelve lista de diccionarios con id_prod, nombre, venta (costo).
    """
    cursor = None
    try:
        # Excluimos adicional=2 (Terapias de Seguimiento) por defecto, ajusta si es necesario
        query = """
            SELECT id_prod, nombre, venta
            FROM productos_servicios
            WHERE adicional != 2 OR adicional IS NULL
            ORDER BY nombre ASC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query)
        productos = cursor.fetchall()
        # Convertir venta a float
        if productos:
            for prod in productos:
                if 'venta' in prod and prod['venta'] is not None:
                    try: prod['venta'] = float(prod['venta'])
                    except (ValueError, TypeError): prod['venta'] = 0.0
        return productos if productos else []
    except Error as e:
        print(f"Error obteniendo productos/servicios para venta: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def save_recibo(connection, datos_recibo, detalles_recibo):
    """
    Guarda un nuevo recibo y sus detalles.
    *** ACTUALIZADO para incluir costo_unitario_compra en recibo_detalle ***
    NO HACE COMMIT NI ROLLBACK.
    """
    cursor = None
    required_recibo = ['id_px', 'id_dr', 'fecha', 'total_neto']
    # --- CAMBIO: 'costo_unitario_compra' no es requerido desde el frontend ---
    required_detalle = ['id_prod', 'cantidad', 'costo_unitario_venta', 'subtotal_linea_neto']

    if not all(key in datos_recibo for key in required_recibo):
        print("Error: Faltan datos requeridos para guardar el recibo principal.")
        return None
    if not isinstance(detalles_recibo, list) or not detalles_recibo:
        print("Error: Se requiere al menos una línea de detalle para guardar el recibo.")
        return None
    if not all(all(key in detalle for key in required_detalle) for detalle in detalles_recibo):
         print("Error: Faltan datos requeridos en una o más líneas de detalle del recibo.")
         return None

    try:
        try:
            fecha_obj = parse_date(datos_recibo.get('fecha'))
            if not fecha_obj:
                 raise ValueError("Fecha vacía o inválida")
            
            # Asegurar explícitamente que sea un string YYYY-MM-DD
            if isinstance(fecha_obj, (date, datetime)):
                fecha_sql_str = fecha_obj.strftime('%Y-%m-%d')
            else:
                fecha_sql_str = str(fecha_obj) # Fallback por si acaso

        except ValueError as e:
            print(f"Error fatal (save_recibo): {e}")
            raise Error(f"La fecha '{datos_recibo.get('fecha')}' tiene un formato inválido.")
        
        cursor = connection.cursor()

        sql_recibo = """
            INSERT INTO recibos
            (id_px, id_dr, fecha, subtotal_bruto, descuento_total, total_neto,
             pago_efectivo, pago_tarjeta, pago_transferencia, pago_otro, pago_otro_desc, notas)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        valores_recibo = (
            datos_recibo['id_px'], datos_recibo['id_dr'], 
            fecha_sql_str,
            datos_recibo.get('subtotal_bruto', 0.0),
            datos_recibo.get('descuento_total', 0.0),
            datos_recibo.get('total_neto', 0.0),
            datos_recibo.get('pago_efectivo', 0.0),
            datos_recibo.get('pago_tarjeta', 0.0),
            datos_recibo.get('pago_transferencia', 0.0),
            datos_recibo.get('pago_otro', 0.0),
            datos_recibo.get('pago_otro_desc'),
            datos_recibo.get('notas')
        )
        cursor.execute(sql_recibo, valores_recibo)
        id_nuevo_recibo = cursor.lastrowid
        print(f"DEBUG DB: Insertado recibo principal con ID: {id_nuevo_recibo}")

        # --- CAMBIO: Modificar INSERT para incluir costo_unitario_compra ---
        sql_detalle = """
            INSERT INTO recibo_detalle
            (id_recibo, id_prod, cantidad, descripcion_prod, 
             costo_unitario_venta, costo_unitario_compra,  -- Nueva columna
             descuento_linea, subtotal_linea_neto)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        valores_detalles_final = []
        for detalle in detalles_recibo:
            # Obtener el costo interno actual del producto
            costo_interno_actual = get_producto_costo_interno(connection, detalle['id_prod'])
            
            valores_detalles_final.append((
                id_nuevo_recibo,
                detalle['id_prod'],
                detalle['cantidad'],
                detalle.get('descripcion_prod'), 
                detalle['costo_unitario_venta'],
                costo_interno_actual, # <-- VALOR PARA LA NUEVA COLUMNA
                detalle.get('descuento_linea', 0.0),
                detalle['subtotal_linea_neto']
            ))

        cursor.executemany(sql_detalle, valores_detalles_final)
        print(f"DEBUG DB: Insertados {len(valores_detalles_final)} detalles para recibo ID: {id_nuevo_recibo}")

        return id_nuevo_recibo
    except Error as e:
        print(f"Error en save_recibo (con costo_unitario_compra): {e}")
        # Considera re-lanzar 'e' si el llamador (main.py) debe manejar el rollback
        # raise e 
        return None
    finally:
        if cursor:
            cursor.close()

def get_recibos_summary(connection, patient_id):
    """Obtiene lista de IDs, fechas y totales netos de recibos para un paciente."""
    cursor = None
    try:
        # ---> Query ACTUALIZADA: Quitar metodo_pago <---
        query = """
            SELECT id_recibo, fecha, total_neto
            FROM recibos
            WHERE id_px = %s
            ORDER BY fecha DESC, id_recibo DESC
        """
        # ----------------------------------------------
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        summary = cursor.fetchall()
        # Convertir decimal a float (sin cambios aquí)
        if summary:
            for recibo in summary:
                 if 'fecha' in recibo and isinstance(recibo['fecha'], date):
                    recibo['fecha'] = recibo['fecha'].strftime('%d/%m/%Y')

                 if 'total_neto' in recibo and recibo['total_neto'] is not None:
                     try: recibo['total_neto'] = float(recibo['total_neto'])
                     except (ValueError, TypeError): recibo['total_neto'] = 0.0
        return summary if summary else []
    except Error as e:
        print(f"Error obteniendo resumen de recibos: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_specific_recibo(connection, id_recibo):
    """Obtiene los datos completos de un recibo y sus detalles.
       *** ACTUALIZADO para usar nuevas columnas de pago ***
    """
    cursor = None
    recibo_completo = None
    try:
        # 1. Obtener datos del recibo principal (Query ACTUALIZADA)
        query_recibo = """
            SELECT r.id_recibo, r.id_px, r.id_dr, r.fecha,
                   r.subtotal_bruto, r.descuento_total, r.total_neto,
                   r.pago_efectivo, r.pago_tarjeta, r.pago_transferencia, -- <-- Nuevos campos
                   r.pago_otro, r.pago_otro_desc,                     -- <-- Nuevos campos
                   r.notas, r.fecha_registro,
                   dr.nombre as nombre_doctor
            FROM recibos r
            LEFT JOIN dr ON r.id_dr = dr.id_dr
            WHERE r.id_recibo = %s
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query_recibo, (id_recibo,))
        recibo_principal = cursor.fetchone()

        if not recibo_principal:
            return None

        # Convertir decimales a float (Añadir nuevos campos de pago)
        for key in ['subtotal_bruto', 'descuento_total', 'total_neto',
                    'pago_efectivo', 'pago_tarjeta', 'pago_transferencia', 'pago_otro']:
             if key in recibo_principal and recibo_principal[key] is not None:
                 try: recibo_principal[key] = float(recibo_principal[key])
                 except (ValueError, TypeError): recibo_principal[key] = 0.0

        # 2. Obtener los detalles del recibo (SIN CAMBIOS aquí)
        query_detalles = """
            SELECT rd.id_detalle, rd.id_recibo, rd.id_prod, rd.cantidad,
                   rd.descripcion_prod, rd.costo_unitario_venta, rd.descuento_linea,
                   rd.subtotal_linea_neto, ps.nombre as nombre_producto
            FROM recibo_detalle rd
            LEFT JOIN productos_servicios ps ON rd.id_prod = ps.id_prod
            WHERE rd.id_recibo = %s
            ORDER BY rd.id_detalle ASC
        """
        cursor.execute(query_detalles, (id_recibo,))
        detalles = cursor.fetchall()

        # Convertir decimales en detalles (SIN CAMBIOS aquí)
        if detalles:
            for detalle in detalles:
                 for key in ['costo_unitario_venta', 'descuento_linea', 'subtotal_linea_neto']:
                     if key in detalle and detalle[key] is not None:
                          try: detalle[key] = float(detalle[key])
                          except (ValueError, TypeError): detalle[key] = 0.0

        # Combinar principal y detalles
        recibo_completo = recibo_principal
        recibo_completo['detalles'] = detalles if detalles else []

        return recibo_completo

    except Error as e:
        print(f"Error obteniendo recibo específico ID {id_recibo}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_active_plans_for_patient(connection, patient_id):
    """
    Obtiene planes de cuidado para un paciente que podrían considerarse 'activos'
    para vincular un nuevo seguimiento.
    Podríamos definir 'activo' como aquellos con sesiones QP restantes > 0,
    o simplemente mostrar los más recientes. Por ahora, mostramos todos los planes
    ordenados por fecha descendente para que el usuario elija.
    """
    cursor = None
    try:
        query = """
            SELECT id_plan, fecha, pb_diagnostico, visitas_qp, visitas_tf
            FROM plancuidado
            WHERE id_px = %s
            ORDER BY fecha DESC, id_plan DESC
        """
        # Podrías añadir un LIMIT aquí si la lista puede ser muy larga, ej. LIMIT 5
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        plans = cursor.fetchall()

        # Opcional: Calcular sesiones restantes para mostrar en el dropdown
        # Esto requeriría llamar a get_seguimientos_for_plan para cada plan,
        # lo cual puede ser costoso si hay muchos planes.
        # Por ahora, solo devolvemos la info básica del plan.
        # Si decides calcularlo, necesitarías pasar 'connection' a esta lógica
        # o hacer una función separada que enriquezca 'plans'.

        return plans if plans else []
    except Error as e:
        print(f"Error obteniendo planes de cuidado activos para paciente {patient_id}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_seguimientos_for_plan(connection, id_plan_cuidado):
    """
    Obtiene todos los registros de seguimiento vinculados a un id_plan_cuidado específico,
    ordenados por fecha ascendente.
    """
    cursor = None
    try:
        # Seleccionar campos relevantes para mostrar el progreso del plan
        query = """
            SELECT id_seguimiento, id_px, fecha, terapia
            FROM quiropractico
            WHERE id_plan_cuidado_asociado = %s
            ORDER BY fecha ASC, id_seguimiento ASC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_plan_cuidado,))
        seguimientos_del_plan = cursor.fetchall()
        return seguimientos_del_plan if seguimientos_del_plan else []
    except Error as e:
        print(f"Error obteniendo seguimientos para plan ID {id_plan_cuidado}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_all_productos_servicios(connection, include_inactive=True): # Nuevo parámetro
    """Obtiene todos los productos y servicios, opcionalmente filtrando por activos."""
    cursor = None
    try:
        query = "SELECT id_prod, nombre, costo, venta, adicional, esta_activo FROM productos_servicios"
        if not include_inactive:
            query += " WHERE esta_activo = 1" # Solo activos
        query += " ORDER BY adicional ASC, nombre ASC" 
        
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query)
        productos = cursor.fetchall()
        if productos:
            for prod in productos:
                for key in ['costo', 'venta']:
                    if key in prod and prod[key] is not None:
                        try: prod[key] = float(prod[key])
                        except (ValueError, TypeError): prod[key] = 0.0
                # Convertir esta_activo a booleano para la lógica
                prod['esta_activo'] = bool(prod.get('esta_activo', 0))
        return productos if productos else []
    except Error as e:
        print(f"Error obteniendo productos/servicios: {e}")
        return []
    finally:
        if cursor: cursor.close()

def get_producto_servicio_by_id(connection, id_prod):
    """Obtiene un producto/servicio específico por su ID, incluyendo su estado activo."""
    cursor = None
    try:
        query = "SELECT id_prod, nombre, costo, venta, adicional, esta_activo FROM productos_servicios WHERE id_prod = %s" # Añadir esta_activo
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_prod,))
        producto = cursor.fetchone()
        if producto:
            for key in ['costo', 'venta']:
                if key in producto and producto[key] is not None:
                    try: producto[key] = float(producto[key])
                    except (ValueError, TypeError): producto[key] = 0.0
            producto['esta_activo'] = bool(producto.get('esta_activo', 0))
        return producto
    except Error as e:
        print(f"Error obteniendo producto/servicio por ID {id_prod}: {e}")
        return None
    finally:
        if cursor: cursor.close()

def add_producto_servicio(connection, data):
    """Añade un nuevo producto/servicio. 'data' es un diccionario.
       'esta_activo' por defecto es 1 (True) si no se especifica.
       NO HACE COMMIT.
    """
    cursor = None
    required_keys = ['nombre', 'venta', 'adicional']
    if not all(key in data for key in required_keys):
        print("Error: Faltan datos requeridos para añadir producto/servicio.")
        return None
    try:
        cursor = connection.cursor()
        query = """
            INSERT INTO productos_servicios (nombre, costo, venta, adicional, esta_activo)
            VALUES (%s, %s, %s, %s, %s)
        """
        values = (
            data['nombre'],
            data.get('costo', 0.00),
            data['venta'],
            data['adicional'],
            int(data.get('esta_activo', 1)) # Default a 1 (activo), convertir a int para DB
        )
        cursor.execute(query, values)
        new_id = cursor.lastrowid
        print(f"Producto/servicio añadido con ID: {new_id}")
        return new_id
    except Error as e:
        print(f"Error añadiendo producto/servicio: {e}")
        return None
    finally:
        if cursor: cursor.close()

def update_producto_servicio(connection, data):
    """Actualiza un producto/servicio existente. 'data' debe incluir 'id_prod'.
       Incluye actualización de 'esta_activo'. NO HACE COMMIT.
    """
    cursor = None
    required_keys = ['id_prod', 'nombre', 'venta', 'adicional'] # esta_activo puede ser opcional en data
    if not all(key in data for key in required_keys):
        print("Error: Faltan datos requeridos para actualizar producto/servicio.")
        return False
    try:
        cursor = connection.cursor()
        query = """
            UPDATE productos_servicios
            SET nombre = %s, costo = %s, venta = %s, adicional = %s, esta_activo = %s
            WHERE id_prod = %s
        """
        values = (
            data['nombre'],
            data.get('costo', 0.00),
            data['venta'],
            data['adicional'],
            int(data.get('esta_activo', 1)), # Default a activo si no se especifica, convertir a int
            data['id_prod']
        )
        cursor.execute(query, values)
        if cursor.rowcount > 0:
            print(f"Producto/servicio ID {data['id_prod']} actualizado.")
            return True
        print(f"Producto/servicio ID {data['id_prod']} no encontrado o datos sin cambios.")
        return False
    except Error as e:
        print(f"Error actualizando producto/servicio ID {data.get('id_prod')}: {e}")
        return False
    finally:
        if cursor: cursor.close()

# Renombrar y cambiar lógica de delete_producto_servicio
def set_producto_servicio_active_status(connection, id_prod, status):
    """Cambia el estado 'esta_activo' de un producto/servicio.
       status debe ser True (activo) o False (inactivo). NO HACE COMMIT.
    """
    cursor = None
    try:
        cursor = connection.cursor()
        query = "UPDATE productos_servicios SET esta_activo = %s WHERE id_prod = %s"
        # Convertir booleano a 0 o 1 para la base de datos
        db_status = 1 if status else 0
        cursor.execute(query, (db_status, id_prod))
        if cursor.rowcount > 0:
            action = "habilitado" if status else "deshabilitado"
            print(f"Producto/servicio ID {id_prod} {action}.")
            return True
        print(f"Producto/servicio ID {id_prod} no encontrado.")
        return False
    except Error as e:
        print(f"Error cambiando estado de producto/servicio ID {id_prod}: {e}")
        return False
    finally:
        if cursor: cursor.close()

# Funciones que deben filtrar por esta_activo = 1
def get_productos_servicios_venta(connection):
    """
    Obtiene productos/servicios ACTIVOS disponibles para agregar a un recibo.
    Devuelve id_prod, nombre, venta (precio al público), y costo (interno).
    """
    cursor = None
    try:
        # --- CAMBIO: Añadir 'costo' a la selección ---
        query = """
            SELECT id_prod, nombre, venta, costo 
            FROM productos_servicios
            WHERE (adicional != 2 OR adicional IS NULL) AND esta_activo = 1
            ORDER BY nombre ASC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query)
        productos = cursor.fetchall()
        if productos:
            for prod in productos:
                if 'venta' in prod and prod['venta'] is not None:
                    try: prod['venta'] = float(prod['venta'])
                    except (ValueError, TypeError): prod['venta'] = 0.0
                # --- CAMBIO: Formatear también el costo ---
                if 'costo' in prod and prod['costo'] is not None:
                    try: prod['costo'] = float(prod['costo'])
                    except (ValueError, TypeError): prod['costo'] = 0.0
                else: # Si el costo es NULL en la BD, asignarle 0.0
                    prod['costo'] = 0.0
        return productos if productos else []
    except Error as e:
        print(f"Error obteniendo productos/servicios activos para venta: {e}")
        return []
    finally:
        if cursor: cursor.close()


def search_productos_servicios(connection, search_term):
    """ Busca productos/servicios ACTIVOS por nombre para autocompletado. """
    cursor = None
    try:
        search_pattern = f"%{search_term}%"
        query = """
            SELECT id_prod, nombre, venta
            FROM productos_servicios
            WHERE (adicional != 2 OR adicional IS NULL) AND nombre LIKE %s AND esta_activo = 1 -- <-- SOLO ACTIVOS
            ORDER BY nombre ASC
            LIMIT 10
        """
        # ... (resto de la función como antes) ...
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (search_pattern,))
        productos = cursor.fetchall()
        if productos:
            for prod in productos:
                if 'venta' in prod and prod['venta'] is not None:
                    try: prod['venta'] = float(prod['venta'])
                    except (ValueError, TypeError): prod['venta'] = 0.0
        return productos if productos else []
    except Error as e:
        print(f"Error buscando productos/servicios activos ('{search_term}'): {e}")
        return []
    finally:
        if cursor: cursor.close()

def get_terapias_fisicas(connection): # Las terapias para seguimiento también deben estar activas
    """Obtiene la lista de terapias físicas (adicional=2) ACTIVAS."""
    cursor = None
    try:
        query = "SELECT id_prod, nombre FROM productos_servicios WHERE adicional = 2 AND esta_activo = 1 ORDER BY nombre ASC" # <-- SOLO ACTIVAS
        # ... (resto de la función como antes) ...
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query)
        therapies = cursor.fetchall()
        return therapies if therapies else []
    except Error as e:
        print(f"Error obteniendo terapias físicas activas: {e}")
        return []
    finally:
        if cursor: cursor.close()

def get_all_doctors(connection, include_inactive=True, filter_by_centro_id=None): # Nuevo parámetro
    """
    Obtiene todos los doctores registrados.
    - include_inactive: Si es True, incluye doctores inactivos.
    - filter_by_centro_id: Si se provee un ID de centro, filtra por ese centro.
                         Si es None, no filtra por centro (útil para admin).
    """
    cursor = None
    try:
        query_base = "SELECT id_dr, nombre, usuario, centro, esta_activo FROM dr"
        conditions = []
        params = []

        if not include_inactive:
            conditions.append("esta_activo = 1")
        
        if filter_by_centro_id is not None: # Solo filtrar si se proporciona un ID de centro
            conditions.append("centro = %s")
            params.append(filter_by_centro_id)

        if conditions:
            query_base += " WHERE " + " AND ".join(conditions)
        
        query_base += " ORDER BY nombre ASC"
        
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query_base, tuple(params)) # Pasar la tupla de parámetros
        doctores = cursor.fetchall()

        if doctores:
            for dr in doctores:
                dr['esta_activo'] = bool(dr.get('esta_activo', 0))
                dr['is_admin_role'] = (dr.get('centro') == 0) 
        return doctores if doctores else []
    except Error as e:
        print(f"Error obteniendo doctores: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_doctor_by_id(connection, id_dr):
    """Obtiene un doctor específico por su ID, incluyendo su estado activo."""
    cursor = None
    try:
        # Asegurarse de seleccionar la columna esta_activo
        query = "SELECT id_dr, nombre, usuario, contraseña, centro, esta_activo FROM dr WHERE id_dr = %s"
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_dr,))
        doctor = cursor.fetchone()
        if doctor:
            doctor['esta_activo'] = bool(doctor.get('esta_activo', 0))
            doctor['is_admin_role'] = (doctor.get('centro') == 0)
        return doctor # Devuelve el diccionario del doctor o None si no se encuentra
    except Error as e:
        print(f"Error obteniendo doctor por ID {id_dr}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def update_doctor_details(connection, data):
    """
    Actualiza los detalles de un doctor (nombre, usuario, centro/rol, esta_activo).
    'data' debe incluir 'id_dr'.
    NO actualiza la contraseña aquí. NO HACE COMMIT.
    """
    cursor = None
    required_keys = ['id_dr', 'nombre', 'usuario'] # 'centro' y 'esta_activo' pueden ser opcionales
    if 'id_dr' not in data:
        print("Error: Falta 'id_dr' para actualizar doctor.")
        return False

    # Columnas que se pueden actualizar
    updatable_columns = ['nombre', 'usuario', 'centro', 'esta_activo']
    set_parts = []
    values = []

    for col in updatable_columns:
        if col in data: # Solo incluir si el campo está en los datos a actualizar
            set_parts.append(f"`{col}`=%s")
            # Convertir bool a int para esta_activo
            value_to_add = int(data[col]) if isinstance(data[col], bool) and col == 'esta_activo' else data[col]
            values.append(value_to_add)

    if not set_parts:
        print("Advertencia: No se proporcionaron campos para actualizar en update_doctor_details.")
        return True # No es error si no hay nada que actualizar

    try:
        cursor = connection.cursor()
        set_clause = ", ".join(set_parts)
        query = f"UPDATE dr SET {set_clause} WHERE id_dr=%s"
        values.append(data['id_dr']) # Añadir id_dr para el WHERE
        
        print(f"DEBUG DB UPDATE Doctor Query: {query}")
        print(f"DEBUG DB UPDATE Doctor Values: {tuple(values)}")
        
        cursor.execute(query, tuple(values))
        if cursor.rowcount > 0:
            print(f"Detalles del doctor ID {data['id_dr']} actualizados.")
            return True
        print(f"Doctor ID {data['id_dr']} no encontrado o datos sin cambios.")
        return True # Considerar True si no hubo error, aunque no haya filas afectadas
    except Error as e:
        print(f"Error actualizando detalles del doctor ID {data.get('id_dr')}: {e}")
        # Manejo de error de duplicidad de usuario (código 1062)
        if e.errno == 1062: # Duplicate entry
            raise ValueError(f"El nombre de usuario '{data.get('usuario')}' ya está en uso.")
        return False
    finally:
        if cursor:
            cursor.close()

def update_doctor_password(connection, id_dr, new_password_plain):
    """
    Actualiza la contraseña de un doctor. La nueva contraseña se hashea.
    NO HACE COMMIT.
    """
    cursor = None
    if not new_password_plain:
        print("Error: La nueva contraseña no puede estar vacía.")
        return False
    try:
        cursor = connection.cursor()
        hashed_password = generate_password_hash(new_password_plain, method='pbkdf2:sha256')
        query = "UPDATE dr SET contraseña = %s WHERE id_dr = %s"
        cursor.execute(query, (hashed_password, id_dr))
        if cursor.rowcount > 0:
            print(f"Contraseña del doctor ID {id_dr} actualizada.")
            return True
        print(f"Doctor ID {id_dr} no encontrado para actualizar contraseña.")
        return False
    except Error as e:
        print(f"Error actualizando contraseña del doctor ID {id_dr}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()

def set_doctor_active_status(connection, id_dr, status):
    """
    Cambia el estado 'esta_activo' de un doctor.
    status debe ser True (activo) o False (inactivo). NO HACE COMMIT.
    """
    cursor = None
    try:
        cursor = connection.cursor()
        query = "UPDATE dr SET esta_activo = %s WHERE id_dr = %s"
        db_status = 1 if status else 0 # Convertir booleano a int
        cursor.execute(query, (db_status, id_dr))
        if cursor.rowcount > 0:
            action = "habilitado" if status else "deshabilitado"
            print(f"Doctor ID {id_dr} {action}.")
            return True
        print(f"Doctor ID {id_dr} no encontrado para cambiar estado.")
        return False
    except Error as e:
        print(f"Error cambiando estado del doctor ID {id_dr}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()

def count_total_pacientes(connection):
    cursor = None
    try:
        query = "SELECT COUNT(*) as total_pacientes FROM datos_personales"
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query)
        result = cursor.fetchone()
        return result['total_pacientes'] if result and 'total_pacientes' in result else 0
    except Error as e:
        print(f"Error contando pacientes: {e}")
        return 0
    finally:
        if cursor:
            cursor.close()

def count_total_doctores(connection):
    cursor = None
    try:
        query = "SELECT COUNT(*) as total_doctores FROM dr"
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query)
        result = cursor.fetchone()
        return result['total_doctores'] if result and 'total_doctores' in result else 0
    except Error as e:
        print(f"Error contando doctores: {e}")
        return 0
    finally:
        if cursor:
            cursor.close()

# Si estás usando count_seguimientos_hoy, añade un print similar allí también
def count_seguimientos_hoy(connection, fecha_hoy_str_ddmmyyyy):
    cursor = None
    try:
        query = "SELECT COUNT(*) as total_seguimientos_hoy FROM quiropractico WHERE fecha = %s"
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (fecha_hoy_str_ddmmyyyy,))
        result = cursor.fetchone()
        return result['total_seguimientos_hoy'] if result and 'total_seguimientos_hoy' in result else 0
    except Error as e:
        print(f"Error contando seguimientos de hoy: {e}")
        return 0
    finally:
        if cursor:
            cursor.close()


def get_all_centros(connection):
    """Obtiene todos los centros/clínicas registrados."""
    cursor = None
    try:
        query = "SELECT id_centro, nombre, direccion, cel, tel FROM centro ORDER BY nombre ASC"
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query)
        centros = cursor.fetchall()
        return centros if centros else []
    except Error as e:
        print(f"Error obteniendo todos los centros: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_centro_by_id(connection, id_centro):
    """Obtiene un centro/clínica específico por su ID."""
    cursor = None
    try:
        query = "SELECT id_centro, nombre, direccion, cel, tel FROM centro WHERE id_centro = %s"
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_centro,))
        centro = cursor.fetchone()
        return centro
    except Error as e:
        print(f"Error obteniendo centro por ID {id_centro}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def add_centro(connection, data):
    """Añade un nuevo centro/clínica. 'data' es un diccionario. NO HACE COMMIT."""
    cursor = None
    required_keys = ['nombre'] # Mínimo requerido
    if not all(key in data for key in required_keys):
        print("Error: Falta 'nombre' para añadir centro.")
        return None
    try:
        cursor = connection.cursor()
        query = """
            INSERT INTO centro (nombre, direccion, cel, tel)
            VALUES (%s, %s, %s, %s)
        """
        values = (
            data['nombre'],
            data.get('direccion'), # .get() para campos opcionales
            data.get('cel'),
            data.get('tel')
        )
        cursor.execute(query, values)
        new_id = cursor.lastrowid
        print(f"Centro añadido con ID: {new_id}")
        return new_id
    except Error as e:
        print(f"Error añadiendo centro: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def update_centro(connection, data):
    """Actualiza un centro/clínica existente. 'data' debe incluir 'id_centro'. NO HACE COMMIT."""
    cursor = None
    required_keys = ['id_centro', 'nombre']
    if not all(key in data for key in required_keys):
        print("Error: Faltan datos ('id_centro', 'nombre') para actualizar centro.")
        return False
    try:
        cursor = connection.cursor()
        query = """
            UPDATE centro
            SET nombre = %s, direccion = %s, cel = %s, tel = %s
            WHERE id_centro = %s
        """
        values = (
            data['nombre'],
            data.get('direccion'),
            data.get('cel'),
            data.get('tel'),
            data['id_centro']
        )
        cursor.execute(query, values)
        if cursor.rowcount > 0:
            print(f"Centro ID {data['id_centro']} actualizado.")
            return True
        print(f"Centro ID {data['id_centro']} no encontrado o datos sin cambios.")
        return False # O True si no hubo error pero no se modificó
    except Error as e:
        print(f"Error actualizando centro ID {data.get('id_centro')}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()

def get_ingresos_por_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id=None):
    """
    Calcula los ingresos totales agrupados por día, mes o año según el rango de fechas.
    Las fechas de entrada deben estar en formato 'YYYY-MM-DD'.
    """
    cursor = None
    resultados = []
    try:
        # Convertir fechas de entrada a objetos datetime para calcular la diferencia
        fecha_inicio_dt = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        fecha_fin_dt = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        diferencia_dias = (fecha_fin_dt - fecha_inicio_dt).days

        # Determinar el nivel de agrupación
        group_by_format_sql = ""
        group_by_format_python = ""
        select_date_column = ""
        order_by_clause = ""

        # --- Lógica de agrupación por fecha (simplificada) ---
        if diferencia_dias <= 45: # Agrupar por día
            select_date_column = "fecha AS periodo"
            group_by_format_sql = "fecha"
            group_by_format_python = "%Y-%m-%d" # El tipo DATE de MySQL se devuelve así
            order_by_clause = "fecha ASC"
        elif diferencia_dias <= 365 * 2: # Agrupar por mes
            select_date_column = "DATE_FORMAT(fecha, '%Y-%m') AS periodo"
            group_by_format_sql = "periodo"
            group_by_format_python = "%Y-%m"
            order_by_clause = "periodo ASC"
        else: # Agrupar por año
            select_date_column = "YEAR(fecha) AS periodo"
            group_by_format_sql = "periodo"
            group_by_format_python = "%Y"
            order_by_clause = "periodo ASC"

        params = [fecha_inicio_str, fecha_fin_str]
        filtro_doctor = ""
        if doctor_id:
            filtro_doctor = "AND id_dr = %s "
            params.append(doctor_id)

        query = f"""
            SELECT 
                {select_date_column}, 
                SUM(total_neto) AS total_ingresos_periodo,
                COUNT(id_recibo) AS numero_recibos
            FROM recibos
            WHERE fecha BETWEEN %s AND %s 
            {filtro_doctor}
            GROUP BY {group_by_format_sql}
            ORDER BY {order_by_clause};
        """
        
        cursor = connection.cursor(dictionary=True)
        print(f"Query Reporte Ingresos: {query}")
        print(f"Params: {tuple(params)}")
        
        cursor.execute(query, tuple(params))
        resultados = cursor.fetchall()

        for res in resultados:
            res['total_ingresos_periodo'] = float(res.get('total_ingresos_periodo', 0.0) or 0.0)
            
            # --- CORRECCIÓN de formato de periodo ---
            if isinstance(res['periodo'], date):
                # Si es un objeto 'date' (agrupado por día), formatearlo
                res['periodo'] = res['periodo'].strftime('%d/%m/%Y')
            else:
                # Si es string ('YYYY-MM') o int (YYYY), convertir a string
                res['periodo'] = str(res['periodo'])
            
            res['formato_periodo_python'] = group_by_format_python

        return resultados
    except ValueError as ve:
        print(f"Error de formato de fecha en get_ingresos_por_periodo: {ve}")
        return []
    except Error as e:
        print(f"Error en get_ingresos_por_periodo: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_ingresos_por_doctor_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id=None):
    """
    Calcula los ingresos totales generados por cada doctor en un periodo específico.
    Si se provee un doctor_id, filtra solo para ese doctor.
    """
    cursor = None
    try:
        params = [fecha_inicio_str, fecha_fin_str]
        filtro_doctor = ""
        if doctor_id:
            filtro_doctor = "AND r.id_dr = %s "
            params.append(doctor_id)

        query = f"""
            SELECT 
                d.id_dr,
                d.nombre AS nombre_doctor,
                SUM(r.total_neto) AS total_ingresos_doctor,
                COUNT(r.id_recibo) AS numero_recibos_doctor
            FROM recibos r
            JOIN dr d ON r.id_dr = d.id_dr
            WHERE r.fecha BETWEEN %s AND %s
            {filtro_doctor}
            GROUP BY d.id_dr, d.nombre
            ORDER BY total_ingresos_doctor DESC, d.nombre ASC;
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        resultados = cursor.fetchall()

        for res in resultados:
            res['total_ingresos_doctor'] = float(res.get('total_ingresos_doctor', 0.0) or 0.0)
        
        return resultados
    except ValueError as ve:
        print(f"Error de formato de fecha en get_ingresos_por_doctor_periodo: {ve}")
        return []
    except Error as e:
        print(f"Error en get_ingresos_por_doctor_periodo: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
            
def get_utilidad_estimada_por_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id=None):
    """
    Calcula la utilidad estimada total agrupada por día, mes o año.
    Si se provee un doctor_id, filtra para ese doctor.
    """
    cursor = None
    try:
        fecha_inicio_dt = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        fecha_fin_dt = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        diferencia_dias = (fecha_fin_dt - fecha_inicio_dt).days

        group_by_format_sql = ""
        group_by_format_python = ""
        select_date_column = ""
        order_by_clause = ""
        
        if diferencia_dias <= 45: # Agrupar por día
            select_date_column = "r.fecha AS periodo"
            group_by_format_sql = "r.fecha"
            group_by_format_python = "%Y-%m-%d"
            order_by_clause = "r.fecha ASC"
        elif diferencia_dias <= 365 * 2: # Agrupar por mes
            select_date_column = "DATE_FORMAT(r.fecha, '%Y-%m') AS periodo"
            group_by_format_sql = "periodo"
            group_by_format_python = "%Y-%m"
            order_by_clause = "periodo ASC"
        else: # Agrupar por año
            select_date_column = "YEAR(r.fecha) AS periodo"
            group_by_format_sql = "periodo"
            group_by_format_python = "%Y"
            order_by_clause = "periodo ASC"

        params = [fecha_inicio_str, fecha_fin_str]
        filtro_doctor = ""
        if doctor_id:
            filtro_doctor = "AND r.id_dr = %s "
            params.append(doctor_id)

        query = f"""
            SELECT 
                {select_date_column},
                SUM(
                    (rd.cantidad * rd.costo_unitario_venta - IFNULL(rd.descuento_linea, 0)) 
                    - 
                    (rd.cantidad * IFNULL(rd.costo_unitario_compra, 0))
                ) AS total_utilidad_estimada_periodo,
                COUNT(DISTINCT r.id_recibo) AS numero_recibos_con_utilidad,
                SUM(r.total_neto) AS total_ingresos_netos_periodo
            FROM recibos r
            JOIN recibo_detalle rd ON r.id_recibo = rd.id_recibo
            WHERE r.fecha BETWEEN %s AND %s
            {filtro_doctor}
            GROUP BY {group_by_format_sql}
            ORDER BY {order_by_clause};
        """
        
        cursor = connection.cursor(dictionary=True)
        print(f"Query Reporte Utilidad Periodo: {query}")
        print(f"Params: {tuple(params)}")
        
        cursor.execute(query, tuple(params))
        resultados = cursor.fetchall()

        for res in resultados:
            res['total_utilidad_estimada_periodo'] = float(res.get('total_utilidad_estimada_periodo', 0.0) or 0.0)
            res['total_ingresos_netos_periodo'] = float(res.get('total_ingresos_netos_periodo', 0.0) or 0.0)
            
            if isinstance(res['periodo'], date):
                res['periodo'] = res['periodo'].strftime('%d/%m/%Y')
            else:
                res['periodo'] = str(res['periodo'])
            
            res['formato_periodo_python'] = group_by_format_python
        
        return resultados
    except ValueError as ve:
        print(f"Error de formato de fecha en get_utilidad_estimada_por_periodo: {ve}")
        return []
    except Error as e:
        print(f"Error en get_utilidad_estimada_por_periodo: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_utilidad_estimada_por_doctor_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id=None):
    """
    Calcula la utilidad estimada generada por cada doctor en un periodo específico.
    Si se provee un doctor_id, filtra solo para ese doctor.
    """
    cursor = None
    try:
        params = [fecha_inicio_str, fecha_fin_str]
        filtro_doctor = ""
        if doctor_id:
            filtro_doctor = "AND r.id_dr = %s "
            params.append(doctor_id)

        query = f"""
            SELECT 
                dr.id_dr,
                dr.nombre AS nombre_doctor,
                SUM(
                    (rd.cantidad * rd.costo_unitario_venta - IFNULL(rd.descuento_linea, 0)) 
                    - 
                    (rd.cantidad * IFNULL(rd.costo_unitario_compra, 0))
                ) AS total_utilidad_estimada_doctor,
                COUNT(DISTINCT r.id_recibo) AS numero_recibos_doctor,
                SUM(r.total_neto) AS total_ingresos_netos_doctor
            FROM recibos r
            JOIN recibo_detalle rd ON r.id_recibo = rd.id_recibo
            JOIN dr ON r.id_dr = dr.id_dr 
            WHERE r.fecha BETWEEN %s AND %s
            {filtro_doctor}
            GROUP BY dr.id_dr, dr.nombre
            ORDER BY total_utilidad_estimada_doctor DESC, dr.nombre ASC;
        """
        cursor = connection.cursor(dictionary=True)
        print(f"Query Reporte Utilidad Doctor: {query}")
        print(f"Params: {tuple(params)}")

        cursor.execute(query, tuple(params))
        resultados = cursor.fetchall()

        for res in resultados:
            res['total_utilidad_estimada_doctor'] = float(res.get('total_utilidad_estimada_doctor', 0.0) or 0.0)
            res['total_ingresos_netos_doctor'] = float(res.get('total_ingresos_netos_doctor', 0.0) or 0.0)
        
        return resultados
    except ValueError as ve:
        print(f"Error de formato de fecha en get_utilidad_estimada_por_doctor_periodo: {ve}")
        return []
    except Error as e:
        print(f"Error en get_utilidad_estimada_por_doctor_periodo: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_pacientes_nuevos_por_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id=0):
    """
    Obtiene la lista de pacientes nuevos y el conteo agrupado.
    Si doctor_id no es 0, filtra por el doctor que los registró.
    """
    cursor = None
    pacientes_nuevos_lista = []
    conteo_agrupado_para_grafica = []
    try:
        fecha_inicio_dt = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        fecha_fin_dt = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        diferencia_dias = (fecha_fin_dt - fecha_inicio_dt).days

        # --- CORRECCIÓN: Lógica de filtro por Doctor ---
        params_lista = [fecha_inicio_str, fecha_fin_str]
        filtro_doctor_sql = ""
        if doctor_id != 0:
            filtro_doctor_sql = "AND id_dr = %s "
            params_lista.append(doctor_id)
        
        # 1. Obtener la lista detallada
        query_lista = f"""
            SELECT id_px, nombre, apellidop, apellidom, fecha AS fecha_registro
            FROM datos_personales
            WHERE fecha BETWEEN %s AND %s
            {filtro_doctor_sql}
            ORDER BY fecha ASC, id_px ASC;
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query_lista, tuple(params_lista))
        pacientes_nuevos_lista = cursor.fetchall()

        # 2. Determinar agrupación para la gráfica
        group_by_format_sql_db = "" 
        group_by_format_python_label = ""
        select_periodo_grafica = ""
        order_by_clause_grafica = ""

        if diferencia_dias <= 45: # Agrupar por día
            select_periodo_grafica = "fecha AS periodo_grafica"
            group_by_format_sql_db = "fecha"
            group_by_format_python_label = "%d %b %Y" # ej: 01 May 2024
            order_by_clause_grafica = "fecha ASC"
        elif diferencia_dias <= 365 * 2: # Agrupar por mes
            select_periodo_grafica = "DATE_FORMAT(fecha, '%Y-%m') AS periodo_grafica"
            group_by_format_sql_db = "periodo_grafica" 
            group_by_format_python_label = "%b %Y" # ej: May 2024
            order_by_clause_grafica = "periodo_grafica ASC"
        else: # Agrupar por año
            select_periodo_grafica = "YEAR(fecha) AS periodo_grafica"
            group_by_format_sql_db = "periodo_grafica"
            group_by_format_python_label = "%Y" # ej: 2024
            order_by_clause_grafica = "periodo_grafica ASC"
        
        # 3. Obtener datos para la gráfica
        # Los parámetros son los mismos que para la lista
        params_grafica = params_lista 
        
        query_grafica = f"""
            SELECT 
                {select_periodo_grafica},
                COUNT(id_px) AS conteo_pacientes_nuevos
            FROM datos_personales
            WHERE fecha BETWEEN %s AND %s
            {filtro_doctor_sql}
            GROUP BY {group_by_format_sql_db}
            ORDER BY {order_by_clause_grafica};
        """
        
        print(f"Query Reporte Pacientes Nuevos (Gráfica): {query_grafica}")
        print(f"Params (Gráfica): {tuple(params_grafica)}")

        cursor.execute(query_grafica, tuple(params_grafica))
        conteo_agrupado_para_grafica_raw = cursor.fetchall()

        # --- CORRECCIÓN: Formatear etiquetas basado en el TIPO de dato devuelto ---
        for item in conteo_agrupado_para_grafica_raw:
            periodo_label_raw = item.get('periodo_grafica')
            label_para_grafica = "Error Etiqueta"
            
            if isinstance(periodo_label_raw, date): 
                # Agrupado por día, la BD devuelve un objeto date
                label_para_grafica = periodo_label_raw.strftime('%d %b %Y')
            elif isinstance(periodo_label_raw, str): 
                # Agrupado por mes ('YYYY-MM')
                try:
                    label_para_grafica = datetime.strptime(periodo_label_raw, '%Y-%m').strftime('%b %Y')
                except (ValueError, TypeError):
                    label_para_grafica = periodo_label_raw
            elif isinstance(periodo_label_raw, int): 
                # Agrupado por año (YYYY)
                label_para_grafica = str(periodo_label_raw)
            else:
                label_para_grafica = str(periodo_label_raw) # Fallback
            
            conteo_agrupado_para_grafica.append({
                'periodo_label': label_para_grafica,
                'conteo': item.get('conteo_pacientes_nuevos', 0)
            })
        
        return pacientes_nuevos_lista, conteo_agrupado_para_grafica

    except ValueError as ve:
        print(f"Error de formato de fecha en get_pacientes_nuevos_por_periodo: {ve}")
        return [], []
    except Error as e:
        print(f"Error en get_pacientes_nuevos_por_periodo: {e}")
        return [], []
    finally:
        if cursor:
            cursor.close()

def get_pacientes_mas_frecuentes(connection, fecha_inicio_str, fecha_fin_str, limit=10):
    """
    Obtiene los N pacientes más frecuentes basados en seguimientos
    dentro de un periodo específico.
    """
    cursor = None
    try:
        fecha_inicio_db = to_db_str(fecha_inicio_str)
        fecha_fin_db = to_db_str(fecha_fin_str)
        
        query = """
            SELECT 
                dp.id_px,
                dp.nombre,
                dp.apellidop,
                dp.apellidom,
                COUNT(q.id_seguimiento) AS numero_seguimientos
            FROM datos_personales dp
            JOIN quiropractico q ON dp.id_px = q.id_px
            WHERE q.fecha BETWEEN %s AND %s
            GROUP BY dp.id_px, dp.nombre, dp.apellidop, dp.apellidom
            ORDER BY numero_seguimientos DESC, dp.apellidop ASC, dp.nombre ASC
            LIMIT %s;
        """
        cursor = connection.cursor(dictionary=True)
        print(f"Query Reporte Pacientes Frecuentes: {query}")
        print(f"Params: {fecha_inicio_db}, {fecha_fin_db}, {limit}")
        
        cursor.execute(query, (fecha_inicio_db, fecha_fin_db, limit))
        resultados = cursor.fetchall()
        
        return resultados
    except ValueError as ve:
        print(f"Error de formato de fecha en get_pacientes_mas_frecuentes: {ve}")
        return []
    except Error as e:
        print(f"Error en get_pacientes_mas_frecuentes: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_seguimientos_por_doctor_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id=0):
    """
    Cuenta el número de seguimientos realizados por cada doctor.
    Si doctor_id no es 0, filtra para ese doctor.
    """
    cursor = None
    try:
        params = [fecha_inicio_str, fecha_fin_str]
        filtro_doctor_sql = ""
        if doctor_id != 0:
            filtro_doctor_sql = "AND q.id_dr = %s "
            params.append(doctor_id)

        query = f"""
            SELECT 
                d.id_dr,
                d.nombre AS nombre_doctor,
                COUNT(q.id_seguimiento) AS numero_consultas
            FROM quiropractico q
            JOIN dr d ON q.id_dr = d.id_dr
            WHERE q.fecha BETWEEN %s AND %s
            {filtro_doctor_sql}
            GROUP BY d.id_dr, d.nombre
            ORDER BY numero_consultas DESC, d.nombre ASC;
        """
        cursor = connection.cursor(dictionary=True)
        print(f"Query Reporte Consultas por Doctor: {query}")
        print(f"Params: {tuple(params)}")
        
        cursor.execute(query, tuple(params))
        resultados = cursor.fetchall()
        
        return resultados
    except ValueError as ve:
        print(f"Error de formato de fecha en get_seguimientos_por_doctor_periodo: {ve}")
        return []
    except Error as e:
        print(f"Error en get_seguimientos_por_doctor_periodo: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_uso_planes_de_cuidado(connection, fecha_inicio_str, fecha_fin_str):
    """
    Analiza los planes de cuidado creados dentro de un rango de fechas
    y determina su estado (Activo o Completado).
    """
    cursor = None
    planes_analizados = []
    try:
        # 1. Obtener los planes creados en el periodo
        query_planes = """
            SELECT 
                pc.id_plan, 
                pc.id_px,
                dp.nombre AS nombre_paciente,
                dp.apellidop AS apellidop_paciente,
                dp.apellidom AS apellidom_paciente,
                pc.fecha AS fecha_creacion_plan, 
                pc.pb_diagnostico,
                pc.visitas_qp AS visitas_qp_planificadas,
                dr.nombre AS nombre_doctor_plan
            FROM plancuidado pc
            JOIN datos_personales dp ON pc.id_px = dp.id_px
            LEFT JOIN dr ON pc.id_dr = dr.id_dr
            WHERE pc.fecha BETWEEN %s AND %s
            ORDER BY pc.fecha DESC, pc.id_plan DESC;
        """
        cursor = connection.cursor(dictionary=True, buffered=True) # buffered para reutilizar
        print(f"Query Uso Planes (Planes Creados): {query_planes}")
        print(f"Params: {fecha_inicio_str}, {fecha_fin_str}")
        cursor.execute(query_planes, (fecha_inicio_str, fecha_fin_str))
        planes_creados = cursor.fetchall()

        if not planes_creados:
            return {
                'total_creados': 0,
                'activos': 0,
                'completados': 0,
                'lista_detallada_planes': []
            }

        # 2. Para cada plan, contar los seguimientos asociados
        query_conteo_seguimientos = """
            SELECT COUNT(id_seguimiento) as conteo
            FROM quiropractico
            WHERE id_plan_cuidado_asociado = %s;
        """
        
        planes_activos = 0
        planes_completados = 0

        for plan in planes_creados:
            cursor.execute(query_conteo_seguimientos, (plan['id_plan'],))
            resultado_conteo = cursor.fetchone()
            visitas_qp_realizadas = resultado_conteo['conteo'] if resultado_conteo else 0
            
            plan['visitas_qp_realizadas'] = visitas_qp_realizadas
            visitas_planificadas = plan.get('visitas_qp_planificadas') or 0

            if visitas_qp_realizadas >= visitas_planificadas:
                plan['estado_plan'] = 'Completado'
                planes_completados += 1
            else:
                plan['estado_plan'] = 'Activo'
                planes_activos += 1
            
            plan['nombre_completo_paciente'] = f"{plan.get('nombre_paciente','')} {plan.get('apellidop_paciente','')} {plan.get('apellidom_paciente','').strip()}".strip()

        return {
            'total_creados': len(planes_creados),
            'activos': planes_activos,
            'completados': planes_completados,
            'lista_detallada_planes': planes_creados 
        }

    except ValueError as ve:
        print(f"Error de formato de fecha en get_uso_planes_de_cuidado: {ve}")
        return {'total_creados': 0, 'activos': 0, 'completados': 0, 'lista_detallada_planes': []}
    except Error as e:
        print(f"Error en get_uso_planes_de_cuidado: {e}")
        return {'total_creados': 0, 'activos': 0, 'completados': 0, 'lista_detallada_planes': []}
    finally:
        if cursor:
            cursor.close()

def get_historial_compras_paciente(connection, id_px):
    """
    Obtiene un historial de todos los ítems comprados por un paciente,
    ordenados por la fecha del recibo.
    """
    cursor = None
    try:
        query = """
            SELECT 
                r.fecha AS fecha_recibo,
                r.id_recibo,
                rd.id_detalle,
                rd.id_prod,
                COALESCE(rd.descripcion_prod, ps.nombre, 'Producto Desconocido') AS descripcion_item,
                rd.cantidad,
                rd.costo_unitario_venta,
                rd.descuento_linea,
                rd.subtotal_linea_neto
            FROM recibo_detalle rd
            JOIN recibos r ON rd.id_recibo = r.id_recibo
            LEFT JOIN productos_servicios ps ON rd.id_prod = ps.id_prod
            WHERE r.id_px = %s
            ORDER BY r.fecha DESC, r.id_recibo DESC, rd.id_detalle ASC;
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (id_px,))
        historial = cursor.fetchall()
        
        # Asegurar que los valores numéricos sean floats
        for item in historial:
            item['cantidad'] = float(item.get('cantidad', 0.0) or 0.0)
            item['costo_unitario_venta'] = float(item.get('costo_unitario_venta', 0.0) or 0.0)
            item['descuento_linea'] = float(item.get('descuento_linea', 0.0) or 0.0)
            item['subtotal_linea_neto'] = float(item.get('subtotal_linea_neto', 0.0) or 0.0)
            
        return historial if historial else []
    except Error as e:
        print(f"Error obteniendo historial de compras para paciente ID {id_px}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_planes_cuidado_paciente(connection, id_px):
    """Obtiene todos los planes de cuidado de un paciente, ordenados por fecha descendente."""
    cursor = None
    try:
        query = """
            SELECT 
                pc.id_plan, 
                pc.fecha AS fecha_creacion_plan, 
                pc.pb_diagnostico,
                pc.visitas_qp, 
                pc.visitas_tf,
                pc.inversion_total,
                pc.adicionales_ids,
                dr.nombre as nombre_doctor_plan,
                (SELECT COUNT(q.id_seguimiento) 
                 FROM quiropractico q 
                 WHERE q.id_plan_cuidado_asociado = pc.id_plan) as visitas_realizadas
            FROM plancuidado pc
            LEFT JOIN dr ON pc.id_dr = dr.id_dr
            WHERE pc.id_px = %s
            ORDER BY pc.fecha DESC, pc.id_plan DESC;
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (id_px,))
        planes = cursor.fetchall()

        # Opcional: Convertir campos numéricos a float/int si es necesario para la plantilla
        for plan in planes:
            if plan.get('inversion_total') is not None:
                try:
                    plan['inversion_total'] = float(plan['inversion_total'])
                except (ValueError, TypeError):
                    plan['inversion_total'] = 0.0
            if plan.get('visitas_qp') is not None:
                try:
                    plan['visitas_qp'] = int(plan['visitas_qp'])
                except (ValueError, TypeError):
                    plan['visitas_qp'] = 0
            if plan.get('visitas_tf') is not None:
                try:
                    plan['visitas_tf'] = int(plan['visitas_tf'])
                except (ValueError, TypeError):
                    plan['visitas_tf'] = 0
            if plan.get('visitas_realizadas') is not None:
                try:
                    plan['visitas_realizadas'] = int(plan['visitas_realizadas'])
                except (ValueError, TypeError):
                    plan['visitas_realizadas'] = 0

        return planes if planes else []
    except Error as e:
        print(f"Error obteniendo planes de cuidado para paciente ID {id_px}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_plan_cuidado_activo_para_paciente(connection, id_px): # Nueva función auxiliar
    cursor = None
    try:
        # Esta query podría necesitar ajustes para definir "activo" 
        # (ej. no completado, más reciente, o un campo 'esta_activo' en plancuidado)
        # Esta versión asume que un plan activo es aquel donde las visitas realizadas
        # son menores que las planificadas.
        query = """
            SELECT 
                pc.id_plan, 
                pc.visitas_qp, 
                pc.visitas_tf, 
                pc.adicionales_ids, 
                pc.inversion_total,
                pc.fecha AS fecha_creacion_plan,
                (SELECT COUNT(q.id_seguimiento) 
                 FROM quiropractico q 
                 WHERE q.id_plan_cuidado_asociado = pc.id_plan) as visitas_realizadas
            FROM plancuidado pc
            LEFT JOIN (
                SELECT id_plan_cuidado_asociado, COUNT(id_seguimiento) as seguimientos_realizados
                FROM quiropractico
                GROUP BY id_plan_cuidado_asociado
            ) q_count ON pc.id_plan = q_count.id_plan_cuidado_asociado
            WHERE pc.id_px = %s 
            AND (q_count.seguimientos_realizados IS NULL OR q_count.seguimientos_realizados < pc.visitas_qp)
            ORDER BY pc.fecha DESC, pc.id_plan DESC
            LIMIT 1;
        """
        # Si tienes un campo 'esta_activo' en tu tabla 'plancuidado', la condición WHERE sería más simple:
        # WHERE pc.id_px = %s AND pc.esta_activo = 1 
        # ORDER BY STR_TO_DATE(pc.fecha, '%d/%m/%Y') DESC, pc.id_plan DESC LIMIT 1;

        cursor = connection.cursor(dictionary=True, buffered=True) # buffered=True es bueno si reutilizas
        cursor.execute(query, (id_px,))
        plan = cursor.fetchone()

        if plan: # Convertir a tipos correctos si es necesario
            if plan.get('visitas_qp') is not None:
                try: plan['visitas_qp'] = int(plan['visitas_qp'])
                except (ValueError, TypeError): plan['visitas_qp'] = 0
            if plan.get('visitas_tf') is not None:
                try: plan['visitas_tf'] = int(plan['visitas_tf'])
                except (ValueError, TypeError): plan['visitas_tf'] = 0
            if plan.get('inversion_total') is not None:
                try: plan['inversion_total'] = float(plan['inversion_total'])
                except (ValueError, TypeError): plan['inversion_total'] = 0.0
        
        return plan # Devuelve el plan o None si no se encontró
    except Error as e:
        print(f"Error obteniendo plan activo para paciente ID {id_px}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

   
def get_recibo_detalles_by_id(connection, id_recibo):
    """
    Obtiene todos los detalles (líneas de ítem) para un recibo específico.
    """
    cursor = None
    try:
        # COALESCE se usa para obtener el nombre del producto desde productos_servicios
        # si la descripcion_prod en recibo_detalle es NULL o vacía.
        # También se incluye costo_unitario_compra.
        query = """
            SELECT 
                rd.id_detalle,
                rd.id_recibo,
                rd.id_prod,
                rd.cantidad,
                COALESCE(NULLIF(TRIM(rd.descripcion_prod), ''), ps.nombre, 'Producto/Servicio Desconocido') AS descripcion_item,
                rd.costo_unitario_venta,
                rd.costo_unitario_compra, 
                rd.descuento_linea,
                rd.subtotal_linea_neto,
                ps.nombre AS nombre_producto_original,
                ps.venta AS precio_venta_original_producto,
                ps.costo AS costo_original_producto
            FROM recibo_detalle rd
            LEFT JOIN productos_servicios ps ON rd.id_prod = ps.id_prod
            WHERE rd.id_recibo = %s
            ORDER BY rd.id_detalle ASC;
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (id_recibo,))
        detalles = cursor.fetchall()

        # Asegurar que los campos numéricos sean del tipo correcto (float)
        if detalles:
            for detalle in detalles:
                detalle['cantidad'] = float(detalle.get('cantidad', 0.0) or 0.0)
                detalle['costo_unitario_venta'] = float(detalle.get('costo_unitario_venta', 0.0) or 0.0)
                detalle['costo_unitario_compra'] = float(detalle.get('costo_unitario_compra', 0.0) or 0.0)
                detalle['descuento_linea'] = float(detalle.get('descuento_linea', 0.0) or 0.0)
                detalle['subtotal_linea_neto'] = float(detalle.get('subtotal_linea_neto', 0.0) or 0.0)
                detalle['precio_venta_original_producto'] = float(detalle.get('precio_venta_original_producto', 0.0) or 0.0)
                detalle['costo_original_producto'] = float(detalle.get('costo_original_producto', 0.0) or 0.0)
        
        return detalles if detalles else []
    except Error as e:
        print(f"Error obteniendo detalles del recibo ID {id_recibo}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_recibos_by_patient(connection, patient_id):
    """
    Obtiene todos los recibos para un paciente específico, ordenados por fecha descendente.
    """
    cursor = None
    try:
        query = """
            SELECT 
                r.id_recibo, 
                r.fecha, 
                r.total_neto, 
                d.nombre AS nombre_doctor,
                (SELECT GROUP_CONCAT(COALESCE(NULLIF(TRIM(rd.descripcion_prod), ''), ps.nombre) SEPARATOR ', ') 
                 FROM recibo_detalle rd 
                 LEFT JOIN productos_servicios ps ON rd.id_prod = ps.id_prod
                 WHERE rd.id_recibo = r.id_recibo) AS conceptos_principales
            FROM recibos r
            LEFT JOIN dr d ON r.id_dr = d.id_dr
            WHERE r.id_px = %s
            ORDER BY r.fecha DESC, r.id_recibo DESC;
        """
        # Nota: GROUP_CONCAT puede tener un límite de longitud por defecto.
        # Si tienes muchos ítems por recibo, podrías necesitar ajustarlo en MySQL
        # o manejar la concatenación de descripciones en Python después de otra query.
        
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (patient_id,))
        recibos = cursor.fetchall()
        
        if recibos:
            for recibo in recibos:
                if 'fecha' in recibo and isinstance(recibo['fecha'], date):
                    recibo['fecha'] = recibo['fecha'].strftime('%d/%m/%Y')

                if recibo.get('total_neto') is not None:
                    try:
                        recibo['total_neto'] = float(recibo['total_neto'])
                    except (ValueError, TypeError):
                        recibo['total_neto'] = 0.0
                # Limitar la longitud de conceptos_principales si es muy larga para la vista
                if recibo.get('conceptos_principales') and len(recibo['conceptos_principales']) > 70: # Ejemplo de límite
                    recibo['conceptos_principales'] = recibo['conceptos_principales'][:67] + "..."

        return recibos if recibos else []
    except Error as e:
        print(f"Error obteniendo recibos para el paciente ID {patient_id}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_latest_recibo_id_for_patient(connection, patient_id):
    """
    Obtiene el ID del último recibo generado para un paciente específico.
    Útil si se necesita redirigir o referenciar el último recibo.
    """
    cursor = None
    try:
        query = """
            SELECT id_recibo 
            FROM recibos 
            WHERE id_px = %s 
            ORDER BY id_recibo DESC 
            LIMIT 1;
        """
        # Alternativamente, si la fecha es más fiable que el ID autoincremental para "último":
        # query = """
        #     SELECT id_recibo
        #     FROM recibos
        #     WHERE id_px = %s
        #     ORDER BY fecha DESC, id_recibo DESC
        #     LIMIT 1;
        # """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (patient_id,))
        result = cursor.fetchone()
        if result:
            return result['id_recibo']
        return None
    except Error as e:
        print(f"Error obteniendo el último ID de recibo para el paciente ID {patient_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_recibo_by_id(connection, recibo_id):
    """
    Obtiene los datos principales de un recibo específico por su ID.
    *** ACTUALIZADO: Convierte la fecha a string dd/mm/YYYY ***
    """
    cursor = None
    try:
        query = """
            SELECT 
                r.id_recibo,
                r.id_px,
                CONCAT(dp.nombre, ' ', dp.apellidop, IFNULL(CONCAT(' ', dp.apellidom), '')) AS nombre_paciente_completo,
                r.id_dr,
                dr.nombre AS nombre_doctor_recibo,
                r.fecha,  -- <-- Obtenemos el objeto DATE
                r.subtotal_bruto,
                r.descuento_total,
                r.total_neto,
                r.pago_efectivo,
                r.pago_tarjeta,
                r.pago_transferencia,
                r.pago_otro,
                r.pago_otro_desc,
                r.notas,
                ce.nombre AS nombre_centro,
                ce.direccion AS direccion_centro,
                ce.tel AS telefono_centro,
                ce.cel AS celular_centro
            FROM recibos r
            JOIN datos_personales dp ON r.id_px = dp.id_px
            LEFT JOIN dr ON r.id_dr = dr.id_dr
            LEFT JOIN centro ce ON dr.centro = ce.id_centro
            WHERE r.id_recibo = %s;
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (recibo_id,))
        recibo_data = cursor.fetchone()

        if recibo_data:
            
            # 1. Convertir el objeto 'date' a string 'dd/mm/YYYY'
            if 'fecha' in recibo_data and isinstance(recibo_data['fecha'], date):
                recibo_data['fecha'] = recibo_data['fecha'].strftime('%d/%m/%Y')
            

            # 2. Convertir campos numéricos (esto ya lo tenías)
            recibo_data['subtotal_bruto'] = float(recibo_data.get('subtotal_bruto', 0.0) or 0.0)
            recibo_data['descuento_total'] = float(recibo_data.get('descuento_total', 0.0) or 0.0)
            recibo_data['total_neto'] = float(recibo_data.get('total_neto', 0.0) or 0.0)
            recibo_data['pago_efectivo'] = float(recibo_data.get('pago_efectivo', 0.0) or 0.0)
            recibo_data['pago_tarjeta'] = float(recibo_data.get('pago_tarjeta', 0.0) or 0.0)
            recibo_data['pago_transferencia'] = float(recibo_data.get('pago_transferencia', 0.0) or 0.0)
            recibo_data['pago_otro'] = float(recibo_data.get('pago_otro', 0.0) or 0.0)
            
        return recibo_data
    except Error as e:
        print(f"Error obteniendo el recibo ID {recibo_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_patients_by_recent_followup(connection, limit=10):
    """
    Obtiene los 'limit' pacientes con el seguimiento más reciente.
    *** ACTUALIZADO: Elimina STR_TO_DATE (ya es DATE) y formatea en Python ***
    """
    cursor = None
    try:
        # --- !! CORRECCIÓN SQL !! ---
        # Quitamos STR_TO_DATE porque q.fecha ya es DATE
        query = """
            SELECT
                dp.id_px,
                dp.nombre,
                dp.apellidop,
                dp.apellidom,
                MAX(q.fecha) AS fecha_ultimo_seguimiento
            FROM
                datos_personales dp
            JOIN
                quiropractico q ON dp.id_px = q.id_px
            GROUP BY
                dp.id_px, dp.nombre, dp.apellidop, dp.apellidom
            ORDER BY
                fecha_ultimo_seguimiento DESC, dp.id_px DESC
            LIMIT %s;
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (limit,))
        patients = cursor.fetchall()
        
        # --- !! CORRECCIÓN PYTHON !! ---
        # Convertir el objeto date a string dd/mm/YYYY para la vista
        if patients:
            for p in patients:
                p['fecha_ultimo_seguimiento'] = to_frontend_str(p.get('fecha_ultimo_seguimiento'))
        
        return patients if patients else []
    except Error as e:
        print(f"Error obteniendo pacientes por seguimiento reciente: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_resumen_dia_anterior(connection):
    """
    Obtiene un resumen de los pacientes atendidos el día anterior.
    Con DEBUGGING activado.
    """
    cursor = None
    resumen_pacientes = []
    
    print("\n--- DEBUG: Iniciando get_resumen_dia_anterior ---")
    
    try:
        terapias_disponibles = get_terapias_fisicas(connection)
        terapias_map = {str(t['id_prod']): t['nombre'] for t in terapias_disponibles}

        cursor = connection.cursor(dictionary=True)
        
        # --- INICIO LÓGICA DE BÚSQUEDA (OPTIMIZADA) ---
        print("DEBUG: Buscando última fecha con registros en los últimos 30 días...")
        
        # Consulta optimizada: Obtener la fecha máxima en el rango de los últimos 30 días
        query_ultima_fecha = """
            SELECT MAX(fecha) as ultima_fecha 
            FROM quiropractico 
            WHERE fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        """
        cursor.execute(query_ultima_fecha)
        result = cursor.fetchone()
        
        fecha_encontrada_str = None
        if result and result.get('ultima_fecha'):
            # Asegurar formato YYYY-MM-DD
            fecha_obj = result['ultima_fecha']
            if isinstance(fecha_obj, str):
                fecha_encontrada_str = fecha_obj
            else:
                fecha_encontrada_str = fecha_obj.strftime('%Y-%m-%d')
            print(f"DEBUG: ¡ENCONTRADO! Última fecha con datos: {fecha_encontrada_str}")
        else:
            print("ADVERTENCIA: No se encontraron seguimientos en los últimos 30 días.")
            return [] 

        # --- PASO 2: Obtener Pacientes ---
        print(f"DEBUG: Buscando IDs de pacientes para {fecha_encontrada_str}")
        
        sql_pacientes_ayer = """
            SELECT DISTINCT id_px
            FROM quiropractico
            WHERE fecha = %s
            ORDER BY id_px; 
        """
        cursor.execute(sql_pacientes_ayer, (fecha_encontrada_str,))
        pacientes_rows = cursor.fetchall()
        pacientes_ayer_ids = [row['id_px'] for row in pacientes_rows]

        print(f"DEBUG: Pacientes encontrados (IDs): {pacientes_ayer_ids}")

        if not pacientes_ayer_ids:
            print(f"DEBUG: Extraño... la búsqueda inicial dijo que sí había datos, pero ahora la lista de pacientes está vacía.")
            return []

        # 3. Procesar cada paciente (sin cambios en la lógica, solo prints)
        for patient_id in pacientes_ayer_ids:
            # ... (resto de tu lógica de procesamiento de pacientes, no necesitamos debuguear esto por ahora) ...
            # Copia aquí el resto de tu función original (el bucle for completo)
            # O para la prueba rápida, puedes dejar este bloque simple para ver si llega hasta aquí:
            
            paciente_info = {
                'id_px': patient_id,
                'nombre_completo': 'Test Debug',
                 # ... Rellena con tu lógica original si quieres ver el reporte completo ...
            }
            # (Para no hacer el código gigante aquí, asumo que mantienes tu lógica del bucle for)
            
            # --- COPIA TU BUCLE FOR ORIGINAL AQUÍ ---
            # ...
            cursor.execute("SELECT nombre, apellidop, apellidom FROM datos_personales WHERE id_px = %s", (patient_id,))
            paciente_db = cursor.fetchone()
            if paciente_db:
                paciente_info['nombre_completo'] = f"{paciente_db.get('nombre', '')} {paciente_db.get('apellidop', '')} {paciente_db.get('apellidom', '')}".strip()
            
            ultima_anamnesis_data = get_latest_anamnesis(connection, patient_id)
            if ultima_anamnesis_data:
                 paciente_info['condicion1_anamnesis'] = ultima_anamnesis_data.get('condicion1', 'N/A')

            sql_ultimos_seguimientos = """
                SELECT fecha, notas, terapia,
                       CONCAT_WS(', ',
                           NULLIF(occipital, ''), NULLIF(atlas, ''), NULLIF(axis, ''), NULLIF(c3, ''), NULLIF(c4, ''),
                           NULLIF(c5, ''), NULLIF(c6, ''), NULLIF(c7, ''), NULLIF(t1, ''), NULLIF(t2, ''),
                           NULLIF(t3, ''), NULLIF(t4, ''), NULLIF(t5, ''), NULLIF(t6, ''), NULLIF(t7, ''),
                           NULLIF(t8, ''), NULLIF(t9, ''), NULLIF(t10, ''), NULLIF(t11, ''), NULLIF(t12, ''),
                           NULLIF(l1, ''), NULLIF(l2, ''), NULLIF(l3, ''), NULLIF(l4, ''), NULLIF(l5, ''),
                           NULLIF(sacro, ''), NULLIF(coxis, ''), NULLIF(iliaco_d, ''), NULLIF(iliaco_i, ''), NULLIF(pubis, '')
                       ) AS segmentos_ajustados,
                       id_plan_cuidado_asociado -- <-- Necesitamos esto para el plan
                FROM quiropractico
                WHERE id_px = %s
                ORDER BY fecha DESC, id_seguimiento DESC
                LIMIT 2;
            """
            cursor.execute(sql_ultimos_seguimientos, (patient_id,))
            ultimos_seguimientos = cursor.fetchall()

            id_plan_ayer = None
            
            if ultimos_seguimientos:
                seg_ayer = ultimos_seguimientos[0]
                id_plan_ayer = seg_ayer.get('id_plan_cuidado_asociado') # Obtener ID del plan
                
                terapias_ids_ayer = [tid for tid in seg_ayer.get('terapia', '0,').split(',') if tid and tid != '0']
                terapias_nombres_ayer = [terapias_map.get(tid, f"ID:{tid}") for tid in terapias_ids_ayer]
                terapias_texto_ayer = ', '.join(terapias_nombres_ayer) if terapias_nombres_ayer else 'Ninguna'
                
                # --- CORRECCIÓN EN LEER FECHA (Python DATE a String) ---
                fecha_seg_ayer_str = seg_ayer.get('fecha')
                if isinstance(fecha_seg_ayer_str, date): 
                    fecha_seg_ayer_str = fecha_seg_ayer_str.strftime('%d/%m/%Y')

                paciente_info['seguimiento_ayer'] = {
                    'fecha': fecha_seg_ayer_str,
                    'segmentos': seg_ayer.get('segmentos_ajustados') or 'Ninguno',
                    'terapias': terapias_texto_ayer,
                    'notas': seg_ayer.get('notas') or 'Sin notas.'
                }

                if len(ultimos_seguimientos) > 1:
                    seg_anterior = ultimos_seguimientos[1]
                    terapias_ids_anterior = [tid for tid in seg_anterior.get('terapia', '0,').split(',') if tid and tid != '0']
                    terapias_nombres_anterior = [terapias_map.get(tid, f"ID:{tid}") for tid in terapias_ids_anterior]
                    terapias_texto_anterior = ', '.join(terapias_nombres_anterior) if terapias_nombres_anterior else 'Ninguna'
                    
                    fecha_seg_ant_str = seg_anterior.get('fecha')
                    if isinstance(fecha_seg_ant_str, date): fecha_seg_ant_str = fecha_seg_ant_str.strftime('%d/%m/%Y')

                    paciente_info['seguimiento_anterior'] = {
                        'fecha': fecha_seg_ant_str,
                        'segmentos': seg_anterior.get('segmentos_ajustados') or 'Ninguno',
                        'terapias': terapias_texto_anterior,
                    }

            # Lógica del plan (simplificada para el ejemplo, usa la tuya)
            plan_activo_data = None
            if id_plan_ayer:
                 plan_activo_data = get_specific_plan_cuidado(connection, id_plan_ayer) 
            if not plan_activo_data:
                plan_activo_data = get_plan_cuidado_activo_para_paciente(connection, patient_id)

            if plan_activo_data and plan_activo_data.get('id_plan'):
                id_plan_activo = plan_activo_data['id_plan']
                total_qp_plan = plan_activo_data.get('visitas_qp', 0)
                total_tf_plan = plan_activo_data.get('visitas_tf', 0)
                seguimientos_del_plan = get_seguimientos_for_plan(connection, id_plan_activo)
                qp_consumidas = 0
                tf_consumidas = 0
                if seguimientos_del_plan:
                    qp_consumidas = len(seguimientos_del_plan)
                    for seg in seguimientos_del_plan:
                        terapias_ids_seg = [tid for tid in seg.get('terapia', '0,').split(',') if tid and tid != '0']
                        if terapias_ids_seg: tf_consumidas += 1
                
                qp_restantes = total_qp_plan - qp_consumidas
                tf_restantes = total_tf_plan - tf_consumidas
                
                paciente_info['plan_activo'] = {
                    'nombre': plan_activo_data.get('pb_diagnostico', f'Plan ID:{id_plan_activo}'),
                    'qp_restantes': qp_restantes,
                    'tf_restantes': tf_restantes,
                    'completado': (qp_restantes <= 0 and tf_restantes <= 0)
                }

            resumen_pacientes.append(paciente_info)
            # --- FIN COPIA BUCLE ---

        return resumen_pacientes

    except Error as e:
        print(f"Error en get_resumen_dia_anterior: {e}")
        return []
    finally:
        if cursor:
            cursor.close()

def get_first_postura_on_or_after_date(connection, patient_id, target_date_str):
    """
    Encuentra el registro de postura más ANTIGUO para un paciente
    en o DESPUÉS de una fecha específica (formato dd/mm/yyyy).
    Si no encuentra, busca el más reciente ANTES como fallback.
    """
    cursor = None
    # !! VERIFICA QUE 'postura' SEA EL NOMBRE CORRECTO DE TU TABLA !!
    tabla_posturas = "postura"
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Convertir fecha objetivo a YYYY-MM-DD
        try:
            target_date_sql = parse_date(target_date_str)
        except ValueError:
             # Si falla (ej. ya viene en YYYY-MM-DD o es inválida), intentamos usarla tal cual o logueamos
             # Asumimos que viene en dd/mm/yyyy como dice el docstring
             print(f"WARN: Fecha inválida en get_first_postura_on_or_after_date: {target_date_str}")
             return None

        # 1. Intenta buscar en o después de la fecha
        sql_after = f"""
            SELECT *
            FROM {tabla_posturas}
            WHERE id_px = %s AND fecha >= %s
            ORDER BY fecha ASC, id_postura ASC
            LIMIT 1;
        """
        cursor.execute(sql_after, (patient_id, target_date_sql))
        result = cursor.fetchone()

        # 2. Fallback
        if not result:
            print(f"INFO: No se encontró postura en o después de {target_date_str}. Buscando antes.")
            sql_before = f"""
                SELECT *
                FROM {tabla_posturas}
                WHERE id_px = %s AND fecha < %s
                ORDER BY fecha DESC, id_postura DESC
                LIMIT 1;
            """
            cursor.execute(sql_before, (patient_id, target_date_sql))
            result = cursor.fetchone()

        return result
    except Error as e:
        print(f"Error en get_first_postura_on_or_after_date: {e}")
        return None
    finally:
        if cursor:
            cursor.close()            


def get_active_plan_status(connection, patient_id):
    """
    Obtiene el plan de cuidado activo MÁS reciente y calcula su estado de uso
    (sesiones consumidas y restantes).
    """
    # 1. Obtener el plan activo más reciente
    # Usamos la función que ya existe y que busca el plan activo (si no, la de más abajo)
    # NOTA: get_plan_cuidado_activo_para_paciente ya busca el plan MÁS RECIENTE
    plan_data = get_plan_cuidado_activo_para_paciente(connection, patient_id)

    if not plan_data:
        # Si no se encontró un plan "activo", salimos.
        # Podríamos buscar el último "completado", pero por ahora nos centramos en el activo.
        return None

    # 2. Si se encontró un plan, obtener sus seguimientos
    id_plan_activo = plan_data.get('id_plan')
    total_qp_plan = plan_data.get('visitas_qp', 0)
    total_tf_plan = plan_data.get('visitas_tf', 0)

    seguimientos_del_plan = get_seguimientos_for_plan(connection, id_plan_activo)

    # 3. Calcular sesiones consumidas (misma lógica que usamos en el resumen)
    qp_consumidas = 0
    tf_consumidas = 0
    if seguimientos_del_plan:
        qp_consumidas = len(seguimientos_del_plan) # Cada seguimiento cuenta como 1 QP
        for seg in seguimientos_del_plan:
            terapias_ids_seg = [tid for tid in seg.get('terapia', '0,').split(',') if tid and tid != '0']
            if terapias_ids_seg: # Si el seguimiento tuvo terapias, cuenta como 1 TF
                tf_consumidas += 1

    # 4. Añadir los cálculos al diccionario del plan
    plan_data['qp_consumidas'] = qp_consumidas
    plan_data['tf_consumidas'] = tf_consumidas
    plan_data['qp_restantes'] = total_qp_plan - qp_consumidas
    plan_data['tf_restantes'] = total_tf_plan - tf_consumidas

    return plan_data # Devuelve el diccionario del plan ENRIQUECIDO          


def update_postura_ortho_notes(connection, id_postura, notas):
    """
    Actualiza ÚNICAMENTE el campo de notas ortopédicas de un registro de postura.
    NO HACE COMMIT (asume que es parte de una transacción).
    """
    cursor = None
    if not id_postura or notas is None: # Permite guardar notas vacías si se envían
        print("WARN (update_postura_ortho_notes): Faltan id_postura o notas.")
        return False

    try:
        cursor = connection.cursor()
        # Asumiendo que el nombre de tu tabla es 'postura'
        query = "UPDATE postura SET notas_pruebas_ortoneuro = %s WHERE id_postura = %s"
        cursor.execute(query, (notas, id_postura))

        if cursor.rowcount > 0:
            print(f"INFO: Notas ortopédicas actualizadas para id_postura {id_postura}.")
        else:
            print(f"WARN: No se encontró id_postura {id_postura} para actualizar notas (o las notas eran las mismas).")

        return True # Indica que la consulta se ejecutó

    except Error as e:
        print(f"ERROR en update_postura_ortho_notes: {e}")
        return False # Indica fallo
    finally:
        if cursor:
            cursor.close()

def analizar_adicionales_plan(connection, id_plan):
    """
    Analiza los productos adicionales de un plan, verifica el historial de compras
    y determina si faltan por adquirir o si necesitan renovación.
    *** ACTUALIZADO: Corrige la comparación de fechas (date vs datetime) ***
    """
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)

        # 1. Obtener el ID del paciente y los productos (sin cambios)
        cursor.execute("SELECT id_px, adicionales_ids FROM plancuidado WHERE id_plan = %s", (id_plan,))
        plan = cursor.fetchone()
        if not plan or not plan.get('adicionales_ids'): return []
        patient_id = plan['id_px']
        adicionales_ids_str = plan['adicionales_ids'].strip('0,')
        if not adicionales_ids_str: return []
        adicionales_ids_list = [int(id_str) for id_str in adicionales_ids_str.split(',') if id_str.isdigit()]
        if not adicionales_ids_list: return []
        placeholders = ', '.join(['%s'] * len(adicionales_ids_list))

        # 2. Obtener los nombres de los productos (sin cambios)
        query_productos = f"SELECT id_prod, nombre FROM productos_servicios WHERE id_prod IN ({placeholders})"
        cursor.execute(query_productos, tuple(adicionales_ids_list))
        recommended_products = {prod['id_prod']: prod for prod in cursor.fetchall()}

        # 3. Obtener el historial de compras (ya corregido, pide el objeto DATE)
        query_compras = f"""
            SELECT rd.id_prod, r.fecha
            FROM recibo_detalle rd
            JOIN recibos r ON rd.id_recibo = r.id_recibo
            WHERE r.id_px = %s AND rd.id_prod IN ({placeholders})
            ORDER BY r.fecha DESC
        """
        cursor.execute(query_compras, (patient_id,) + tuple(adicionales_ids_list))
        purchase_history = cursor.fetchall()

        # 4. Analizar cada producto (LÓGICA CORREGIDA)
        status_list = []
        
        # --- !! INICIO DE LA CORRECCIÓN !! ---
        # 1. Usar datetime.now().date() para obtener un objeto DATE
        today = datetime.now().date() 
        # --- !! FIN DE LA CORRECCIÓN !! ---

        for prod_id in adicionales_ids_list:
            prod_info = recommended_products.get(prod_id)
            if not prod_info: continue

            latest_purchase = next((p for p in purchase_history if p['id_prod'] == prod_id), None)

            analysis = {
                'id_prod': prod_id,
                'nombre': prod_info['nombre'],
                'status': '',
                'ultima_compra': None,
                'fecha_renovacion': None
            }

            if not latest_purchase:
                analysis['status'] = 'Falta adquirir'
            else:
                purchase_date_obj = latest_purchase.get('fecha')
                
                # 2. Verificar que la fecha no sea Nula (importante)
                if not purchase_date_obj or not isinstance(purchase_date_obj, date):
                    analysis['status'] = 'Error en fecha'
                    analysis['ultima_compra'] = 'Inválida'
                    status_list.append(analysis)
                    continue # Saltar al siguiente producto

                try:
                    # 3. Formatear para mostrar
                    analysis['ultima_compra'] = purchase_date_obj.strftime('%d/%m/%Y')
                    
                    # 4. Usar el objeto DATE para la lógica
                    purchase_date = purchase_date_obj 
                    
                    renewal_date = None
                    if 'plantilla' in prod_info['nombre'].lower():
                        renewal_date = purchase_date + relativedelta(months=6)
                    else:
                        renewal_date = purchase_date + relativedelta(months=1)
                    
                    analysis['fecha_renovacion'] = renewal_date.strftime('%d/%m/%Y')

                    # 5. Comparar DATE vs DATE (ahora sí funciona)
                    if today > renewal_date:
                        analysis['status'] = 'Renovación sugerida'
                    else:
                        analysis['status'] = 'Adquirido'
                
                except (ValueError, TypeError, AttributeError) as e:
                    print(f"Error procesando fechas de renovación: {e}")
                    analysis['status'] = 'Error en fecha'
            
            status_list.append(analysis)
        
        return status_list

    except Error as e:
        print(f"Error en analizar_adicionales_plan: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
                        

def get_unseen_notes_for_patient(connection, patient_id):
    """
    Obtiene todas las notas generales NO vistas (visto=0) para un paciente.
    Ordena por fecha para mostrar la más antigua primero.
    *** ACTUALIZADO: Formatea la fecha en Python ***
    """
    cursor = None
    try:
        # --- !! INICIO DE LA CORRECCIÓN !! ---
        
        # 1. Seleccionamos el objeto DATE puro, no un string formateado
        query = """
            SELECT id_nota, 
                   fecha,  -- <-- Seleccionar objeto DATE
                   notas 
            FROM notas_generales 
            WHERE id_px = %s AND (visto = 0 OR visto IS NULL) 
            ORDER BY fecha ASC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        notes = cursor.fetchall()
        
        # 2. Formateamos la fecha usando Python
        if notes:
            for note in notes:
                # (Asegúrate de tener 'from datetime import date' al inicio de database.py)
                if note['fecha'] and isinstance(note['fecha'], date):
                    note['fecha'] = note['fecha'].strftime('%d/%m/%Y')
                elif not note['fecha']:
                    note['fecha'] = 'Sin Fecha' # Un fallback por si acaso
        
        # --- !! FIN DE LA CORRECCIÓN !! ---

        return notes if notes else []
    except Error as e:
        print(f"Error obteniendo notas no vistas para paciente {patient_id}: {e}")
        return []
    finally:
        if cursor:
            cursor.close()
            
def mark_notes_as_seen(connection, note_ids_list):
    """
    Marca una lista de IDs de notas como vistas (visto=1).
    NO HACE COMMIT (asume que se maneja en la ruta).
    """
    if not note_ids_list:
        return 0
    
    cursor = None
    try:
        # Convertir todos los IDs a int por seguridad
        safe_ids = [int(id_nota) for id_nota in note_ids_list if str(id_nota).isdigit()]
        if not safe_ids:
            return 0
        
        # Crear placeholders (%s) para cada ID en la lista
        placeholders = ', '.join(['%s'] * len(safe_ids))
        
        query = f"UPDATE notas_generales SET visto = 1 WHERE id_nota IN ({placeholders})"
        
        cursor = connection.cursor()
        cursor.execute(query, tuple(safe_ids))
        rows_affected = cursor.rowcount
        print(f"Marcadas {rows_affected} notas como vistas.")
        return rows_affected
    except Error as e:
        print(f"Error marcando notas como vistas: {e}")
        raise # Re-lanzar para que la ruta de la API pueda hacer rollback
    finally:
        if cursor:
            cursor.close()

def add_general_note(connection, id_px, notas_text):
    """
    Añade una nueva nota general para un paciente.
    La fecha se establece en HOY y 'visto' en 0 (no visto).
    NO HACE COMMIT.
    """
    cursor = None
    try:
        # Usamos CURDATE() de MySQL para la fecha y '0' para 'visto'
        query = """
            INSERT INTO notas_generales (id_px, fecha, notas, visto)
            VALUES (%s, CURDATE(), %s, 0)
        """
        cursor = connection.cursor()
        cursor.execute(query, (id_px, notas_text))
        new_note_id = cursor.lastrowid
        print(f"Nota general añadida con ID: {new_note_id} para Paciente ID: {id_px}")
        return new_note_id
    except Error as e:
        print(f"Error añadiendo nota general: {e}")
        raise # Re-lanzar para que la API haga rollback
    finally:
        if cursor:
            cursor.close()

def get_latest_postura_on_or_before_date(connection, patient_id, target_date_str):
    """
    Encuentra el registro de postura más reciente para un paciente
    en o antes de una fecha específica (formato dd/mm/yyyy).
    """
    cursor = None
    tabla_posturas = "postura" 
    try:
        target_date_sql = parse_date(target_date_str)
        cursor = connection.cursor(dictionary=True)
        sql = f"""
            SELECT *
            FROM {tabla_posturas}
            WHERE id_px = %s AND fecha <= %s
            ORDER BY fecha DESC, id_postura DESC
            LIMIT 1;
        """
        cursor.execute(sql, (patient_id, target_date_sql))
        result = cursor.fetchone()
        return result
    except ValueError:
        print(f"Error fecha inválida en get_latest_postura_on_or_before_date: {target_date_str}")
        return None
    except Error as e:
        print(f"Error en get_latest_postura_on_or_before_date: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

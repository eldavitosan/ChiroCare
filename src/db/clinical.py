from mysql.connector import Error, IntegrityError
from datetime import datetime, date
from utils.date_manager import to_db_str, to_frontend_str, parse_date

# --- Antecedentes ---
def get_antecedentes_summary(connection, patient_id):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id_antecedente, fecha FROM antecedentes WHERE id_px = %s ORDER BY fecha DESC, id_antecedente DESC", (patient_id,))
        return cursor.fetchall() or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_specific_antecedente(connection, id_antecedente):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM antecedentes WHERE id_antecedente = %s", (id_antecedente,))
        data = cursor.fetchone()
        if data and data.get('calzado'): data['calzado'] = float(data['calzado'])
        return data
    except Error: return None
    finally: 
        if cursor: cursor.close()

def get_latest_antecedente(connection, patient_id):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM antecedentes WHERE id_px = %s ORDER BY fecha DESC, id_antecedente DESC LIMIT 1", (patient_id,))
        data = cursor.fetchone()
        if data and data.get('calzado'): data['calzado'] = float(data['calzado'])
        return data
    except Error: return None
    finally: 
        if cursor: cursor.close()

def save_antecedentes(connection, data):
    cursor = None
    if not all(k in data for k in ['id_px', 'fecha']): return False
    cols = ['peso', 'altura', 'calzado', 'condiciones_generales', 'condicion_diagnosticada', 'presion_alta', 'trigliceridos', 'diabetes', 'agua', 'notas']
    
    try:
        cursor = connection.cursor()
        fecha_sql = parse_date(data.get('fecha'))
        id_update = data.get('id_antecedente')

        for col in cols: data[col] = data.get(col)

        if id_update:
            set_clause = ", ".join([f"`{c}`=%s" for c in cols])
            query = f"UPDATE antecedentes SET `fecha`=%s, {set_clause} WHERE id_antecedente=%s"
            values = [fecha_sql] + [data[c] for c in cols] + [id_update]
            cursor.execute(query, tuple(values))
        else:
            ins_cols = ['id_px', 'fecha'] + cols
            ph = ", ".join(['%s'] * len(ins_cols))
            query = f"INSERT INTO antecedentes ({', '.join([f'`{c}`' for c in ins_cols])}) VALUES ({ph})"
            values = [data['id_px'], fecha_sql] + [data[c] for c in cols]
            cursor.execute(query, tuple(values))
        return True
    except Error as e:
        print(f"Error save_antecedentes: {e}")
        return False
    finally: 
        if cursor: cursor.close()

# --- Anamnesis ---
def get_anamnesis_summary(connection, patient_id):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id_anamnesis, DATE_FORMAT(fecha, '%d/%m/%Y') as fecha, condicion1, condicion2, condicion3 FROM anamnesis WHERE id_px = %s ORDER BY fecha DESC, id_anamnesis DESC", (patient_id,))
        return cursor.fetchall() or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_specific_anamnesis(connection, id_anamnesis):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM anamnesis WHERE id_anamnesis = %s", (id_anamnesis,))
        return cursor.fetchone()
    except Error: return None
    finally: 
        if cursor: cursor.close()

def get_latest_anamnesis(connection, patient_id):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM anamnesis WHERE id_px = %s ORDER BY fecha DESC, id_anamnesis DESC LIMIT 1", (patient_id,))
        return cursor.fetchone()
    except Error: return None
    finally: 
        if cursor: cursor.close()

def save_anamnesis(connection, data):
    cursor = None
    if not all(k in data for k in ['id_px', 'fecha']): return False
    cols = ['condicion1', 'calif1', 'condicion2', 'calif2', 'condicion3', 'calif3', 'como_comenzo', 'primera_vez', 'alivia', 'empeora', 'como_ocurrio', 'actividades_afectadas', 'dolor_intenso', 'tipo_dolor', 'diagrama', 'historia']
    try:
        cursor = connection.cursor()
        fecha_sql = parse_date(data.get('fecha'))
        id_update = data.get('id_anamnesis')

        if id_update:
            set_clause = ", ".join([f"`{c}`=%s" for c in cols])
            query = f"UPDATE anamnesis SET `fecha`=%s, {set_clause} WHERE id_anamnesis=%s"
            values = [fecha_sql] + [data.get(c) for c in cols] + [id_update]
        else:
            ins_cols = ['id_px', 'fecha'] + cols
            ph = ", ".join(['%s'] * len(ins_cols))
            query = f"INSERT INTO anamnesis ({', '.join([f'`{c}`' for c in ins_cols])}) VALUES ({ph})"
            values = [data['id_px'], fecha_sql] + [data.get(c) for c in cols]
        
        cursor.execute(query, tuple(values))
        connection.commit()
        return True
    except IntegrityError: return "duplicate"
    except Error as e: 
        print(f"Error save_anamnesis: {e}")
        return False
    finally: 
        if cursor: cursor.close()

# --- Postura ---
def get_postura_summary(connection, patient_id):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT DISTINCT fecha FROM postura WHERE id_px = %s ORDER BY fecha DESC", (patient_id,))
        return [row['fecha'].strftime('%d/%m/%Y') for row in cursor.fetchall() if row['fecha']]
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_specific_postura_by_date(connection, patient_id, fecha_str):
    cursor = None
    try:
        fecha_sql = parse_date(fecha_str)
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = "SELECT * FROM postura WHERE id_px = %s AND fecha = %s ORDER BY id_postura DESC LIMIT 1"
        cursor.execute(query, (patient_id, fecha_sql))
        data = cursor.fetchone()
        if data:
            for k in ['pie_cm', 'zapato_cm', 'fuerza_izq', 'fuerza_der']:
                if data.get(k): data[k] = float(data[k])
        return data
    except Error: return None
    finally: 
        if cursor: cursor.close()

def save_postura(connection, data):
    cursor = None
    if not all(k in data for k in ['id_px', 'fecha']): return None
    cols = ['frente', 'lado', 'postura_extra', 'pies', 'pies_frontal', 'pies_trasera', 'pie_cm', 'zapato_cm', 'tipo_calzado', 'termografia', 'fuerza_izq', 'fuerza_der', 'oxigeno', 'notas_plantillas', 'notas_pruebas_ortoneuro']
    
    try:
        id_update = data.get('id_postura')
        if not id_update:
            exist = get_specific_postura_by_date(connection, data['id_px'], data['fecha'])
            if exist: id_update = exist['id_postura']
        
        cursor = connection.cursor()
        if id_update:
            set_clause = ", ".join([f"`{c}`=%s" for c in cols])
            query = f"UPDATE postura SET {set_clause} WHERE id_postura=%s"
            values = [data.get(c) for c in cols] + [id_update]
            cursor.execute(query, tuple(values))
            return id_update
        else:
            fecha_sql = to_db_str(data['fecha'])
            ins_cols = ['id_px', 'fecha'] + cols
            ph = ", ".join(['%s'] * len(ins_cols))
            query = f"INSERT INTO postura ({', '.join([f'`{c}`' for c in ins_cols])}) VALUES ({ph})"
            values = [data['id_px'], fecha_sql] + [data.get(c) for c in cols]
            cursor.execute(query, tuple(values))
            return cursor.lastrowid
    except Error as e:
        print(f"Error save_postura: {e}")
        return None
    finally: 
        if cursor: cursor.close()

def get_latest_postura_overall(connection, patient_id):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM postura WHERE id_px = %s ORDER BY fecha DESC, id_postura DESC LIMIT 1", (patient_id,))
        data = cursor.fetchone()
        if data:
            for k in ['pie_cm', 'zapato_cm', 'fuerza_izq', 'fuerza_der']:
                if data.get(k): data[k] = float(data[k])
        return data
    except Error: return None
    finally: 
        if cursor: cursor.close()



def get_first_postura_on_or_after_date(connection, patient_id, target_date_str):
    cursor = None
    try:
        target_date_sql = parse_date(target_date_str)
        cursor = connection.cursor(dictionary=True, buffered=True)
        # Buscar el primero en o después
        query = "SELECT * FROM postura WHERE id_px = %s AND fecha >= %s ORDER BY fecha ASC, id_postura ASC LIMIT 1"
        cursor.execute(query, (patient_id, target_date_sql))
        result = cursor.fetchone()
        
        if not result:
            # Fallback: buscar el más reciente antes
            query_fallback = "SELECT * FROM postura WHERE id_px = %s AND fecha < %s ORDER BY fecha DESC, id_postura DESC LIMIT 1"
            cursor.execute(query_fallback, (patient_id, target_date_sql))
            result = cursor.fetchone()
            
        return result
    except Error: return None
    finally: 
        if cursor: cursor.close()

def update_postura_ortho_notes(connection, id_postura, notas):
    cursor = None
    try:
        cursor = connection.cursor()
        query = "UPDATE postura SET notas_pruebas_ortoneuro = %s WHERE id_postura = %s"
        cursor.execute(query, (notas, id_postura))
        return True
    except Error as e:
        print(f"Error update_postura_ortho_notes: {e}")
        return False
    finally: 
        if cursor: cursor.close()

def get_latest_postura_on_or_before_date(connection, patient_id, target_date_str):
    cursor = None
    try:
        target_date_sql = parse_date(target_date_str)
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = "SELECT * FROM postura WHERE id_px = %s AND fecha <= %s ORDER BY fecha DESC, id_postura DESC LIMIT 1"
        cursor.execute(query, (patient_id, target_date_sql))
        data = cursor.fetchone()
        if data:
            for k in ['pie_cm', 'zapato_cm', 'fuerza_izq', 'fuerza_der']:
                if data.get(k): data[k] = float(data[k])
        return data
    except Error: return None
    finally: 
        if cursor: cursor.close()

def get_latest_antecedente_on_or_before_date(connection, patient_id, target_date_str):
    cursor = None
    try:
        target_date_obj = datetime.strptime(target_date_str, '%d/%m/%Y')
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = "SELECT * FROM antecedentes WHERE id_px = %s AND fecha <= %s ORDER BY fecha DESC, id_antecedente DESC LIMIT 1"
        cursor.execute(query, (patient_id, target_date_obj.strftime('%Y-%m-%d')))
        data = cursor.fetchone()
        if data and data.get('calzado'): data['calzado'] = float(data['calzado'])
        return data
    except (ValueError, Error): return None
    finally: 
        if cursor: cursor.close()



def get_radiografias_for_postura(connection, id_postura):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM radiografias WHERE id_postura = %s ORDER BY fecha_carga DESC", (id_postura,))
        return cursor.fetchall() or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def insert_radiografia(connection, id_postura, ruta_archivo):
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO radiografias (id_postura, ruta_archivo) VALUES (%s, %s)", (id_postura, ruta_archivo))
        return cursor.lastrowid
    except Error: raise
    finally: 
        if cursor: cursor.close()

# --- Revaloraciones ---
def get_revaloraciones_summary(connection, patient_id):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id_revaloracion, fecha FROM revaloraciones WHERE id_px = %s ORDER BY fecha DESC, id_revaloracion DESC", (patient_id,))
        return cursor.fetchall() or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_specific_revaloracion(connection, id_revaloracion):
    cursor = None
    try:
        query = """
            SELECT r.*,
                   p.frente AS frente_path, p.lado AS lado1_path, p.postura_extra AS lado2_path,
                   p.pies AS pies_path, p.termografia AS termografia_path,
                   p.pies_frontal AS pies_frontal_path, p.pies_trasera AS pies_trasera_path
            FROM revaloraciones r
            LEFT JOIN postura p ON r.id_postura_asociado = p.id_postura
            WHERE r.id_revaloracion = %s
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_revaloracion,))
        return cursor.fetchone()
    except Error: return None
    finally: 
        if cursor: cursor.close()

def get_latest_revaloracion_overall(connection, patient_id):
    cursor = None
    try:
        query = """
            SELECT r.*,
                   p.frente AS frente_path, p.lado AS lado1_path, p.postura_extra AS lado2_path,
                   p.pies AS pies_path, p.termografia AS termografia_path,
                   p.pies_frontal AS pies_frontal_path, p.pies_trasera AS pies_trasera_path
            FROM revaloraciones r
            LEFT JOIN postura p ON r.id_postura_asociado = p.id_postura
            WHERE r.id_px = %s
            ORDER BY r.fecha DESC, r.id_revaloracion DESC LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        return cursor.fetchone()
    except Error: return None
    finally: 
        if cursor: cursor.close()

def save_revaloracion(connection, data):
    cursor = None
    if not all(k in data for k in ['id_px', 'id_dr', 'fecha']): return None
    cols = ['fecha', 'id_anamnesis_inicial', 'id_postura_asociado', 'calif1_actual', 'calif2_actual', 'calif3_actual', 'mejora_subjetiva_pct', 'notas_adicionales_reval', 'diagrama_actual']
    
    try:
        cursor = connection.cursor()
        fecha_sql = parse_date(data.get('fecha'))
        id_update = data.get('id_revaloracion')
        
        # Copiar datos existentes si update
        existing = {}
        if id_update:
            existing = get_specific_revaloracion(connection, id_update) or {}
        
        final_vals = []
        for c in cols:
            val = data.get(c)
            if val is None and id_update: val = existing.get(c)
            final_vals.append(val if c != 'fecha' else fecha_sql)

        if id_update:
            set_clause = ", ".join([f"`{c}`=%s" for c in cols])
            query = f"UPDATE revaloraciones SET {set_clause} WHERE id_revaloracion=%s"
            cursor.execute(query, tuple(final_vals + [id_update]))
            return id_update
        else:
            ins_cols = ['id_px', 'id_dr'] + cols
            ph = ", ".join(['%s'] * len(ins_cols))
            query = f"INSERT INTO revaloraciones ({', '.join([f'`{c}`' for c in ins_cols])}) VALUES ({ph})"
            vals = [data['id_px'], data['id_dr']] + final_vals
            cursor.execute(query, tuple(vals))
            return cursor.lastrowid
    except Error as e:
        print(f"Error save_revaloracion: {e}")
        return None
    finally: 
        if cursor: cursor.close()

# --- Seguimientos ---
def get_seguimiento_summary(connection, patient_id):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id_seguimiento, fecha FROM quiropractico WHERE id_px = %s ORDER BY fecha DESC, id_seguimiento DESC", (patient_id,))
        return cursor.fetchall() or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_specific_seguimiento(connection, id_seguimiento):
    cursor = None
    try:
        query = """
            SELECT q.*, dr.nombre as nombre_doctor_seguimiento 
            FROM quiropractico q
            LEFT JOIN dr ON q.id_dr = dr.id_dr 
            WHERE q.id_seguimiento = %s
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_seguimiento,))
        return cursor.fetchone()
    except Error: return None
    finally: 
        if cursor: cursor.close()

def save_seguimiento(connection, data):
    cursor = None
    if not all(k in data for k in ['id_px', 'id_dr', 'fecha']): return None
    cols = ['fecha', 'occipital', 'atlas', 'axis', 'c3', 'c4', 'c5', 'c6', 'c7', 't1', 't2', 't3', 't4', 't5', 't6', 't7', 't8', 't9', 't10', 't11', 't12', 'l1', 'l2', 'l3', 'l4', 'l5', 'sacro', 'coxis', 'iliaco_d', 'iliaco_i', 'notas', 'terapia', 'pubis', 'id_plan_cuidado_asociado', 'id_dr']
    
    try:
        cursor = connection.cursor()
        fecha_sql = parse_date(data.get('fecha'))
        id_update = data.get('id_seguimiento')
        
        vals = []
        for c in cols:
            v = data.get(c)
            if c == 'fecha': v = fecha_sql
            elif v is None and c == 'id_plan_cuidado_asociado': v = None
            elif v is None: v = '' 
            vals.append(v)

        if id_update:
            cols_no_fecha = [c for c in cols if c != 'fecha']
            set_clause = "fecha=%s, " + ", ".join([f"`{c}`=%s" for c in cols_no_fecha])
            query = f"UPDATE quiropractico SET {set_clause} WHERE id_seguimiento=%s"
            # Reorganizar vals para fecha primero
            vals_update = [fecha_sql] + [data.get(c) for c in cols_no_fecha] + [id_update]
            cursor.execute(query, tuple(vals_update))
            return id_update
        else:
            ins_cols = ['id_px'] + cols
            ph = ", ".join(['%s'] * len(ins_cols))
            query = f"INSERT INTO quiropractico ({', '.join([f'`{c}`' for c in ins_cols])}) VALUES ({ph})"
            vals_ins = [data['id_px']] + vals
            cursor.execute(query, tuple(vals_ins))
            return cursor.lastrowid
    except Error as e:
        print(f"Error save_seguimiento: {e}")
        return None
    finally: 
        if cursor: cursor.close()

def get_clinical_dates_with_types(connection, patient_id):
    # Lógica simplificada para obtener fechas
    cursor = None
    dates_info = {}
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        for table in ['antecedentes', 'anamnesis', 'postura', 'revaloraciones']:
            cursor.execute(f"SELECT DISTINCT fecha FROM {table} WHERE id_px = %s", (patient_id,))
            for row in cursor.fetchall():
                if not row['fecha']: continue
                d_str = to_frontend_str(row['fecha'])
                if d_str not in dates_info:
                    dates_info[d_str] = {'fecha': d_str, 'has_antecedentes': False, 'has_anamnesis': False, 'has_postura': False, 'has_revaloracion': False}
        
        for d_str, info in dates_info.items():
            f_sql = to_db_str(d_str)
            for table in ['antecedentes', 'anamnesis', 'postura', 'revaloraciones']:
                cursor.execute(f"SELECT 1 FROM {table} WHERE id_px=%s AND fecha=%s LIMIT 1", (patient_id, f_sql))
                if cursor.fetchone():
                    info[f"has_{table}"] = True
                    
        return sorted(dates_info.values(), key=lambda x: to_db_str(x['fecha']))
    except Error: return []
    finally: 
        if cursor: cursor.close()

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

def get_latest_radiografias_overall(connection, patient_id, limit=5):
    """
    Obtiene los registros de las 'limit' radiografías más recientes
    para un paciente, ordenadas por fecha de carga descendente.
    """
    cursor = None
    try:
        query = """
            SELECT
                rx.id_radiografia,
                rx.id_postura,
                rx.fecha_carga,
                rx.ruta_archivo,
                p.fecha AS fecha_visita_asociada
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

def get_specific_anamnesis_by_date(connection, patient_id, fecha_str):
    """Obtiene el registro de anamnesis para un paciente en una fecha específica."""
    cursor = None
    try:
        fecha_sql = parse_date(fecha_str)
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = """
            SELECT id_anamnesis, id_px, fecha, condicion1, calif1, condicion2, calif2,
                   condicion3, calif3, como_comenzo, primera_vez, alivia, empeora,
                   como_ocurrio, actividades_afectadas, dolor_intenso, tipo_dolor,
                   diagrama, historia 
            FROM anamnesis
            WHERE id_px = %s AND fecha = %s
            ORDER BY id_anamnesis DESC
            LIMIT 1
        """
        cursor.execute(query, (patient_id, fecha_sql))
        return cursor.fetchone()
    except (ValueError, Error): return None
    finally: 
        if cursor: cursor.close()

def get_specific_antecedente_by_date(connection, patient_id, fecha_str):
    """Obtiene el antecedente para un paciente en una fecha específica."""
    cursor = None
    try:
        fecha_sql = parse_date(fecha_str)
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = """
            SELECT * FROM antecedentes
            WHERE id_px = %s AND fecha = %s
            ORDER BY id_antecedente DESC
            LIMIT 1
        """
        cursor.execute(query, (patient_id, fecha_sql))
        data = cursor.fetchone()
        if data and data.get('calzado'): data['calzado'] = float(data['calzado'])
        return data
    except (ValueError, Error): return None
    finally: 
        if cursor: cursor.close()

def get_specific_seguimiento_by_date(connection, patient_id, fecha_str):
    """Obtiene el seguimiento para un paciente en una fecha específica."""
    cursor = None
    try:
        fecha_sql = parse_date(fecha_str)
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = """
            SELECT q.*, dr.nombre as nombre_doctor_seguimiento
            FROM quiropractico q
            LEFT JOIN dr ON q.id_dr = dr.id_dr
            WHERE q.id_px = %s AND q.fecha = %s
            ORDER BY q.id_seguimiento DESC
            LIMIT 1
        """
        cursor.execute(query, (patient_id, fecha_sql))
        return cursor.fetchone()
    except (ValueError, Error): return None
    finally: 
        if cursor: cursor.close()

def get_specific_revaloracion_by_date(connection, patient_id, fecha_str):
    """Obtiene la revaloración para un paciente en una fecha específica."""
    cursor = None
    try:
        fecha_sql = parse_date(fecha_str)
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = """
            SELECT r.*,
                   p.frente AS frente_path, p.lado AS lado1_path, p.postura_extra AS lado2_path,
                   p.pies AS pies_path, p.termografia AS termografia_path,
                   p.pies_frontal AS pies_frontal_path, p.pies_trasera AS pies_trasera_path
            FROM revaloraciones r
            LEFT JOIN postura p ON r.id_postura_asociado = p.id_postura
            WHERE r.id_px = %s AND r.fecha = %s
            ORDER BY id_revaloracion DESC
            LIMIT 1
        """
        cursor.execute(query, (patient_id, fecha_sql))
        return cursor.fetchone()
    except (ValueError, Error): return None
    finally: 
        if cursor: cursor.close()    

def get_revaloraciones_linked_to_anamnesis(connection, id_anamnesis_inicial):
    """
    Obtiene todos los registros de revaloración vinculados a un id_anamnesis_inicial específico,
    ordenados por fecha ascendente.
    """
    cursor = None
    try:
        query = """
            SELECT id_revaloracion, id_px, id_dr, fecha, id_anamnesis_inicial,
                   id_postura_asociado,
                   calif1_actual, calif2_actual, calif3_actual,
                   mejora_subjetiva_pct, notas_adicionales_reval,
                   diagrama_actual,
                   fecha_registro
            FROM revaloraciones
            WHERE id_anamnesis_inicial = %s
            ORDER BY fecha ASC, id_revaloracion ASC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_anamnesis_inicial,))
        return cursor.fetchall() or []
    except Error as e:
        print(f"Error obteniendo revaloraciones vinculadas a anamnesis ID {id_anamnesis_inicial}: {e}")
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
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = """
            SELECT * FROM anamnesis
            WHERE id_px = %s
            ORDER BY fecha ASC, id_anamnesis ASC
            LIMIT 1
        """
        cursor.execute(query, (patient_id,))
        return cursor.fetchone()
    except Error as e:
        print(f"Error obteniendo la primera anamnesis para paciente {patient_id}: {e}")
        return None
    finally:
        if cursor:
            cursor.close()

def get_first_postura_on_or_after_date(connection, patient_id, target_date_str):
    """
    Encuentra el registro de postura más ANTIGUO para un paciente
    en o DESPUÉS de una fecha específica. Si no encuentra, busca antes.
    """
    cursor = None
    try:
        # Convertir fecha objetivo
        try:
            target_date_sql = parse_date(target_date_str)
        except ValueError:
             return None

        cursor = connection.cursor(dictionary=True, buffered=True)

        # 1. Intenta buscar en o después de la fecha
        sql_after = """
            SELECT * FROM postura
            WHERE id_px = %s AND fecha >= %s
            ORDER BY fecha ASC, id_postura ASC
            LIMIT 1
        """
        cursor.execute(sql_after, (patient_id, target_date_sql))
        result = cursor.fetchone()

        # 2. Fallback: Buscar el más reciente antes de esa fecha
        if not result:
            sql_before = """
                SELECT * FROM postura
                WHERE id_px = %s AND fecha < %s
                ORDER BY fecha DESC, id_postura DESC
                LIMIT 1
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

def update_postura_ortho_notes(connection, id_postura, notas):
    """
    Actualiza ÚNICAMENTE el campo de notas ortopédicas de un registro de postura.
    """
    cursor = None
    if not id_postura: 
        return False

    try:
        cursor = connection.cursor()
        query = "UPDATE postura SET notas_pruebas_ortoneuro = %s WHERE id_postura = %s"
        cursor.execute(query, (notas, id_postura))
        return True 
    except Error as e:
        print(f"ERROR en update_postura_ortho_notes: {e}")
        return False
    finally:
        if cursor:
            cursor.close()

def get_latest_postura_on_or_before_date(connection, patient_id, target_date_str):
    """
    Obtiene el registro de postura más reciente para un paciente
    en o antes de una fecha específica.
    """
    cursor = None
    try:
        target_date_obj = parse_date(target_date_str)
        query = """
            SELECT * FROM postura
            WHERE id_px = %s AND fecha <= %s
            ORDER BY fecha DESC, id_postura DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id, target_date_obj))
        data = cursor.fetchone()
        if data: 
            for key in ['pie_cm', 'zapato_cm', 'fuerza_izq', 'fuerza_der']:
                if data.get(key): data[key] = float(data[key])
        return data
    except (ValueError, Error):
        return None
    finally:
        if cursor: cursor.close()

def get_latest_antecedente_on_or_before_date(connection, patient_id, target_date_str):
    """
    Obtiene el registro de antecedentes más reciente para un paciente
    en o antes de una fecha específica.
    """
    cursor = None
    try:
        target_date_obj = parse_date(target_date_str)
        query = """
            SELECT * FROM antecedentes
            WHERE id_px = %s AND fecha <= %s
            ORDER BY fecha DESC, id_antecedente DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id, target_date_obj))
        data = cursor.fetchone()
        if data and data.get('calzado'): 
             data['calzado'] = float(data['calzado'])
        return data
    except (ValueError, Error):
        return None
    finally:
        if cursor: cursor.close()
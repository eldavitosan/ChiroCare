from mysql.connector import Error
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from utils.date_manager import parse_date

# --- Productos ---
def get_all_productos_servicios(connection, include_inactive=True):
    cursor = None
    try:
        query = "SELECT * FROM productos_servicios" + ("" if include_inactive else " WHERE esta_activo = 1") + " ORDER BY adicional ASC, nombre ASC"
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query)
        prods = cursor.fetchall()
        for p in prods:
            p['esta_activo'] = bool(p.get('esta_activo', 0))
            for k in ['costo', 'venta']: p[k] = float(p.get(k) or 0)
        return prods or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_productos_servicios_venta(connection):
    cursor = None
    try:
        query = "SELECT id_prod, nombre, venta, costo FROM productos_servicios WHERE (adicional != 2 OR adicional IS NULL) AND esta_activo = 1 ORDER BY nombre ASC"
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query)
        prods = cursor.fetchall()
        for p in prods:
            for k in ['venta', 'costo']: p[k] = float(p.get(k) or 0)
        return prods or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_terapias_fisicas(connection):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id_prod, nombre FROM productos_servicios WHERE adicional = 2 AND esta_activo = 1 ORDER BY nombre ASC")
        return cursor.fetchall() or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_producto_costo_interno(connection, id_prod):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT costo FROM productos_servicios WHERE id_prod=%s", (id_prod,))
        res = cursor.fetchone()
        return float(res['costo']) if res and res['costo'] else 0.0
    except Error: return 0.0
    finally: 
        if cursor: cursor.close()

def add_producto_servicio(connection, data):
    cursor = None
    try:
        cursor = connection.cursor()
        query = "INSERT INTO productos_servicios (nombre, costo, venta, adicional, esta_activo) VALUES (%s, %s, %s, %s, %s)"
        cursor.execute(query, (data['nombre'], data.get('costo', 0), data['venta'], data['adicional'], int(data.get('esta_activo', 1))))
        return cursor.lastrowid
    except Error: return None
    finally: 
        if cursor: cursor.close()

# --- Planes de Cuidado ---
def save_plan_cuidado(connection, data):
    cursor = None
    if not all(k in data for k in ['id_px', 'id_dr', 'fecha']): return None
    cols = ['fecha', 'pb_diagnostico', 'visitas_qp', 'visitas_tf', 'etapa', 'inversion_total', 'promocion_pct', 'ahorro_calculado', 'adicionales_ids', 'notas_plan']
    try:
        cursor = connection.cursor()
        fecha_sql = parse_date(data.get('fecha'))
        id_update = data.get('id_plan')
        
        vals = [fecha_sql if c == 'fecha' else data.get(c) for c in cols]

        if id_update:
            cols_no_fecha = [c for c in cols if c != 'fecha']
            set_clause = "fecha=%s, " + ", ".join([f"`{c}`=%s" for c in cols_no_fecha])
            vals_upd = [fecha_sql] + [data.get(c) for c in cols_no_fecha] + [id_update]
            cursor.execute(f"UPDATE plancuidado SET {set_clause} WHERE id_plan=%s", tuple(vals_upd))
            return id_update
        else:
            ins_cols = ['id_px', 'id_dr'] + cols
            ph = ", ".join(['%s'] * len(ins_cols))
            vals_ins = [data['id_px'], data['id_dr']] + vals
            cursor.execute(f"INSERT INTO plancuidado ({', '.join([f'`{c}`' for c in ins_cols])}) VALUES ({ph})", tuple(vals_ins))
            return cursor.lastrowid
    except Error: return None
    finally: 
        if cursor: cursor.close()

def get_plan_cuidado_summary(connection, patient_id):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id_plan, fecha, pb_diagnostico FROM plancuidado WHERE id_px = %s ORDER BY fecha DESC, id_plan DESC", (patient_id,))
        return cursor.fetchall() or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_specific_plan_cuidado(connection, id_plan):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT * FROM plancuidado WHERE id_plan = %s", (id_plan,))
        data = cursor.fetchone()
        if data:
            for k in ['inversion_total', 'ahorro_calculado']: 
                if data.get(k): data[k] = float(data[k])
        return data
    except Error: return None
    finally: 
        if cursor: cursor.close()

def get_active_plans_for_patient(connection, patient_id):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id_plan, fecha, pb_diagnostico, visitas_qp, visitas_tf FROM plancuidado WHERE id_px = %s ORDER BY fecha DESC", (patient_id,))
        return cursor.fetchall() or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

# --- Recibos ---
def save_recibo(connection, datos_recibo, detalles_recibo):
    cursor = None
    try:
        cursor = connection.cursor()
        f_obj = parse_date(datos_recibo.get('fecha'))
        f_sql = f_obj.strftime('%Y-%m-%d') if isinstance(f_obj, (date, datetime)) else str(f_obj)

        sql_r = """INSERT INTO recibos (id_px, id_dr, fecha, subtotal_bruto, descuento_total, total_neto, pago_efectivo, pago_tarjeta, pago_transferencia, pago_otro, pago_otro_desc, notas) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
        vals_r = (datos_recibo['id_px'], datos_recibo['id_dr'], f_sql, datos_recibo.get('subtotal_bruto',0), datos_recibo.get('descuento_total',0), datos_recibo.get('total_neto',0), datos_recibo.get('pago_efectivo',0), datos_recibo.get('pago_tarjeta',0), datos_recibo.get('pago_transferencia',0), datos_recibo.get('pago_otro',0), datos_recibo.get('pago_otro_desc'), datos_recibo.get('notas'))
        cursor.execute(sql_r, vals_r)
        id_recibo = cursor.lastrowid

        sql_d = """INSERT INTO recibo_detalle (id_recibo, id_prod, cantidad, descripcion_prod, costo_unitario_venta, costo_unitario_compra, descuento_linea, subtotal_linea_neto) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        vals_d = []
        for d in detalles_recibo:
            costo_interno = get_producto_costo_interno(connection, d['id_prod'])
            vals_d.append((id_recibo, d['id_prod'], d['cantidad'], d.get('descripcion_prod'), d['costo_unitario_venta'], costo_interno, d.get('descuento_linea', 0), d['subtotal_linea_neto']))
        
        cursor.executemany(sql_d, vals_d)
        return id_recibo
    except Error as e:
        print(f"Error save_recibo: {e}")
        return None
    finally: 
        if cursor: cursor.close()

def get_recibos_summary(connection, patient_id):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT id_recibo, fecha, total_neto FROM recibos WHERE id_px = %s ORDER BY fecha DESC, id_recibo DESC", (patient_id,))
        res = cursor.fetchall()
        for r in res:
            if isinstance(r['fecha'], date): r['fecha'] = r['fecha'].strftime('%d/%m/%Y')
            if r['total_neto']: r['total_neto'] = float(r['total_neto'])
        return res or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_specific_recibo(connection, id_recibo):
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT r.*, dr.nombre as nombre_doctor FROM recibos r LEFT JOIN dr ON r.id_dr = dr.id_dr WHERE r.id_recibo = %s", (id_recibo,))
        recibo = cursor.fetchone()
        if not recibo: return None
        
        for k in ['subtotal_bruto', 'descuento_total', 'total_neto', 'pago_efectivo', 'pago_tarjeta', 'pago_transferencia', 'pago_otro']:
            if recibo.get(k): recibo[k] = float(recibo[k])

        cursor.execute("SELECT rd.*, ps.nombre as nombre_producto FROM recibo_detalle rd LEFT JOIN productos_servicios ps ON rd.id_prod = ps.id_prod WHERE rd.id_recibo = %s", (id_recibo,))
        detalles = cursor.fetchall()
        for d in detalles:
            for k in ['costo_unitario_venta', 'descuento_linea', 'subtotal_linea_neto']:
                if d.get(k): d[k] = float(d[k])
        
        recibo['detalles'] = detalles or []
        return recibo
    except Error: return None
    finally: 
        if cursor: cursor.close()

def get_producto_servicio_by_id(connection, id_prod):
    """Obtiene un producto/servicio específico por su ID."""
    cursor = None
    try:
        query = "SELECT id_prod, nombre, costo, venta, adicional, esta_activo FROM productos_servicios WHERE id_prod = %s"
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

def update_producto_servicio(connection, data):
    """Actualiza un producto/servicio existente."""
    cursor = None
    required_keys = ['id_prod', 'nombre', 'venta', 'adicional']
    if not all(key in data for key in required_keys):
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
            int(data.get('esta_activo', 1)),
            data['id_prod']
        )
        cursor.execute(query, values)
        # Retorna True si se ejecutó sin error, incluso si no cambió nada (rowcount=0)
        return True 
    except Error as e:
        print(f"Error actualizando producto/servicio ID {data.get('id_prod')}: {e}")
        return False
    finally:
        if cursor: cursor.close()

def set_producto_servicio_active_status(connection, id_prod, status):
    """Cambia el estado 'esta_activo' de un producto/servicio."""
    cursor = None
    try:
        cursor = connection.cursor()
        query = "UPDATE productos_servicios SET esta_activo = %s WHERE id_prod = %s"
        db_status = 1 if status else 0
        cursor.execute(query, (db_status, id_prod))
        return cursor.rowcount > 0
    except Error as e:
        print(f"Error cambiando estado de producto/servicio ID {id_prod}: {e}")
        return False
    finally:
        if cursor: cursor.close()

def get_specific_plan_cuidado_by_date(connection, patient_id, fecha_str):
    """Obtiene el plan de cuidado más reciente para un paciente en una fecha específica."""
    cursor = None
    try:
        # fecha_str ya viene como string 'dd/mm/yyyy' usualmente, pero aquí necesitamos pasarla directo
        # o parsearla si tu DB usa DATE. Asumiendo que parse_date maneja la conversión:
        fecha_sql = parse_date(fecha_str)
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = "SELECT * FROM plancuidado WHERE id_px = %s AND fecha = %s ORDER BY id_plan DESC LIMIT 1"
        cursor.execute(query, (patient_id, fecha_sql))
        data = cursor.fetchone()
        if data:
            for k in ['inversion_total', 'ahorro_calculado']:
                if data.get(k): data[k] = float(data[k])
        return data
    except Error: return None
    finally: 
        if cursor: cursor.close()

def get_productos_servicios_by_type(connection, tipo_adicional=1):
    """Obtiene productos filtrados por tipo (1=Adicionales, 2=Terapia Física, 0=Base)."""
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        # Asumimos que 'venta' es el costo al paciente
        query = "SELECT id_prod, nombre, venta as costo FROM productos_servicios WHERE adicional = %s ORDER BY nombre ASC"
        cursor.execute(query, (tipo_adicional,))
        productos = cursor.fetchall()
        if productos:
            for prod in productos:
                if prod.get('costo'): prod['costo'] = float(prod['costo'])
        return productos or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_productos_by_ids(connection, ids_list):
    """Obtiene detalles de productos basados en una lista de IDs."""
    cursor = None
    if not ids_list: return []
    try:
        # Validar IDs
        valid_ids = [int(i) for i in ids_list if str(i).isdigit()]
        if not valid_ids: return []
        
        placeholders = ', '.join(['%s'] * len(valid_ids))
        query = f"SELECT id_prod, nombre, venta, costo FROM productos_servicios WHERE id_prod IN ({placeholders}) ORDER BY nombre ASC"
        
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, tuple(valid_ids))
        productos = cursor.fetchall()
        
        for prod in productos:
            for k in ['venta', 'costo']: 
                if prod.get(k): prod[k] = float(prod[k])
        return productos or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_plan_cuidado_activo_para_paciente(connection, patient_id):
    """
    Busca un plan activo (donde las visitas realizadas < visitas planificadas).
    """
    cursor = None
    try:
        # Esta query compleja cuenta los seguimientos y los compara con el plan
        query = """
            SELECT pc.*, 
                   (SELECT COUNT(q.id_seguimiento) FROM quiropractico q WHERE q.id_plan_cuidado_asociado = pc.id_plan) as visitas_realizadas
            FROM plancuidado pc
            WHERE pc.id_px = %s 
            HAVING visitas_realizadas < pc.visitas_qp
            ORDER BY pc.fecha DESC, pc.id_plan DESC
            LIMIT 1
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        plan = cursor.fetchone()
        if plan:
            for k in ['visitas_qp', 'visitas_tf']: 
                if plan.get(k): plan[k] = int(plan[k])
            if plan.get('inversion_total'): plan['inversion_total'] = float(plan['inversion_total'])
        return plan
    except Error: return None
    finally: 
        if cursor: cursor.close()

def get_active_plan_status(connection, patient_id):
    """Obtiene el plan activo y calcula su estado detallado."""
    from .clinical import get_seguimientos_for_plan # Import local para evitar ciclo
    
    plan_data = get_plan_cuidado_activo_para_paciente(connection, patient_id)
    if not plan_data: return None

    seguimientos = get_seguimientos_for_plan(connection, plan_data['id_plan'])
    qp_consumidas = len(seguimientos)
    tf_consumidas = sum(1 for s in seguimientos if s.get('terapia') and s.get('terapia') != '0')

    plan_data['qp_consumidas'] = qp_consumidas
    plan_data['tf_consumidas'] = tf_consumidas
    plan_data['qp_restantes'] = (plan_data.get('visitas_qp') or 0) - qp_consumidas
    plan_data['tf_restantes'] = (plan_data.get('visitas_tf') or 0) - tf_consumidas
    
    return plan_data

def analizar_adicionales_plan(connection, id_plan):
    """Analiza estado de productos adicionales de un plan (adquiridos vs pendientes)."""
    cursor = None
    try:
        plan = get_specific_plan_cuidado(connection, id_plan)
        if not plan or not plan.get('adicionales_ids'): return []
        
        ids_str = plan['adicionales_ids'].strip('0,')
        if not ids_str: return []
        ids_list = [id for id in ids_str.split(',') if id.isdigit()]
        
        # Obtener nombres
        prods_info = {str(p['id_prod']): p for p in get_productos_by_ids(connection, ids_list)}
        
        # Obtener historial de compras del paciente
        historial = get_historial_compras_paciente(connection, plan['id_px'])
        
        status_list = []
        today = date.today()
        
        for pid in ids_list:
            p_data = prods_info.get(pid)
            if not p_data: continue
            
            # Buscar si se compró después de la fecha del plan (simplificado: buscamos si se compró alguna vez recientemente)
            compra = next((h for h in historial if str(h['id_prod']) == pid), None)
            
            estado = 'Falta adquirir'
            fecha_reno = None
            ultima_compra = None
            
            if compra:
                ultima_compra = compra['fecha_recibo'].strftime('%d/%m/%Y') if isinstance(compra['fecha_recibo'], date) else str(compra['fecha_recibo'])
                # Lógica simple de renovación
                if 'plantilla' in p_data['nombre'].lower():
                    # Aquí podrías añadir lógica de fechas complejas con relativedelta
                    estado = 'Adquirido' 
                else:
                    estado = 'Adquirido'

            status_list.append({
                'id_prod': pid,
                'nombre': p_data['nombre'],
                'status': estado,
                'ultima_compra': ultima_compra
            })
            
        return status_list
    except Error as e: 
        print(f"Error analizar_adicionales: {e}")
        return []
    finally: 
        if cursor: cursor.close()

def get_recibo_detalles_by_id(connection, id_recibo):
    """Obtiene los detalles (líneas) de un recibo."""
    cursor = None
    try:
        query = """
            SELECT rd.*, ps.nombre as nombre_producto_original
            FROM recibo_detalle rd
            LEFT JOIN productos_servicios ps ON rd.id_prod = ps.id_prod
            WHERE rd.id_recibo = %s ORDER BY rd.id_detalle ASC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_recibo,))
        detalles = cursor.fetchall()
        for d in detalles:
            for k in ['costo_unitario_venta', 'descuento_linea', 'subtotal_linea_neto', 'costo_unitario_compra']:
                if d.get(k): d[k] = float(d[k])
        return detalles or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_recibos_by_patient(connection, patient_id):
    """Obtiene todos los recibos de un paciente con un resumen de conceptos."""
    cursor = None
    try:
        query = """
            SELECT r.id_recibo, r.fecha, r.total_neto, dr.nombre AS nombre_doctor,
            (SELECT GROUP_CONCAT(COALESCE(NULLIF(TRIM(rd.descripcion_prod), ''), ps.nombre) SEPARATOR ', ')
             FROM recibo_detalle rd LEFT JOIN productos_servicios ps ON rd.id_prod = ps.id_prod
             WHERE rd.id_recibo = r.id_recibo) as conceptos_principales
            FROM recibos r
            LEFT JOIN dr ON r.id_dr = dr.id_dr
            WHERE r.id_px = %s ORDER BY r.fecha DESC, r.id_recibo DESC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (patient_id,))
        recibos = cursor.fetchall()
        for r in recibos:
            if isinstance(r['fecha'], date): r['fecha'] = r['fecha'].strftime('%d/%m/%Y')
            if r.get('total_neto'): r['total_neto'] = float(r['total_neto'])
        return recibos or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_recibo_by_id(connection, recibo_id):
    """Obtiene encabezado de recibo con datos extra para PDF."""
    cursor = None
    try:
        query = """
            SELECT r.*, dr.nombre as nombre_doctor_recibo, 
                   ce.nombre as nombre_centro, ce.direccion as direccion_centro,
                   ce.tel as telefono_centro, ce.cel as celular_centro
            FROM recibos r
            LEFT JOIN dr ON r.id_dr = dr.id_dr
            LEFT JOIN centro ce ON dr.centro = ce.id_centro
            WHERE r.id_recibo = %s
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (recibo_id,))
        data = cursor.fetchone()
        if data:
            if isinstance(data['fecha'], date): data['fecha'] = data['fecha'].strftime('%d/%m/%Y')
            for k in ['subtotal_bruto', 'descuento_total', 'total_neto', 'pago_efectivo', 'pago_tarjeta', 'pago_transferencia', 'pago_otro']:
                if data.get(k): data[k] = float(data[k])
        return data
    except Error: return None
    finally: 
        if cursor: cursor.close()

def get_historial_compras_paciente(connection, id_px):
    """Historial plano de ítems comprados."""
    cursor = None
    try:
        query = """
            SELECT r.fecha as fecha_recibo, rd.id_prod, rd.cantidad, 
                   COALESCE(rd.descripcion_prod, ps.nombre) as descripcion_item,
                   rd.subtotal_linea_neto
            FROM recibo_detalle rd
            JOIN recibos r ON rd.id_recibo = r.id_recibo
            LEFT JOIN productos_servicios ps ON rd.id_prod = ps.id_prod
            WHERE r.id_px = %s ORDER BY r.fecha DESC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query, (id_px,))
        return cursor.fetchall() or []
    except Error: return []
    finally: 
        if cursor: cursor.close()
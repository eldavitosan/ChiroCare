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

        # 1. Calcular Totales Financieros
        total_neto = float(datos_recibo.get('total_neto', 0))
        pago_efectivo = float(datos_recibo.get('pago_efectivo', 0))
        pago_tarjeta = float(datos_recibo.get('pago_tarjeta', 0))
        pago_transferencia = float(datos_recibo.get('pago_transferencia', 0))
        pago_otro = float(datos_recibo.get('pago_otro', 0))
        
        total_pagado_inicial = pago_efectivo + pago_tarjeta + pago_transferencia + pago_otro
        
        # 2. Determinar Deuda y Estado
        saldo_pendiente = total_neto - total_pagado_inicial
        estado = 'PENDIENTE' if saldo_pendiente > 0.01 else 'PAGADO'
        if saldo_pendiente < 0: saldo_pendiente = 0

        # 3. Insertar Cabecera del Recibo
        sql_r = """
            INSERT INTO recibos 
            (id_px, id_dr, fecha, subtotal_bruto, descuento_total, total_neto, 
             pago_efectivo, pago_tarjeta, pago_transferencia, pago_otro, pago_otro_desc, 
             notas, estado, saldo_pendiente) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        vals_r = (
            datos_recibo['id_px'], datos_recibo['id_dr'], f_sql, 
            datos_recibo.get('subtotal_bruto',0), datos_recibo.get('descuento_total',0), total_neto, 
            pago_efectivo, pago_tarjeta, pago_transferencia, pago_otro, datos_recibo.get('pago_otro_desc'), 
            datos_recibo.get('notas'), estado, saldo_pendiente
        )
        cursor.execute(sql_r, vals_r)
        id_recibo = cursor.lastrowid

        # 4. Insertar Detalles y ACTUALIZAR INVENTARIO (SOLO SI ES PRODUCTO)
        sql_d = """INSERT INTO recibo_detalle (id_recibo, id_prod, cantidad, descripcion_prod, costo_unitario_venta, costo_unitario_compra, descuento_linea, subtotal_linea_neto) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
        
        # Query para descontar stock
        sql_update_stock = """UPDATE productos_servicios SET stock_actual = stock_actual - %s WHERE id_prod = %s"""
        
        # Query para saber qué tipo de ítem es (0=Servicio, 1=Producto, 2=Terapia)
        sql_check_type = "SELECT adicional, costo FROM productos_servicios WHERE id_prod = %s"
        
        vals_d = []
        for d in detalles_recibo:
            id_prod = d['id_prod']
            cantidad = int(d['cantidad'])
            
            # Consultamos Tipo y Costo Interno al mismo tiempo
            cursor.execute(sql_check_type, (id_prod,))
            prod_info = cursor.fetchone()
            
            tipo_adicional = 0
            costo_interno = 0.0
            
            if prod_info:
                tipo_adicional = int(prod_info[0]) # 0, 1 o 2
                costo_interno = float(prod_info[1]) if prod_info[1] else 0.0
            
            # Agregamos al detalle del recibo (siempre se guarda el historial)
            vals_d.append((
                id_recibo, id_prod, cantidad, d.get('descripcion_prod'), 
                d['costo_unitario_venta'], costo_interno, d.get('descuento_linea', 0), d['subtotal_linea_neto']
            ))
            
            # --- CORRECCIÓN AQUÍ: Solo restamos stock si es TIPO 1 (Producto Físico) ---
            if tipo_adicional == 1:
                cursor.execute(sql_update_stock, (cantidad, id_prod))
            # ---------------------------------------------------------------------------
        
        cursor.executemany(sql_d, vals_d)

        # 5. Registrar el pago inicial en el historial
        if total_pagado_inicial > 0:
            nota_pago = "Pago inicial al crear el recibo"
            pagos_detalle = [
                ('Efectivo', pago_efectivo), ('Tarjeta', pago_tarjeta), 
                ('Transferencia', pago_transferencia), 
                (f"Otro ({datos_recibo.get('pago_otro_desc','Vales')})", pago_otro)
            ]
            
            sql_pago = "INSERT INTO recibo_pagos (id_recibo, fecha, monto, metodo_pago, notas) VALUES (%s, %s, %s, %s, %s)"
            
            for metodo, monto in pagos_detalle:
                if monto > 0:
                    cursor.execute(sql_pago, (id_recibo, f_sql, monto, metodo, nota_pago))

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
        query = """
            SELECT r.*, dr.nombre as nombre_doctor, 
                   ce.nombre as nombre_centro, ce.direccion as direccion_centro,
                   ce.tel as telefono_centro, ce.cel as celular_centro
            FROM recibos r
            LEFT JOIN dr ON r.id_dr = dr.id_dr
            LEFT JOIN centro ce ON dr.centro = ce.id_centro
            WHERE r.id_recibo = %s
        """
        cursor.execute(query, (id_recibo,))
        data = cursor.fetchone()
        
        if data:
            if isinstance(data['fecha'], date): 
                data['fecha'] = data['fecha'].strftime('%d/%m/%Y')
            
            # --- CORRECCIÓN: Convertir SIEMPRE, aunque sea 0 ---
            campos_moneda = [
                'subtotal_bruto', 'descuento_total', 'total_neto', 
                'pago_efectivo', 'pago_tarjeta', 'pago_transferencia', 
                'pago_otro', 'saldo_pendiente'
            ]
            
            for k in campos_moneda:
                # Usamos 'or 0' para convertir None a 0, y float() para todo lo demás
                data[k] = float(data.get(k) or 0)
        
        # Obtener los detalles (productos)
        cursor.execute("SELECT rd.*, ps.nombre as nombre_producto FROM recibo_detalle rd LEFT JOIN productos_servicios ps ON rd.id_prod = ps.id_prod WHERE rd.id_recibo = %s", (id_recibo,))
        detalles = cursor.fetchall()
        for d in detalles:
            for k in ['costo_unitario_venta', 'descuento_linea', 'subtotal_linea_neto']:
                d[k] = float(d.get(k) or 0)
        
        if data:
            data['detalles'] = detalles or []

            # ===============================================================
            # === BLOQUE NUEVO: OBLIGATORIO PARA QUE CUADREN LOS TOTALES ===
            # ===============================================================
            try:
                # Buscamos TODOS los pagos (el inicial y los abonos)
                sql_pagos = "SELECT * FROM recibo_pagos WHERE id_recibo = %s ORDER BY fecha ASC"
                cursor.execute(sql_pagos, (id_recibo,))
                pagos_raw = cursor.fetchall()
                
                # Convertimos números para que no den error en el PDF
                if pagos_raw:
                    for p in pagos_raw:
                        p['monto'] = float(p.get('monto') or 0)
                        if isinstance(p['fecha'], date): 
                            p['fecha'] = p['fecha'].strftime('%d/%m/%Y')
                    data['historial_pagos'] = pagos_raw
                else:
                    data['historial_pagos'] = []
            except Exception as e:
                print(f"Error leyendo pagos: {e}")
                data['historial_pagos'] = []
            # ===============================================================

        return data
    except Error as e: 
        print(f"Error en get_specific_recibo: {e}")
        return None
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
    """Obtiene todos los recibos con estado y saldo."""
    cursor = None
    try:
        # AGREGAMOS r.saldo_pendiente y r.estado A LA CONSULTA
        query = """
            SELECT r.id_recibo, r.fecha, r.total_neto, r.saldo_pendiente, r.estado, 
                   dr.nombre AS nombre_doctor,
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
            # Conversión segura
            r['total_neto'] = float(r.get('total_neto') or 0)
            r['saldo_pendiente'] = float(r.get('saldo_pendiente') or 0)
        return recibos or []
    except Error: return []
    finally: 
        if cursor: cursor.close()

def get_recibo_by_id(connection, recibo_id):
    """Obtiene encabezado de recibo con datos extra para PDF y Vista Web."""
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = """
            SELECT r.*, dr.nombre as nombre_doctor_recibo, 
                   ce.nombre as nombre_centro, ce.direccion as direccion_centro,
                   ce.tel as telefono_centro, ce.cel as celular_centro
            FROM recibos r
            LEFT JOIN dr ON r.id_dr = dr.id_dr
            LEFT JOIN centro ce ON dr.centro = ce.id_centro
            WHERE r.id_recibo = %s
        """
        cursor.execute(query, (recibo_id,))
        data = cursor.fetchone()
        
        if data:
            if isinstance(data['fecha'], date): 
                data['fecha'] = data['fecha'].strftime('%d/%m/%Y')
            
            # --- LISTA DE CAMPOS A CONVERTIR A FLOAT (Corrección aquí) ---
            campos_moneda = [
                'subtotal_bruto', 'descuento_total', 'total_neto', 
                'pago_efectivo', 'pago_tarjeta', 'pago_transferencia', 
                'pago_otro', 'saldo_pendiente' # <--- Agregado para evitar el error Decimal vs Float
            ]
            
            for k in campos_moneda:
                # Convertimos siempre, usando 0 si es None
                data[k] = float(data.get(k) or 0)
                
        return data
    except Error as e: 
        print(f"Error en get_recibo_by_id: {e}")
        return None
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

# --- GESTIÓN DE DEUDAS Y ABONOS (NUEVO) ---

def registrar_abono(connection, id_recibo, monto, metodo_pago, notas="Abono a cuenta"):
    """
    Registra un pago posterior a la fecha de venta.
    Actualiza el saldo pendiente y el estado del recibo.
    NO modifica inventario (ya se entregó el producto antes).
    """
    cursor = None
    try:
        cursor = connection.cursor()
        monto = float(monto)
        
        # 1. Insertar el pago en el historial
        sql_insert = "INSERT INTO recibo_pagos (id_recibo, fecha, monto, metodo_pago, notas) VALUES (%s, NOW(), %s, %s, %s)"
        cursor.execute(sql_insert, (id_recibo, monto, metodo_pago, notas))
        
        # 2. Actualizar el saldo del recibo padre
        sql_update = "UPDATE recibos SET saldo_pendiente = saldo_pendiente - %s WHERE id_recibo = %s"
        cursor.execute(sql_update, (monto, id_recibo))
        
        # 3. Verificar si ya se liquidó para cambiar estado a PAGADO
        cursor.execute("SELECT saldo_pendiente FROM recibos WHERE id_recibo = %s", (id_recibo,))
        row = cursor.fetchone()
        if row:
            saldo_actual = float(row[0])
            # Si el saldo es cero o negativo (por centavos), marcar PAGADO
            if saldo_actual <= 0.01:
                cursor.execute("UPDATE recibos SET estado = 'PAGADO', saldo_pendiente = 0 WHERE id_recibo = %s", (id_recibo,))
        
        return True
    except Error as e:
        print(f"Error registrando abono: {e}")
        return False
    finally:
        if cursor: cursor.close()

def get_historial_pagos_recibo(connection, id_recibo):
    """Obtiene la lista de todos los pagos (iniciales y abonos) de un recibo."""
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True, buffered=True)
        sql = "SELECT * FROM recibo_pagos WHERE id_recibo = %s ORDER BY fecha ASC, fecha_registro ASC"
        cursor.execute(sql, (id_recibo,))
        pagos = cursor.fetchall()
        for p in pagos:
            if p.get('monto'): p['monto'] = float(p['monto'])
            if isinstance(p['fecha'], date): p['fecha'] = p['fecha'].strftime('%d/%m/%Y')
        return pagos or []
    except Error: return []
    finally:
        if cursor: cursor.close()

def get_total_deuda_paciente(connection, patient_id):
    """Calcula cuánto debe el paciente en total (Suma de saldos pendientes)."""
    cursor = None
    try:
        cursor = connection.cursor()
        # Solo sumamos de recibos que estén marcados como PENDIENTE para ser más rápidos
        sql = "SELECT SUM(saldo_pendiente) FROM recibos WHERE id_px = %s AND estado = 'PENDIENTE'"
        cursor.execute(sql, (patient_id,))
        res = cursor.fetchone()
        return float(res[0]) if res and res[0] else 0.0
    except Error: return 0.0
    finally:
        if cursor: cursor.close()

# --- GESTIÓN DE INVENTARIO (NUEVO) ---

def actualizar_stock_producto(connection, id_prod, cantidad_agregar):
    """
    Suma stock (Entrada de almacén). 
    Para restar, enviar cantidad negativa, aunque save_recibo ya lo hace.
    """
    cursor = None
    try:
        cursor = connection.cursor()
        sql = "UPDATE productos_servicios SET stock_actual = stock_actual + %s WHERE id_prod = %s"
        cursor.execute(sql, (int(cantidad_agregar), id_prod))
        return True
    except Error: return False
    finally:
        if cursor: cursor.close()

def get_primer_recibo_pendiente(connection, patient_id):
    """Devuelve el ID del recibo pendiente más antiguo para ir a cobrarlo directo."""
    cursor = None
    try:
        cursor = connection.cursor()
        # Buscamos el primero por fecha ascendente (el más viejo)
        sql = "SELECT id_recibo FROM recibos WHERE id_px = %s AND estado = 'PENDIENTE' ORDER BY fecha ASC LIMIT 1"
        cursor.execute(sql, (patient_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"Error buscando recibo pendiente: {e}")
        return None
    finally:
        if cursor: cursor.close()


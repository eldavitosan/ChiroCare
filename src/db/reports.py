from mysql.connector import Error
from datetime import datetime, date, timedelta
from utils.date_manager import to_db_str, to_frontend_str
# Importamos funciones de otros módulos para reutilizar lógica en el resumen diario
from .finance import get_terapias_fisicas, get_specific_plan_cuidado, get_active_plans_for_patient
from .clinical import get_latest_anamnesis, get_seguimientos_for_plan

# --- Reportes Financieros ---

def get_ingresos_por_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id=None):
    cursor = None
    try:
        f_ini = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        f_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        diff = (f_fin - f_ini).days
        
        # Determinar agrupación
        if diff <= 45: 
            col, grp, fmt = "fecha", "fecha", "%Y-%m-%d"
        elif diff <= 730:
            col, grp, fmt = "DATE_FORMAT(fecha, '%Y-%m')", "periodo", "%Y-%m"
        else:
            col, grp, fmt = "YEAR(fecha)", "periodo", "%Y"
        
        sel_col = f"{col} AS periodo"
        params = [fecha_inicio_str, fecha_fin_str]
        filtro = ""
        if doctor_id:
            filtro = "AND id_dr = %s "
            params.append(doctor_id)

        query = f"""
            SELECT {sel_col}, SUM(total_neto) AS total_ingresos_periodo, COUNT(id_recibo) AS numero_recibos
            FROM recibos WHERE fecha BETWEEN %s AND %s {filtro}
            GROUP BY {grp} ORDER BY {grp} ASC
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        res = cursor.fetchall()
        for r in res:
            r['total_ingresos_periodo'] = float(r.get('total_ingresos_periodo') or 0)
            # Formatear periodo para el frontend si es fecha
            if isinstance(r['periodo'], date): r['periodo'] = r['periodo'].strftime('%d/%m/%Y')
            else: r['periodo'] = str(r['periodo'])
            r['formato_periodo_python'] = fmt
        return res
    except Exception as e:
        print(f"Error report ingresos: {e}")
        return []
    finally: 
        if cursor: cursor.close()

def get_ingresos_por_doctor_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id=None):
    cursor = None
    try:
        params = [fecha_inicio_str, fecha_fin_str]
        filtro = ""
        if doctor_id:
            filtro = "AND r.id_dr = %s "
            params.append(doctor_id)

        query = f"""
            SELECT d.id_dr, d.nombre AS nombre_doctor, SUM(r.total_neto) AS total_ingresos_doctor, COUNT(r.id_recibo) AS numero_recibos_doctor
            FROM recibos r JOIN dr d ON r.id_dr = d.id_dr
            WHERE r.fecha BETWEEN %s AND %s {filtro}
            GROUP BY d.id_dr, d.nombre
            ORDER BY total_ingresos_doctor DESC, d.nombre ASC
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        res = cursor.fetchall()
        for r in res:
            r['total_ingresos_doctor'] = float(r.get('total_ingresos_doctor') or 0)
        return res
    except Error as e:
        print(f"Error report ingresos doctor: {e}")
        return []
    finally: 
        if cursor: cursor.close()

def get_utilidad_estimada_por_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id=None):
    cursor = None
    try:
        f_ini = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        f_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        diff = (f_fin - f_ini).days
        
        if diff <= 45: col, grp, fmt = "r.fecha", "r.fecha", "%Y-%m-%d"
        elif diff <= 730: col, grp, fmt = "DATE_FORMAT(r.fecha, '%Y-%m')", "periodo", "%Y-%m"
        else: col, grp, fmt = "YEAR(r.fecha)", "periodo", "%Y"

        params = [fecha_inicio_str, fecha_fin_str]
        filtro = ""
        if doctor_id:
            filtro = "AND r.id_dr = %s "
            params.append(doctor_id)

        query = f"""
            SELECT {col} AS periodo,
            SUM((rd.cantidad * rd.costo_unitario_venta - IFNULL(rd.descuento_linea, 0)) - (rd.cantidad * IFNULL(rd.costo_unitario_compra, 0))) AS total_utilidad_estimada_periodo,
            COUNT(DISTINCT r.id_recibo) AS numero_recibos_con_utilidad, SUM(r.total_neto) AS total_ingresos_netos_periodo
            FROM recibos r JOIN recibo_detalle rd ON r.id_recibo = rd.id_recibo
            WHERE r.fecha BETWEEN %s AND %s {filtro}
            GROUP BY {grp} ORDER BY {grp} ASC
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        res = cursor.fetchall()
        for r in res:
            r['total_utilidad_estimada_periodo'] = float(r.get('total_utilidad_estimada_periodo') or 0)
            r['total_ingresos_netos_periodo'] = float(r.get('total_ingresos_netos_periodo') or 0)
            if isinstance(r['periodo'], date): r['periodo'] = r['periodo'].strftime('%d/%m/%Y')
            else: r['periodo'] = str(r['periodo'])
            r['formato_periodo_python'] = fmt
        return res
    except Exception as e:
        print(f"Error report utilidad: {e}")
        return []
    finally: 
        if cursor: cursor.close()

def get_utilidad_estimada_por_doctor_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id=None):
    cursor = None
    try:
        params = [fecha_inicio_str, fecha_fin_str]
        filtro = ""
        if doctor_id:
            filtro = "AND r.id_dr = %s "
            params.append(doctor_id)

        query = f"""
            SELECT dr.id_dr, dr.nombre AS nombre_doctor,
            SUM((rd.cantidad * rd.costo_unitario_venta - IFNULL(rd.descuento_linea, 0)) - (rd.cantidad * IFNULL(rd.costo_unitario_compra, 0))) AS total_utilidad_estimada_doctor,
            COUNT(DISTINCT r.id_recibo) AS numero_recibos_doctor, SUM(r.total_neto) AS total_ingresos_netos_doctor
            FROM recibos r JOIN recibo_detalle rd ON r.id_recibo = rd.id_recibo JOIN dr ON r.id_dr = dr.id_dr 
            WHERE r.fecha BETWEEN %s AND %s {filtro}
            GROUP BY dr.id_dr, dr.nombre ORDER BY total_utilidad_estimada_doctor DESC, dr.nombre ASC
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        res = cursor.fetchall()
        for r in res:
            r['total_utilidad_estimada_doctor'] = float(r.get('total_utilidad_estimada_doctor') or 0)
            r['total_ingresos_netos_doctor'] = float(r.get('total_ingresos_netos_doctor') or 0)
        return res
    except Error as e:
        print(f"Error report utilidad doctor: {e}")
        return []
    finally: 
        if cursor: cursor.close()

# --- Reportes Operativos ---

def get_pacientes_nuevos_por_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id=0):
    cursor = None
    try:
        f_ini = datetime.strptime(fecha_inicio_str, '%Y-%m-%d')
        f_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d')
        diff = (f_fin - f_ini).days
        
        params = [fecha_inicio_str, fecha_fin_str]
        filtro = ""
        if doctor_id != 0:
            filtro = "AND id_dr = %s "
            params.append(doctor_id)

        # 1. Lista
        query_lista = f"""
            SELECT id_px, nombre, apellidop, apellidom, fecha AS fecha_registro
            FROM datos_personales WHERE fecha BETWEEN %s AND %s {filtro} ORDER BY fecha ASC, id_px ASC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query_lista, tuple(params))
        lista = cursor.fetchall()

        # 2. Gráfica
        if diff <= 45: col, grp, fmt = "fecha", "fecha", "%d %b %Y"
        elif diff <= 730: col, grp, fmt = "DATE_FORMAT(fecha, '%Y-%m')", "periodo_grafica", "%b %Y"
        else: col, grp, fmt = "YEAR(fecha)", "periodo_grafica", "%Y"

        query_grafica = f"""
            SELECT {col} AS periodo_grafica, COUNT(id_px) AS conteo_pacientes_nuevos
            FROM datos_personales WHERE fecha BETWEEN %s AND %s {filtro}
            GROUP BY {grp} ORDER BY {grp} ASC
        """
        cursor.execute(query_grafica, tuple(params))
        grafica_raw = cursor.fetchall()
        
        grafica = []
        for item in grafica_raw:
            p_raw = item.get('periodo_grafica')
            label = str(p_raw)
            if isinstance(p_raw, date): label = p_raw.strftime('%d %b %Y')
            elif isinstance(p_raw, str) and len(p_raw) == 7: # YYYY-MM
                 try: label = datetime.strptime(p_raw, '%Y-%m').strftime('%b %Y')
                 except: pass
            
            grafica.append({'periodo_label': label, 'conteo': item.get('conteo_pacientes_nuevos', 0)})
            
        return lista, grafica
    except Exception as e:
        print(f"Error report pacientes nuevos: {e}")
        return [], []
    finally: 
        if cursor: cursor.close()

def get_pacientes_mas_frecuentes(connection, fecha_inicio_str, fecha_fin_str, limit=10):
    cursor = None
    try:
        f_ini = to_db_str(fecha_inicio_str)
        f_fin = to_db_str(fecha_fin_str)
        query = """
            SELECT dp.id_px, dp.nombre, dp.apellidop, dp.apellidom, COUNT(q.id_seguimiento) AS numero_seguimientos
            FROM datos_personales dp JOIN quiropractico q ON dp.id_px = q.id_px
            WHERE q.fecha BETWEEN %s AND %s
            GROUP BY dp.id_px, dp.nombre, dp.apellidop, dp.apellidom
            ORDER BY numero_seguimientos DESC, dp.apellidop ASC, dp.nombre ASC LIMIT %s
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (f_ini, f_fin, limit))
        return cursor.fetchall()
    except Exception as e:
        print(f"Error report frecuentes: {e}")
        return []
    finally: 
        if cursor: cursor.close()

def get_seguimientos_por_doctor_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id=0):
    cursor = None
    try:
        params = [fecha_inicio_str, fecha_fin_str]
        filtro = ""
        if doctor_id != 0:
            filtro = "AND q.id_dr = %s "
            params.append(doctor_id)

        query = f"""
            SELECT d.id_dr, d.nombre AS nombre_doctor, COUNT(q.id_seguimiento) AS numero_consultas
            FROM quiropractico q JOIN dr d ON q.id_dr = d.id_dr
            WHERE q.fecha BETWEEN %s AND %s {filtro}
            GROUP BY d.id_dr, d.nombre ORDER BY numero_consultas DESC, d.nombre ASC
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        return cursor.fetchall()
    except Error as e:
        print(f"Error report consultas doctor: {e}")
        return []
    finally: 
        if cursor: cursor.close()

def get_uso_planes_de_cuidado(connection, fecha_inicio_str, fecha_fin_str):
    cursor = None
    try:
        query_planes = """
            SELECT pc.id_plan, pc.id_px, dp.nombre AS nombre_paciente, dp.apellidop AS apellidop_paciente, 
                   dp.apellidom AS apellidom_paciente, pc.fecha AS fecha_creacion_plan, pc.pb_diagnostico, 
                   pc.visitas_qp AS visitas_qp_planificadas, dr.nombre AS nombre_doctor_plan
            FROM plancuidado pc JOIN datos_personales dp ON pc.id_px = dp.id_px LEFT JOIN dr ON pc.id_dr = dr.id_dr
            WHERE pc.fecha BETWEEN %s AND %s ORDER BY pc.fecha DESC, pc.id_plan DESC
        """
        cursor = connection.cursor(dictionary=True, buffered=True)
        cursor.execute(query_planes, (fecha_inicio_str, fecha_fin_str))
        planes = cursor.fetchall()
        if not planes: return {'total_creados': 0, 'activos': 0, 'completados': 0, 'lista_detallada_planes': []}

        activos, completados = 0, 0
        for plan in planes:
            cursor.execute("SELECT COUNT(id_seguimiento) as conteo FROM quiropractico WHERE id_plan_cuidado_asociado = %s", (plan['id_plan'],))
            realizadas = cursor.fetchone()['conteo']
            plan['visitas_qp_realizadas'] = realizadas
            
            if realizadas >= (plan.get('visitas_qp_planificadas') or 0):
                plan['estado_plan'] = 'Completado'; completados += 1
            else:
                plan['estado_plan'] = 'Activo'; activos += 1
            
            plan['nombre_completo_paciente'] = f"{plan['nombre_paciente']} {plan['apellidop_paciente']} {plan.get('apellidom_paciente','')}".strip()

        return {'total_creados': len(planes), 'activos': activos, 'completados': completados, 'lista_detallada_planes': planes}
    except Exception as e:
        print(f"Error report uso planes: {e}")
        return {'total_creados': 0, 'activos': 0, 'completados': 0, 'lista_detallada_planes': []}
    finally: 
        if cursor: cursor.close()

# --- Resumen Diario (Dashboard Principal) ---

def get_resumen_dia_anterior(connection):
    """Obtiene resumen de pacientes atendidos (Optimizado con 1 query de fecha)."""
    cursor = None
    resumen = []
    try:
        terapias = {str(t['id_prod']): t['nombre'] for t in get_terapias_fisicas(connection)}
        cursor = connection.cursor(dictionary=True)
        
        # 1. Encontrar última fecha con datos
        cursor.execute("SELECT MAX(fecha) as ultima_fecha FROM quiropractico WHERE fecha >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)")
        res = cursor.fetchone()
        
        if not res or not res['ultima_fecha']: return []
        
        fecha_target = res['ultima_fecha'].strftime('%Y-%m-%d') if isinstance(res['ultima_fecha'], (date, datetime)) else str(res['ultima_fecha'])
        
        # 2. Obtener Pacientes de esa fecha
        cursor.execute("SELECT DISTINCT id_px FROM quiropractico WHERE fecha = %s", (fecha_target,))
        p_ids = [row['id_px'] for row in cursor.fetchall()]
        
        for pid in p_ids:
            # Info básica
            cursor.execute("SELECT nombre, apellidop, apellidom FROM datos_personales WHERE id_px=%s", (pid,))
            pdb = cursor.fetchone()
            p_info = {'id_px': pid, 'nombre_completo': f"{pdb['nombre']} {pdb['apellidop']} {pdb.get('apellidom','')}".strip()}
            
            # Anamnesis
            anam = get_latest_anamnesis(connection, pid)
            if anam: p_info['condicion1_anamnesis'] = anam.get('condicion1', 'N/A')
            
            # --- CORRECCIÓN AQUÍ: Ampliamos la lista de segmentos en el SQL para que no salgan vacíos ---
            cursor.execute("""
                SELECT fecha, notas, terapia, id_plan_cuidado_asociado,
                CONCAT_WS(', ', 
                    IF(occipital != '', CONCAT('Occipital: ', occipital), NULL),
                    IF(atlas != '', CONCAT('Atlas: ', atlas), NULL),
                    IF(axis != '', CONCAT('Axis: ', axis), NULL),
                    IF(c3 != '', CONCAT('C3: ', c3), NULL),
                    IF(c4 != '', CONCAT('C4: ', c4), NULL),
                    IF(c5 != '', CONCAT('C5: ', c5), NULL),
                    IF(c6 != '', CONCAT('C6: ', c6), NULL),
                    IF(c7 != '', CONCAT('C7: ', c7), NULL),
                    IF(t1 != '', CONCAT('T1: ', t1), NULL),
                    IF(t2 != '', CONCAT('T2: ', t2), NULL),
                    IF(t3 != '', CONCAT('T3: ', t3), NULL),
                    IF(t4 != '', CONCAT('T4: ', t4), NULL),
                    IF(t5 != '', CONCAT('T5: ', t5), NULL),
                    IF(t6 != '', CONCAT('T6: ', t6), NULL),
                    IF(t7 != '', CONCAT('T7: ', t7), NULL),
                    IF(t8 != '', CONCAT('T8: ', t8), NULL),
                    IF(t9 != '', CONCAT('T9: ', t9), NULL),
                    IF(t10 != '', CONCAT('T10: ', t10), NULL),
                    IF(t11 != '', CONCAT('T11: ', t11), NULL),
                    IF(t12 != '', CONCAT('T12: ', t12), NULL),
                    IF(l1 != '', CONCAT('L1: ', l1), NULL),
                    IF(l2 != '', CONCAT('L2: ', l2), NULL),
                    IF(l3 != '', CONCAT('L3: ', l3), NULL),
                    IF(l4 != '', CONCAT('L4: ', l4), NULL),
                    IF(l5 != '', CONCAT('L5: ', l5), NULL),
                    IF(sacro != '', CONCAT('Sacro: ', sacro), NULL),
                    IF(iliaco_d != '', CONCAT('Ilíaco Der: ', iliaco_d), NULL),
                    IF(iliaco_i != '', CONCAT('Ilíaco Izq: ', iliaco_i), NULL),
                    IF(coxis != '', CONCAT('Coxis: ', coxis), NULL)
                ) as segmentos_resumidos
                FROM quiropractico WHERE id_px=%s ORDER BY fecha DESC, id_seguimiento DESC LIMIT 2
            """, (pid,))
            segs = cursor.fetchall()
            
            if segs:
                # --- 1. Procesar AYER (segs[0]) ---
                s_ayer = segs[0]
                t_ids = [tid for tid in s_ayer.get('terapia', '0,').split(',') if tid and tid != '0']
                t_txt = ', '.join([terapias.get(tid, tid) for tid in t_ids]) or 'Ninguna'
                
                f_str = s_ayer['fecha'].strftime('%d/%m/%Y') if isinstance(s_ayer['fecha'], date) else str(s_ayer['fecha'])
                p_info['seguimiento_ayer'] = {'fecha': f_str, 'segmentos': s_ayer['segmentos_resumidos'], 'terapias': t_txt, 'notas': s_ayer.get('notas')}

                # --- 2. Procesar ANTERIOR (segs[1]) - ESTO FALTABA ---
                if len(segs) > 1:
                    s_prev = segs[1]
                    t_ids_prev = [tid for tid in s_prev.get('terapia', '0,').split(',') if tid and tid != '0']
                    t_txt_prev = ', '.join([terapias.get(tid, tid) for tid in t_ids_prev]) or 'Ninguna'
                    f_str_prev = s_prev['fecha'].strftime('%d/%m/%Y') if isinstance(s_prev['fecha'], date) else str(s_prev['fecha'])
                    
                    p_info['seguimiento_anterior'] = {
                        'fecha': f_str_prev,
                        'segmentos': s_prev['segmentos_resumidos'],
                        'terapias': t_txt_prev
                    }
                
                # Estado del Plan
                id_plan = s_ayer.get('id_plan_cuidado_asociado')
                if not id_plan:
                    plans = get_active_plans_for_patient(connection, pid)
                    if plans: id_plan = plans[0]['id_plan']
                
                if id_plan:
                    plan = get_specific_plan_cuidado(connection, id_plan)
                    if plan:
                        all_segs = get_seguimientos_for_plan(connection, id_plan)
                        qp_used = len(all_segs)
                        tf_used = sum(1 for s in all_segs if s.get('terapia') and s.get('terapia') != '0')
                        p_info['plan_activo'] = {
                            'nombre': plan.get('pb_diagnostico'),
                            'qp_restantes': (plan.get('visitas_qp') or 0) - qp_used,
                            'tf_restantes': (plan.get('visitas_tf') or 0) - tf_used
                        }

            resumen.append(p_info)
        return resumen
    except Error as e:
        print(f"Error resumen: {e}")
        return []
    finally: 
        if cursor: cursor.close()


def count_seguimientos_hoy(connection, fecha_hoy_str):
    """
    Cuenta los seguimientos realizados en una fecha específica.
    Convierte la fecha al formato de DB antes de consultar.
    """
    cursor = None
    try:
        # Convertir 'dd/mm/yyyy' a 'yyyy-mm-dd'
        fecha_db = to_db_str(fecha_hoy_str)
        
        query = "SELECT COUNT(*) as total_seguimientos_hoy FROM quiropractico WHERE fecha = %s"
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (fecha_db,))
        result = cursor.fetchone()
        return result['total_seguimientos_hoy'] if result and 'total_seguimientos_hoy' in result else 0
    except Exception as e:
        print(f"Error contando seguimientos de hoy: {e}")
        return 0
    finally:
        if cursor:
            cursor.close()

# --- Reportes de Cobranza y Caja ---

def get_cuentas_por_cobrar(connection, doctor_id=0):
    """Obtiene lista de recibos con saldo pendiente."""
    cursor = None
    try:
        filtro_dr = ""
        params = []
        if doctor_id != 0:
            filtro_dr = "AND r.id_dr = %s"
            params.append(doctor_id)

        query = f"""
            SELECT r.id_recibo, r.fecha, r.total_neto, r.saldo_pendiente,
                   dp.id_px, dp.nombre, dp.apellidop, dp.apellidom, dp.cel,
                   dr.nombre as nombre_doctor
            FROM recibos r
            JOIN datos_personales dp ON r.id_px = dp.id_px
            JOIN dr ON r.id_dr = dr.id_dr
            WHERE r.saldo_pendiente > 0.01 {filtro_dr}
            ORDER BY r.fecha ASC
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, tuple(params))
        res = cursor.fetchall()
        
        for r in res:
            r['total_neto'] = float(r.get('total_neto') or 0)
            r['saldo_pendiente'] = float(r.get('saldo_pendiente') or 0)
            if isinstance(r['fecha'], date): r['fecha'] = r['fecha'].strftime('%d/%m/%Y')
            r['nombre_paciente'] = f"{r['nombre']} {r['apellidop']} {r.get('apellidom','')}".strip()
            
        return res
    except Exception as e:
        print(f"Error report cxc: {e}")
        return []
    finally:
        if cursor: cursor.close()

def get_corte_caja_detallado(connection, fecha_inicio_str, fecha_fin_str, doctor_id=0):
    """
    Suma los PAGOS REALES (Flujo de Efectivo) registrados en recibo_pagos.
    Incluye ventas de contado y abonos a deudas pasadas.
    """
    cursor = None
    try:
        params = [fecha_inicio_str, fecha_fin_str]
        filtro_dr = ""
        # Nota: recibo_pagos no tiene id_dr directo, lo unimos con recibos
        if doctor_id != 0:
            filtro_dr = "AND r.id_dr = %s"
            params.append(doctor_id)

        # 1. Totales por Método de Pago
        query_metodos = f"""
            SELECT rp.metodo_pago, SUM(rp.monto) as total_metodo
            FROM recibo_pagos rp
            JOIN recibos r ON rp.id_recibo = r.id_recibo
            WHERE rp.fecha BETWEEN %s AND %s {filtro_dr}
            GROUP BY rp.metodo_pago
            ORDER BY total_metodo DESC
        """
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query_metodos, tuple(params))
        totales_metodo = cursor.fetchall()
        
        # 2. Lista Detallada de Movimientos (AGREGADO r.id_px)
        query_detalle = f"""
            SELECT rp.id_pago, rp.fecha, rp.monto, rp.metodo_pago, rp.notas,
                   r.id_recibo, r.id_px, dp.nombre, dp.apellidop
            FROM recibo_pagos rp
            JOIN recibos r ON rp.id_recibo = r.id_recibo
            JOIN datos_personales dp ON r.id_px = dp.id_px
            WHERE rp.fecha BETWEEN %s AND %s {filtro_dr}
            ORDER BY rp.fecha DESC, rp.id_pago DESC
        """
        cursor.execute(query_detalle, tuple(params))
        movimientos = cursor.fetchall()

        # Formatear
        total_general = 0.0
        for t in totales_metodo:
            t['total_metodo'] = float(t.get('total_metodo') or 0)
            total_general += t['total_metodo']
            
        for m in movimientos:
            m['monto'] = float(m.get('monto') or 0)
            if isinstance(m['fecha'], date): m['fecha'] = m['fecha'].strftime('%d/%m/%Y')
            m['paciente'] = f"{m['nombre']} {m['apellidop']}"

        return {
            'totales_por_metodo': totales_metodo,
            'total_general': total_general,
            'movimientos': movimientos
        }

    except Exception as e:
        print(f"Error corte caja: {e}")
        return {'totales_por_metodo': [], 'total_general': 0.0, 'movimientos': []}
    finally:
        if cursor: cursor.close()
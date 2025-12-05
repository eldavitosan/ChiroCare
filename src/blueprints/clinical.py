import os
import json
import base64
from datetime import datetime, date
from flask import (
    Blueprint, render_template, request, redirect, jsonify, session, flash, url_for, Response, current_app
)
from io import BytesIO
from xhtml2pdf import pisa

# 1. IMPORTAR HERRAMIENTA DB
from db.connection import connect_to_db, get_db_cursor

# 2. IMPORTAR FUNCIONES DB
from db.clinical import (
    get_specific_anamnesis, save_anamnesis, get_anamnesis_summary,
    get_specific_anamnesis_by_date, get_postura_summary, get_specific_postura_by_date,
    save_postura, get_radiografias_for_postura, insert_radiografia,
    get_latest_anamnesis, get_seguimiento_summary, get_specific_seguimiento,
    get_specific_seguimiento_by_date, save_seguimiento, get_latest_postura_overall,
    get_latest_radiografias_overall, get_revaloraciones_linked_to_anamnesis,
    get_seguimientos_for_plan, get_first_postura_on_or_after_date,
    update_postura_ortho_notes, get_latest_postura_on_or_before_date,
    get_antecedentes_summary, get_specific_antecedente,
    get_specific_antecedente_by_date, save_antecedentes,
    get_revaloraciones_summary, get_specific_revaloracion, get_specific_revaloracion_by_date,
    save_revaloracion, get_latest_antecedente_on_or_before_date 
)
from db.patients import get_patient_by_id, mark_notes_as_seen, add_general_note
from db.finance import (
    get_active_plans_for_patient, get_terapias_fisicas, get_plan_cuidado_summary,
    get_specific_plan_cuidado, get_specific_plan_cuidado_by_date, save_plan_cuidado,
    get_productos_servicios_by_type, get_productos_by_ids, get_productos_servicios_venta,
    save_recibo, get_specific_recibo, get_plan_cuidado_activo_para_paciente,
    get_recibo_detalles_by_id, get_recibos_by_patient, get_recibo_by_id,
    get_active_plan_status, analizar_adicionales_plan, get_historial_compras_paciente,registrar_abono
)
from db.auth import get_all_doctors, get_centro_by_id, get_doctor_profile

# 3. IMPORTAR HERRAMIENTAS MIGRADAS A UTILS
from utils.clinical_tools import (
    generar_historia_con_ia, procesar_y_guardar_imagen_postura,
    generar_informe_postura_con_ia, generar_informe_podal_unificado,
    analizar_coordenadas_postura, analizar_coordenadas_podal,
    generar_informe_integral_con_ia, allowed_file,
    CONDICIONES_GENERALES_MAP, CONDICION_DIAGNOSTICADA_MAP, 
    DOLOR_INTENSO_MAP, TIPO_DOLOR_MAP, COMO_COMENZO_MAP, 
    DIAGRAMA_PUNTOS_COORDENADAS, ETAPA_CUIDADO_MAP
)

from forms import AntecedentesForm, AnamnesisForm
from utils.date_manager import to_frontend_str, to_db_str, parse_date, calculate_age
from decorators import login_required

clinical_bp = Blueprint('clinical', 
                        __name__, 
                        template_folder='../../templates',
                        url_prefix='/paciente/<int:patient_id>')

# --- RUTAS ---

@clinical_bp.route('/antecedentes', methods=['GET', 'POST'])
@login_required
def manage_antecedentes(patient_id): 
    # Configuración del formulario
    form = AntecedentesForm()
    form.cond_gen.choices = [(k, v) for k, v in CONDICIONES_GENERALES_MAP.items()]
    
    is_admin = session.get('is_admin', False)
    # Objetos de fecha para lógica
    today_date_obj = date.today()  
    today_str = to_frontend_str(today_date_obj)

    try:
        # Usamos el gestor de contexto para la conexión
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                flash('Error conectando a la base de datos.', 'danger')
                return redirect(url_for('main')) 

            patient = get_patient_by_id(connection, patient_id)
            if not patient:
                flash('Paciente no encontrado.', 'warning')
                return redirect(url_for('main')) 

            # --- Lógica POST (Guardar) ---
            if form.validate_on_submit():
                print("DEBUG: Formulario validado.")
                
                id_antecedente_editado_str = request.form.get('id_antecedente')
                id_antecedente_editado = int(id_antecedente_editado_str) if id_antecedente_editado_str else None

                is_editable_post = False
                fecha_para_guardar_str = today_str 

                if id_antecedente_editado:
                    record_original = get_specific_antecedente(connection, id_antecedente_editado)
                    if record_original and record_original.get('id_px') == patient_id:
                        fecha_original_registro_obj = record_original.get('fecha') 
                        
                        if is_admin or fecha_original_registro_obj == today_date_obj:
                            is_editable_post = True
                        
                        if is_admin and fecha_original_registro_obj:
                             fecha_para_guardar_str = to_frontend_str(fecha_original_registro_obj)
                    else:
                        flash("Error: No se encontró el registro original a actualizar.", "danger")
                        return redirect(url_for('clinical.manage_antecedentes', patient_id=patient_id))
                else: 
                    is_editable_post = True
                    fecha_para_guardar_str = today_str

                if not is_editable_post:
                    flash('No tiene permiso para modificar estos antecedentes en este momento.', 'warning')
                    return redirect(url_for('clinical.manage_antecedentes', patient_id=patient_id))

                data = {'id_px': patient_id}
                data['fecha'] = fecha_para_guardar_str 
                if id_antecedente_editado: 
                    data['id_antecedente'] = id_antecedente_editado

                data['peso'] = form.peso.data
                data['altura'] = form.altura.data
                data['calzado'] = form.calzado.data
                data['presion_alta'] = form.presion_alta.data
                data['trigliceridos'] = form.trigliceridos.data
                data['diabetes'] = form.diabetes.data
                data['agua'] = form.agua.data
                data['notas'] = form.notas.data
                
                selected_cond_gen = form.cond_gen.data if form.cond_gen.data else []
                data['condiciones_generales'] = '0,' + ','.join(selected_cond_gen) if selected_cond_gen else '0,'
                if data['condiciones_generales'] == '0,': data['condiciones_generales'] = '0,'

                selected_diag_codes = []
                if form.diag_dislocacion.data: selected_diag_codes.append(form.diag_dislocacion.data)
                if form.diag_fractura.data: selected_diag_codes.append(form.diag_fractura.data)
                if form.diag_tumor.data: selected_diag_codes.append(form.diag_tumor.data)
                if form.diag_cancer.data: selected_diag_codes.append(form.diag_cancer.data)
                if form.diag_embarazo.data: selected_diag_codes.append(form.diag_embarazo.data)
                if form.diag_osteo.data: selected_diag_codes.append(form.diag_osteo.data)
                if form.diag_implante.data: selected_diag_codes.append(form.diag_implante.data)
                if form.diag_ataque.data: selected_diag_codes.append(form.diag_ataque.data)
                if form.diag_epilepsia.data: selected_diag_codes.append(form.diag_epilepsia.data)
                
                data['condicion_diagnosticada'] = '0,' + ','.join(selected_diag_codes)
                if data['condicion_diagnosticada'] == '0,': data['condicion_diagnosticada'] = '0,'

                success = save_antecedentes(connection, data)

                if success:
                    flash('Antecedentes guardados exitosamente.', 'success')
                    return redirect(url_for('patient.patient_detail', patient_id=patient_id))
                else:
                    flash('Error al guardar los antecedentes.', 'danger')
                    fecha_cargada_obj_error = parse_date(fecha_para_guardar_str) or today_date_obj
                    
                    return render_template('antecedentes_form.html',
                                           patient=patient,
                                           all_records_info=get_antecedentes_summary(connection, patient_id),
                                           form=form, 
                                           is_editable=is_editable_post,
                                           loaded_id_antecedente=id_antecedente_editado,
                                           today_str=today_str,
                                           fecha_cargada=fecha_cargada_obj_error)

            # --- LÓGICA GET (Cargar datos) ---
            else:
                selected_id_str = request.args.get('selected_id')
                selected_id = int(selected_id_str) if selected_id_str else None

                all_records_info = get_antecedentes_summary(connection, patient_id) 

                current_data = None
                id_antecedente_a_cargar = None
                fecha_cargada_obj = today_date_obj 

                if selected_id: 
                    current_data = get_specific_antecedente(connection, selected_id)
                    if not (current_data and current_data.get('id_px') == patient_id):
                        flash("ID de antecedente seleccionado inválido.", "warning")
                        current_data = None 
                    else:
                        id_antecedente_a_cargar = selected_id
                        if current_data.get('fecha'): 
                            fecha_cargada_obj = current_data.get('fecha')

                if current_data is None:
                     current_data_today = get_specific_antecedente_by_date(connection, patient_id, today_str)
                     if current_data_today: 
                         current_data = current_data_today 
                         id_antecedente_a_cargar = current_data.get('id_antecedente')
                         if current_data.get('fecha'): 
                            fecha_cargada_obj = current_data.get('fecha')
                     else: 
                         current_data = {} 
                         id_antecedente_a_cargar = None
                         fecha_cargada_obj = today_date_obj 

                is_editable = is_admin or fecha_cargada_obj == today_date_obj
                
                # Pre-poblar el formulario
                current_data_for_form = current_data.copy()

                cg_codes_str = current_data.get('condiciones_generales', '0,')
                current_data_for_form['cond_gen'] = [code for code in cg_codes_str.split(',') if code != '0']

                cd_codes_list = [code for code in current_data.get('condicion_diagnosticada', '0,').split(',') if code != '0']
                if cd_codes_list:
                    if '1' in cd_codes_list: current_data_for_form['diag_dislocacion'] = '1'
                    if '2' in cd_codes_list: current_data_for_form['diag_dislocacion'] = '2'
                    if '3' in cd_codes_list: current_data_for_form['diag_fractura'] = '3'
                    if '4' in cd_codes_list: current_data_for_form['diag_fractura'] = '4T'
                    if '5' in cd_codes_list: current_data_for_form['diag_tumor'] = '5'
                    if '6' in cd_codes_list: current_data_for_form['diag_tumor'] = '6'
                    if '7' in cd_codes_list: current_data_for_form['diag_cancer'] = '7'
                    if '8' in cd_codes_list: current_data_for_form['diag_cancer'] = '8'
                    if '9' in cd_codes_list: current_data_for_form['diag_embarazo'] = '9'
                    if '10' in cd_codes_list: current_data_for_form['diag_embarazo'] = '10'
                    if '11' in cd_codes_list: current_data_for_form['diag_osteo'] = '11'
                    if '12' in cd_codes_list: current_data_for_form['diag_osteo'] = '12'
                    if '13' in cd_codes_list: current_data_for_form['diag_implante'] = '13'
                    if '14' in cd_codes_list: current_data_for_form['diag_implante'] = '14'
                    if '15' in cd_codes_list: current_data_for_form['diag_ataque'] = '15'
                    if '16' in cd_codes_list: current_data_for_form['diag_ataque'] = '16'
                    if '17' in cd_codes_list: current_data_for_form['diag_epilepsia'] = '17'
                    if '18' in cd_codes_list: current_data_for_form['diag_epilepsia'] = '18'
                
                # Cargar datos en el formulario WTForms
                form.process(data=current_data_for_form)
                form.cond_gen.choices = [(k, v) for k, v in CONDICIONES_GENERALES_MAP.items()]
                
                return render_template('antecedentes_form.html',
                                       patient=patient,
                                       all_records_info=all_records_info,
                                       form=form, 
                                       is_editable=is_editable,
                                       loaded_id_antecedente=id_antecedente_a_cargar,
                                       today_str=today_str, 
                                       fecha_cargada=fecha_cargada_obj) 

    except Exception as e:
        print(f"Error en manage_antecedentes (PID {patient_id}): {e}") 
        flash('Ocurrió un error inesperado al gestionar antecedentes.', 'danger')
        safe_redirect_url = url_for('patient.patient_detail', patient_id=patient_id) 
        return redirect(safe_redirect_url)
        
@clinical_bp.route('/anamnesis', methods=['GET', 'POST'])
@login_required
def manage_anamnesis(patient_id): 
    # Configuración inicial del formulario (fuera de la BD)
    form = AnamnesisForm()
    form.dolor_intenso_chk.choices = [(k, v) for k, v in DOLOR_INTENSO_MAP.items()]
    form.tipo_dolor_chk.choices = [(k, v) for k, v in TIPO_DOLOR_MAP.items()]
    
    is_admin = session.get('is_admin', False)
    today_str = to_frontend_str(date.today())
    today_date_obj = date.today()

    try:
        # Usamos el gestor de contexto para la conexión segura
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                flash('Error conectando a la base de datos.', 'danger')
                return redirect(url_for('main')) 

            patient = get_patient_by_id(connection, patient_id)
            if not patient:
                flash('Paciente no encontrado.', 'warning')
                return redirect(url_for('main')) 

            # --- LÓGICA POST (Guardar) ---
            if form.validate_on_submit():
                id_anamnesis_editado_str = request.form.get('id_anamnesis') 
                id_anamnesis_editado = int(id_anamnesis_editado_str) if id_anamnesis_editado_str else None

                is_editable_post = False
                fecha_para_guardar_str = today_str 
                fecha_original_registro_obj = None

                if id_anamnesis_editado:
                    record_original = get_specific_anamnesis(connection, id_anamnesis_editado)
                    if record_original and record_original.get('id_px') == patient_id:
                        fecha_original_registro_obj = record_original.get('fecha')
                        if not isinstance(fecha_original_registro_obj, date):
                             fecha_original_registro_obj = parse_date(str(fecha_original_registro_obj))

                        if is_admin or fecha_original_registro_obj == today_date_obj:
                            is_editable_post = True
                        
                        if is_admin and fecha_original_registro_obj:
                             fecha_para_guardar_str = to_frontend_str(fecha_original_registro_obj)
                    else:
                        flash("Error: No se encontró el registro original a actualizar.", "danger")
                        return redirect(url_for('clinical.manage_anamnesis', patient_id=patient_id))
                else: 
                    is_editable_post = True
                    fecha_para_guardar_str = today_str

                if not is_editable_post:
                    flash('No tiene permiso para modificar esta anamnesis en este momento.', 'warning')
                    return redirect(url_for('clinical.manage_anamnesis', patient_id=patient_id))

                data = {'id_px': patient_id}
                data['fecha'] = fecha_para_guardar_str 
                if id_anamnesis_editado: 
                    data['id_anamnesis'] = id_anamnesis_editado
                
                data['condicion1'] = form.condicion1.data
                data['calif1'] = form.calif1.data
                data['condicion2'] = form.condicion2.data
                data['calif2'] = form.calif2.data
                data['condicion3'] = form.condicion3.data
                data['calif3'] = form.calif3.data
                data['como_comenzo'] = form.como_comenzo.data
                data['primera_vez'] = form.primera_vez.data
                data['alivia'] = form.alivia.data
                data['empeora'] = form.empeora.data
                data['como_ocurrio'] = form.como_ocurrio.data
                data['actividades_afectadas'] = form.actividades_afectadas.data
                data['diagrama'] = request.form.get('diagrama_puntos', '0,')
                if not data['diagrama']: data['diagrama'] = '0,'
                
                selected_dolor_intenso_ids = form.dolor_intenso_chk.data
                data['dolor_intenso'] = '0,' + ','.join(selected_dolor_intenso_ids)
                if data['dolor_intenso'] == '0,': data['dolor_intenso'] = '0,'
                
                selected_tipo_dolor_ids = form.tipo_dolor_chk.data
                data['tipo_dolor'] = '0,' + ','.join(selected_tipo_dolor_ids)
                if data['tipo_dolor'] == '0,': data['tipo_dolor'] = '0,'
                
                mapas_para_ia = {
                    'dolor_intenso': DOLOR_INTENSO_MAP,
                    'tipo_dolor': TIPO_DOLOR_MAP,
                    'como_comenzo': COMO_COMENZO_MAP
                }
                # Llamada a función auxiliar (definida en clinical_tools)
                data['historia'] = generar_historia_con_ia(data, mapas_para_ia)
                
                success = save_anamnesis(connection, data)

                if success == "duplicate":
                    flash(f"Error: Ya existe un registro para la fecha {data.get('fecha')}.", 'danger')
                elif success:
                    flash('Anamnesis guardada exitosamente.', 'success')
                    return redirect(url_for('patient.patient_detail', patient_id=patient_id))
                else:
                    flash('Error al guardar la anamnesis.', 'danger')
                
                # En caso de error, re-renderizar
                all_records_info = get_anamnesis_summary(connection, patient_id)
                selected_diagrama_puntos = data.get('diagrama', '0,').split(',')
                try: fecha_cargada_obj_error = parse_date(fecha_para_guardar_str) or today_date_obj
                except (ValueError, TypeError): fecha_cargada_obj_error = today_date_obj
                
                return render_template('anamnesis_form.html',
                                       patient=patient, all_records_info=all_records_info, form=form, 
                                       is_editable=is_editable_post, loaded_id_anamnesis=id_anamnesis_editado,
                                       today_str=today_str, DIAGRAMA_PUNTOS_COORDENADAS=DIAGRAMA_PUNTOS_COORDENADAS,
                                       selected_diagrama_puntos=selected_diagrama_puntos,
                                       fecha_cargada=fecha_cargada_obj_error, current_data=data)

            # --- LÓGICA GET (Ver / Cargar) ---
            else: 
                all_records_info = get_anamnesis_summary(connection, patient_id)
                selected_diagrama_puntos = ['0']
                fecha_cargada_obj = today_date_obj
                id_anamnesis_a_cargar = None
                is_editable = True
                current_data = None 

                # Si venimos de un POST fallido (validación)
                if request.method == 'POST':
                    id_anamnesis_a_cargar_str = request.form.get('id_anamnesis')
                    try: id_anamnesis_a_cargar = int(id_anamnesis_a_cargar_str) if id_anamnesis_a_cargar_str else None
                    except ValueError: id_anamnesis_a_cargar = None
                    
                    fecha_cargada_str = request.form.get('fecha_cargada', today_str)
                    is_editable = is_admin or (fecha_cargada_str == today_str)
                    selected_diagrama_puntos = request.form.get('diagrama_puntos', '0,').split(',')
                    try: fecha_cargada_obj = parse_date(fecha_cargada_str) or today_date_obj
                    except (ValueError, TypeError): fecha_cargada_obj = today_date_obj

                # Si es GET puro
                else:
                    selected_id_str = request.args.get('selected_id')
                    selected_id = int(selected_id_str) if selected_id_str else None

                    if selected_id:
                        current_data = get_specific_anamnesis(connection, selected_id)
                        if not (current_data and current_data.get('id_px') == patient_id):
                            flash("ID seleccionado inválido.", "warning")
                            current_data = None
                        else:
                            id_anamnesis_a_cargar = selected_id
                            fecha_cargada_obj = current_data.get('fecha') or today_date_obj
                    
                    if current_data is None:
                         current_data_today = get_specific_anamnesis_by_date(connection, patient_id, today_str)
                         if current_data_today: 
                             current_data = current_data_today
                             id_anamnesis_a_cargar = current_data.get('id_anamnesis')
                             fecha_cargada_obj = current_data.get('fecha') or today_date_obj
                         else: 
                             current_data = {} 
                             id_anamnesis_a_cargar = None
                             fecha_cargada_obj = today_date_obj 

                    is_editable = is_admin or fecha_cargada_obj == today_date_obj
                    
                    # Pre-poblar el formulario con datos cargados
                    current_data_for_form = current_data.copy()
                    current_data_for_form['diagrama_puntos'] = current_data.get('diagrama', '0,')
                    
                    # Cargar Checkboxes
                    di_codes_str = current_data.get('dolor_intenso', '0,')
                    current_data_for_form['dolor_intenso_chk'] = [code for code in di_codes_str.split(',') if code != '0']
                    td_codes_str = current_data.get('tipo_dolor', '0,')
                    current_data_for_form['tipo_dolor_chk'] = [code for code in td_codes_str.split(',') if code != '0']
                    
                    form.process(data=current_data_for_form) 
                    # Re-asignar choices después de process() es buena práctica en WTForms dinámicos
                    form.dolor_intenso_chk.choices = [(k, v) for k, v in DOLOR_INTENSO_MAP.items()]
                    form.tipo_dolor_chk.choices = [(k, v) for k, v in TIPO_DOLOR_MAP.items()]
                    
                    selected_diagrama_puntos = current_data.get('diagrama', '0,').split(',')

                return render_template('anamnesis_form.html',
                                       patient=patient,
                                       all_records_info=all_records_info,
                                       form=form, 
                                       is_editable=is_editable,
                                       loaded_id_anamnesis=id_anamnesis_a_cargar,
                                       today_str=today_str,
                                       DIAGRAMA_PUNTOS_COORDENADAS=DIAGRAMA_PUNTOS_COORDENADAS,
                                       fecha_cargada=fecha_cargada_obj,
                                       selected_diagrama_puntos=selected_diagrama_puntos,
                                       current_data=current_data
                                      )

    except Exception as e:
        print(f"Error en manage_anamnesis (PID {patient_id}): {e}") 
        flash('Ocurrió un error inesperado al gestionar la anamnesis.', 'danger')
        safe_redirect_url = url_for('patient.patient_detail', patient_id=patient_id) 
        return redirect(safe_redirect_url)

@clinical_bp.route('/pruebas', methods=['GET', 'POST'])
@login_required
def manage_pruebas(patient_id):
    today_str = to_frontend_str(date.today())
    is_admin = session.get('is_admin', False)
    id_dr_actual = session.get('id_dr')

    if not id_dr_actual:
        flash("Error de sesión.", "danger")
        return redirect(url_for('auth.login'))

    try:
        # Usamos el gestor de contexto para la conexión
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection: 
                flash('Error conectando a la base de datos.', 'danger')
                return redirect(url_for('main'))
            
            patient = get_patient_by_id(connection, patient_id)
            if not patient:
                 flash('Paciente no encontrado.', 'warning')
                 return redirect(url_for('main'))

            # --- Lógica POST (Guardado Granular) ---
            if request.method == 'POST':
                # Deshabilitar autocommit para transacción manual compleja
                connection.autocommit = False 
                print(f"INFO: POST pruebas para PID {patient_id}")

                try:
                    fecha_guardada = request.form.get('fecha_cargada', today_str)
                    id_postura_editado = int(request.form.get('id_postura')) if request.form.get('id_postura') else None
                    
                    record_original = get_specific_postura_by_date(connection, patient_id, fecha_guardada)
                    existing_data = record_original if record_original else {}
                    id_postura_existente = existing_data.get('id_postura')

                    if id_postura_editado and id_postura_editado != id_postura_existente:
                         raise ValueError("Inconsistencia de ID.")

                    # Permisos
                    es_hoy = (fecha_guardada == today_str)
                    puede_editar_todo = is_admin or es_hoy
                    record_exists = (id_postura_existente is not None)
                    puede_anadir_rx = is_admin or record_exists

                    if not (puede_editar_todo or (not puede_editar_todo and record_exists)):
                         if not is_admin and not es_hoy: raise PermissionError("No puede crear registros pasados.")
                         raise PermissionError("Acción no permitida.")

                    # Preparar datos base
                    data_to_save = {'id_px': patient_id, 'fecha': fecha_guardada}
                    if id_postura_existente: data_to_save['id_postura'] = id_postura_existente
                    else: data_to_save['fecha'] = today_str

                    # Procesar campos texto/número (Lógica Granular Restaurada)
                    campos = {
                        'tipo_calzado': (request.form.get('tipo_calzado', '').strip(), 'tipo_calzado'),
                        'pie_cm': (request.form.get('pie_cm'), 'pie_cm'),
                        'zapato_cm': (request.form.get('zapato_cm'), 'zapato_cm'),
                        'fuerza_izq': (request.form.get('fuerza_izq'), 'fuerza_izq'),
                        'fuerza_der': (request.form.get('fuerza_der'), 'fuerza_der'),
                        'oxigeno': (request.form.get('oxigeno'), 'oxigeno'),
                        'notas_plantillas': (request.form.get('notas_plantillas', '').strip(), 'notas_plantillas'),
                        'notas_pruebas_ortoneuro': (request.form.get('notas_pruebas_ortoneuro', '').strip(), 'notas_pruebas_ortoneuro')
                    }

                    for val, key in campos.values():
                        orig_val = existing_data.get(key)
                        orig_has = (orig_val is not None) if key in ['pie_cm', 'zapato_cm', 'fuerza_izq', 'fuerza_der', 'oxigeno'] else bool(orig_val)
                        
                        save_val = False
                        if puede_editar_todo: save_val = True
                        elif not orig_has and val: save_val = True # Solo llenar huecos si no es admin/hoy

                        if save_val:
                            if key in ['pie_cm', 'zapato_cm', 'fuerza_izq', 'fuerza_der']:
                                data_to_save[key] = float(val) if val else None
                            elif key == 'oxigeno':
                                data_to_save[key] = int(val) if val else None
                            else:
                                data_to_save[key] = val if val else None

                    # Procesar Imágenes (Lógica Completa Restaurada)
                    img_map = {
                        'foto_frente': ('frente', 'frontal'), 'foto_lado': ('lado', 'lateral_izq'), 
                        'foto_postura3': ('postura_extra', 'lateral_der'), 'foto_termografia': ('termografia', None), 
                        'foto_pisada': ('pies', None), 'foto_pies_frontal': ('pies_frontal', None), 
                        'foto_pies_trasera': ('pies_trasera', None) 
                    }

                    for input_name, (db_col, view) in img_map.items():
                        file = request.files.get(input_name)
                        orig_path = existing_data.get(db_col)
                        
                        if file and file.filename != '' and allowed_file(file.filename):
                            if puede_editar_todo or not orig_path:
                                base_name = secure_filename(f"{patient_id}_{data_to_save['fecha'].replace('/', '-')}_{db_col}")
                                new_path, err = procesar_y_guardar_imagen_postura(file, current_app.config['UPLOAD_FOLDER'], base_name, view_type=view)
                                if err: flash(f"Advertencia {input_name}: {err}", "warning")
                                data_to_save[db_col] = new_path
                        else:
                            # Mantener original si no se sube nuevo (importante para UPDATE)
                            if db_col in existing_data and db_col not in data_to_save:
                                 # No hace falta añadirlo a data_to_save si save_postura hace UPDATE selectivo,
                                 # pero si hace UPDATE total, deberíamos mantenerlo.
                                 # Asumiendo save_postura maneja esto o data_to_save es parcial.
                                 pass 

                    # Guardar Postura Base
                    id_postura_res = save_postura(connection, data_to_save)
                    if not id_postura_res: raise Exception("Error al guardar postura.")

                    # Guardar RX
                    if puede_anadir_rx:
                        rx_files = request.files.getlist('fotos_rx')
                        for i, f in enumerate(rx_files):
                            if f and allowed_file(f.filename):
                                base = secure_filename(f"{patient_id}_{data_to_save['fecha'].replace('/', '-')}_rx_{i}")
                                path, _ = procesar_y_guardar_imagen_postura(f, current_app.config['RX_UPLOAD_FOLDER'], base, view_type=None)
                                if path: insert_radiografia(connection, id_postura_res, path)

                    connection.commit()
                    flash('Pruebas guardadas exitosamente.', 'success')
                    return redirect(url_for('clinical.manage_pruebas', patient_id=patient_id, fecha=data_to_save['fecha']))

                except Exception as e:
                    print(f"ERROR POST pruebas: {e}")
                    try: connection.rollback()
                    except Error: pass
                    flash(f"Error: {e}", 'danger')
                    return redirect(url_for('clinical.manage_pruebas', patient_id=patient_id))
                finally:
                    if connection: connection.autocommit = True

            # --- Lógica GET (Ver) ---
            else:
                sel_date = request.args.get('fecha')
                avail_dates = get_postura_summary(connection, patient_id)
                
                target_date = None
                if sel_date == 'hoy': target_date = today_str
                elif sel_date and sel_date in avail_dates: target_date = sel_date
                elif avail_dates: target_date = avail_dates[0]
                else: target_date = today_str

                curr_data = get_specific_postura_by_date(connection, patient_id, target_date) or {}
                id_curr = curr_data.get('id_postura')
                rx_list = get_radiografias_for_postura(connection, id_curr) if id_curr else []
                
                is_fully_editable = is_admin or (target_date == today_str)
                can_add_rx = is_admin or (id_curr is not None)

                return render_template('pruebas_form.html',
                                       patient=patient, available_dates=avail_dates,
                                       current_data=curr_data, current_rx_list=rx_list,
                                       is_fully_editable=is_fully_editable, can_add_rx=can_add_rx,
                                       is_admin=is_admin, loaded_date=target_date, today_str=today_str)

    except Exception as e:
        print(f"Error general manage_pruebas: {e}")
        flash('Error inesperado.', 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@clinical_bp.route('/seguimiento', methods=['GET', 'POST'])
@login_required
def manage_seguimiento(patient_id):
    connection = None
    record_original = None 
    id_dr_para_guardar = session.get('id_dr') 

    try:
        # Usamos el gestor de contexto para la conexión
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection: 
                flash('Error conectando a la base de datos.', 'danger')
                return redirect(url_for('main'))
            
            patient = get_patient_by_id(connection, patient_id)
            if not patient:
                 flash('Paciente no encontrado.', 'warning')
                 return redirect(url_for('main'))

            is_admin = session.get('is_admin', False)
            today_str = datetime.now().strftime('%d/%m/%Y')
            id_dr_actual_sesion = session.get('id_dr') 
            nombre_dr_actual_sesion = session.get('nombre_dr', 'Doctor Desconocido') 

            if not id_dr_actual_sesion:
                 flash("Error de sesión. No se pudo identificar al doctor.", "danger")
                 return redirect(url_for('auth.login'))

            active_plans_list = get_active_plans_for_patient(connection, patient_id)

            # --- Lógica POST (Guardar) ---
            if request.method == 'POST':
                id_seguimiento_editado_str = request.form.get('id_seguimiento')
                id_seguimiento_editado = int(id_seguimiento_editado_str) if id_seguimiento_editado_str else None
                fecha_guardada = request.form.get('fecha_cargada', today_str)
                
                id_dr_para_guardar = id_dr_actual_sesion 

                # Deshabilitamos autocommit para transacción manual compleja
                connection.autocommit = False 

                try:
                    if id_seguimiento_editado:
                        record_original = get_specific_seguimiento(connection, id_seguimiento_editado)
                        # Validación simplificada
                        if not (record_original and record_original.get('id_px') == patient_id):
                             raise ValueError("Error: El registro de seguimiento a editar no existe o no coincide con el paciente.")
                        
                        if is_admin and record_original.get('id_dr'): 
                            id_dr_para_guardar = record_original.get('id_dr')

                    elif not (fecha_guardada == today_str): 
                        record_original = get_specific_seguimiento_by_date(connection, patient_id, fecha_guardada)
                        if record_original: 
                            id_seguimiento_editado = record_original.get('id_seguimiento')
                            if record_original.get('id_dr'): 
                                 id_dr_para_guardar = record_original.get('id_dr')
                    
                    data_to_save = {
                        'id_px': patient_id,
                        'id_dr': id_dr_para_guardar,
                        'fecha': fecha_guardada if (is_admin and record_original) else today_str
                    }
                    if id_seguimiento_editado:
                        data_to_save['id_seguimiento'] = id_seguimiento_editado
                    
                    id_plan_asociado_str = request.form.get('id_plan_cuidado_asociado')
                    data_to_save['id_plan_cuidado_asociado'] = int(id_plan_asociado_str) if id_plan_asociado_str and id_plan_asociado_str.isdigit() else None
                    
                    # Segmentos
                    segmentos = ['occipital', 'atlas', 'axis', 'c3', 'c4', 'c5', 'c6', 'c7',
                        't1', 't2', 't3', 't4', 't5', 't6', 't7', 't8', 't9', 't10', 't11', 't12',
                        'l1', 'l2', 'l3', 'l4', 'l5', 'sacro', 'coxis', 'iliaco_d', 'iliaco_i', 'pubis']
                    for seg in segmentos:
                        data_to_save[seg] = request.form.get(seg, '').strip()

                    data_to_save['notas'] = request.form.get('notas', '').strip()

                    # Terapias
                    selected_therapy_ids = request.form.getlist('terapia_chk')
                    valid_therapy_ids = [tid for tid in selected_therapy_ids if tid.isdigit()]
                    terapia_string_form = '0,' + ','.join(sorted(valid_therapy_ids))
                    if terapia_string_form == '0,': terapia_string_form = '0,'
                    data_to_save['terapia'] = terapia_string_form

                    # 1. Guardar seguimiento
                    saved_id_seguimiento = save_seguimiento(connection, data_to_save) 
                    if not saved_id_seguimiento:
                        raise Exception("Error al guardar el seguimiento principal.")

                    # 2. Guardar Notas Ortopédicas
                    notas_orto_form = request.form.get('notas_pruebas_ortoneuro')
                    id_postura_para_actualizar_str = request.form.get('id_postura_hoy')
                    id_postura_para_actualizar = int(id_postura_para_actualizar_str) if id_postura_para_actualizar_str and id_postura_para_actualizar_str.isdigit() else None

                    if notas_orto_form is not None and id_postura_para_actualizar:
                        success_notas = update_postura_ortho_notes(connection, id_postura_para_actualizar, notas_orto_form.strip())
                        if not success_notas:
                            raise Exception("Error al guardar las notas ortopédicas.")

                    # 3. Commit Manual
                    connection.commit()
                    flash('Seguimiento guardado exitosamente.', 'success')

                    # Lógica Dinámica de Redirección
                    from db.auth import get_doctor_profile
                    perfil_dr = get_doctor_profile(connection, id_dr_actual_sesion)
                    preferencia = perfil_dr.get('config_redireccion_seguimiento', 0) if perfil_dr else 0

                    if preferencia == 1: return redirect(url_for('main'))
                    elif preferencia == 2: return redirect(url_for('patient.patient_detail', patient_id=patient_id))
                    else: return redirect(url_for('clinical.manage_seguimiento', patient_id=patient_id, selected_id=saved_id_seguimiento))
                
                except (PermissionError, ValueError, Exception) as e:
                     print(f"Error POST manage_seguimiento (PID {patient_id}): {e}")
                     try: connection.rollback()
                     except Error: pass
                     
                     if isinstance(e, PermissionError): flash(str(e), 'warning')
                     elif isinstance(e, ValueError): flash(f"Error en datos: {e}", 'danger')
                     else: flash(f'Error interno al guardar: {e}', 'danger')

                     # Lógica de re-renderizado en caso de error (Simplificada: redirigir para recargar limpio)
                     return redirect(url_for('clinical.manage_seguimiento', patient_id=patient_id))
                finally:
                    if connection: connection.autocommit = True # Restaurar autocommit
                    
            # --- Lógica GET (Ver) ---
            else: 
                today_date_obj = datetime.now().date()
                
                selected_id_str = request.args.get('selected_id')
                force_today_view = (selected_id_str == "")
                selected_id = None
                if selected_id_str and selected_id_str != "":
                    try: selected_id = int(selected_id_str)
                    except ValueError: flash("ID de seguimiento inválido.", "warning")

                all_records_info = get_seguimiento_summary(connection, patient_id)
                current_data = None
                id_seguimiento_a_cargar = None
                fecha_cargada_obj = None 
                id_plan_asociado_a_cargar = None
                nombre_doctor_del_registro = nombre_dr_actual_sesion 

                if selected_id:
                    current_data = get_specific_seguimiento(connection, selected_id)
                    if not (current_data and current_data.get('id_px') == patient_id):
                        flash("Registro de seguimiento no encontrado o inválido.", "warning")
                        current_data = None; selected_id = None
                        force_today_view = True
                    else:
                        id_seguimiento_a_cargar = selected_id
                        fecha_cargada_obj = current_data.get('fecha') 
                        id_plan_asociado_a_cargar = current_data.get('id_plan_cuidado_asociado')
                        nombre_doctor_del_registro = current_data.get('nombre_doctor_seguimiento', nombre_dr_actual_sesion)

                if current_data is None:
                     if force_today_view:
                          current_data_today = get_specific_seguimiento_by_date(connection, patient_id, today_str)
                          if current_data_today:
                              current_data = current_data_today
                              id_seguimiento_a_cargar = current_data.get('id_seguimiento')
                              id_plan_asociado_a_cargar = current_data.get('id_plan_cuidado_asociado')
                              nombre_doctor_del_registro = current_data.get('nombre_doctor_seguimiento', nombre_dr_actual_sesion)
                          else: 
                              current_data = {}
                              id_seguimiento_a_cargar = None
                              if active_plans_list:
                                  id_plan_asociado_a_cargar = active_plans_list[0]['id_plan']
                          fecha_cargada_obj = today_date_obj
                     else:
                          current_data_today = get_specific_seguimiento_by_date(connection, patient_id, today_str)
                          if current_data_today:
                              current_data = current_data_today
                              id_seguimiento_a_cargar = current_data.get('id_seguimiento')
                              fecha_cargada_obj = today_date_obj
                              id_plan_asociado_a_cargar = current_data.get('id_plan_cuidado_asociado')
                              nombre_doctor_del_registro = current_data.get('nombre_doctor_seguimiento', nombre_dr_actual_sesion)
                          else: 
                              current_data = {}
                              id_seguimiento_a_cargar = None
                              fecha_cargada_obj = today_date_obj 
                              if active_plans_list:
                                  id_plan_asociado_a_cargar = active_plans_list[0]['id_plan']
                
                is_editable = is_admin or (fecha_cargada_obj == today_date_obj)
                
                available_therapies = get_terapias_fisicas(connection)
                terapia_string = current_data.get('terapia', '0,') if current_data else '0,'
                current_selected_ids = terapia_string.split(',')
                latest_anamnesis_data = get_latest_anamnesis(connection, patient_id) or {}
                historia_narrativa = latest_anamnesis_data.get('historia', '')
                latest_postura_data = get_latest_postura_overall(connection, patient_id) or {}
                latest_rx_list = get_latest_radiografias_overall(connection, patient_id, limit=4)

                active_plan_status = get_active_plan_status(connection, patient_id)

                # --- CÁLCULO DE VISITAS ---
                safe_plan = active_plan_status if active_plan_status else {}
                qp_total = safe_plan.get('visitas_qp', 0)
                qp_restantes = safe_plan.get('qp_restantes', 0) 
                tf_total = safe_plan.get('visitas_tf', 0)
                tf_restantes = safe_plan.get('tf_restantes', 0)

                visita_qp_actual = qp_total - qp_restantes
                visita_tf_actual = tf_total - tf_restantes

                if id_seguimiento_a_cargar is None:
                    visita_qp_actual += 1
                    visita_tf_actual += 1
                
                # --- Notas Ortopédicas ---
                show_ortho_notes_field = False
                ortho_notes_today = ""
                id_postura_hoy_para_form = None
                postura_data_hoy = None

                if fecha_cargada_obj == today_date_obj:
                    postura_data_hoy = get_specific_postura_by_date(connection, patient_id, today_str)

                if postura_data_hoy:
                    show_ortho_notes_field = True
                    ortho_notes_today = postura_data_hoy.get('notas_pruebas_ortoneuro', '')
                    id_postura_hoy_para_form = postura_data_hoy.get('id_postura')
                    
                return render_template('seguimiento_form.html',
                                       patient=patient,
                                       all_records_info=all_records_info,
                                       current_data=current_data,
                                       is_editable=is_editable, 
                                       loaded_id_seguimiento=id_seguimiento_a_cargar,
                                       today_str=today_str,
                                       available_therapies=available_therapies,
                                       current_selected_ids=current_selected_ids,
                                       active_plans_list=active_plans_list,
                                       id_plan_asociado_seleccionado=id_plan_asociado_a_cargar,
                                       historia_narrativa=historia_narrativa,
                                       latest_postura_data=latest_postura_data,
                                       latest_rx_list=latest_rx_list,
                                       nombre_doctor_sesion=nombre_doctor_del_registro, 
                                       active_plan_status=active_plan_status,
                                       show_ortho_notes_field=show_ortho_notes_field,
                                       ortho_notes_today=ortho_notes_today,
                                       id_postura_hoy_para_form=id_postura_hoy_para_form,
                                       
                                       visita_qp_actual=visita_qp_actual,
                                       visita_tf_actual=visita_tf_actual,
                                       qp_total=qp_total,
                                       qp_restantes=qp_restantes,
                                       tf_total=tf_total,
                                       tf_restantes=tf_restantes,
                                       tf_consumidas=visita_tf_actual 
                                      )
    except Exception as e:
        print(f"Error general en manage_seguimiento (PID {patient_id}): {e}")
        flash('Ocurrió un error inesperado al gestionar el seguimiento.', 'danger')
        safe_redirect_url = url_for('patient.patient_detail', patient_id=patient_id) if 'patient_id' in locals() and patient_id is not None else url_for('main')
        return redirect(safe_redirect_url)

@clinical_bp.route('/revaloracion', methods=['GET', 'POST'])
@login_required
def manage_revaloracion(patient_id):
    today_str = datetime.now().strftime('%d/%m/%Y')
    is_admin = session.get('is_admin', False)
    id_dr_actual = session.get('id_dr')

    if not id_dr_actual:
        flash("Error de sesión.", "danger")
        return redirect(url_for('auth.login'))

    try:
        # Usamos el gestor de contexto para la conexión
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                flash('Error conectando.', 'danger')
                return redirect(url_for('main'))
            
            patient = get_patient_by_id(connection, patient_id)
            if not patient:
                flash('Paciente no encontrado.', 'warning')
                return redirect(url_for('main'))

            # --- Lógica POST (Guardar) ---
            if request.method == 'POST':
                # Deshabilitamos autocommit del conector para manejar transacción manual compleja
                # (Aunque el CM hace commit al final, esto nos da control fino para rollback manual)
                connection.autocommit = False
                print("INFO (Reval POST): Autocommit deshabilitado. Iniciando transacción.")

                try:
                    id_revaloracion_editado_str = request.form.get('id_revaloracion')
                    id_revaloracion_editado = int(id_revaloracion_editado_str) if id_revaloracion_editado_str else None
                    fecha_guardada = request.form.get('fecha_cargada', today_str)

                    # Validación de Permisos
                    is_editable_post = False
                    record_original = None
                    fecha_original_db_str = None
                    
                    if id_revaloracion_editado:
                        record_original = get_specific_revaloracion(connection, id_revaloracion_editado)
                        fecha_original_db_obj = record_original.get('fecha') if record_original else None
                        if isinstance(fecha_original_db_obj, date):
                            fecha_original_db_str = fecha_original_db_obj.strftime('%d/%m/%Y')

                        if not (record_original and record_original.get('id_px') == patient_id and fecha_original_db_str == fecha_guardada):
                             raise ValueError("Revaloración a editar inválida.")
                        
                        if is_admin or (fecha_original_db_str == today_str): is_editable_post = True
                    else: 
                         if fecha_guardada == today_str: is_editable_post = True
                         else: is_editable_post = is_admin
                    
                    if not is_editable_post: raise PermissionError('Permiso denegado.')

                    # Preparar Datos
                    data_to_save = {
                        'id_px': patient_id, 'id_dr': id_dr_actual, 'id_revaloracion': id_revaloracion_editado,
                        'fecha': fecha_guardada if (is_admin and record_original) else today_str,
                        'id_anamnesis_inicial': request.form.get('id_anamnesis_inicial') or None,
                        'diagrama_actual': request.form.get('diagrama_puntos', '0,')
                    }
                    if not data_to_save['diagrama_actual']: data_to_save['diagrama_actual'] = '0,'
                    
                    try:
                        data_to_save['calif1_actual'] = int(request.form.get('calif1_actual') or 0)
                        data_to_save['calif2_actual'] = int(request.form.get('calif2_actual') or 0)
                        data_to_save['calif3_actual'] = int(request.form.get('calif3_actual') or 0)
                        data_to_save['mejora_subjetiva_pct'] = int(request.form.get('mejora_subjetiva_pct') or 0)
                        data_to_save['notas_adicionales_reval'] = request.form.get('notas_adicionales_reval', '').strip()
                    except ValueError: raise ValueError("Calificaciones deben ser números.")

                    # Vincular Postura
                    postura_asoc = get_specific_postura_by_date(connection, patient_id, data_to_save['fecha'])
                    data_to_save['id_postura_asociado'] = postura_asoc.get('id_postura') if postura_asoc else None
                    if not postura_asoc:
                        flash(f"Advertencia: No se encontraron 'Pruebas' para la fecha {data_to_save['fecha']}.", "info")

                    # Guardar
                    saved_id = save_revaloracion(connection, data_to_save)
                    if not saved_id: raise Exception("Error al guardar la revaloración.")

                    # Commit Manual (dentro del bloque try)
                    connection.commit()
                    flash('Revaloración guardada exitosamente.', 'success')
                    return redirect(url_for('clinical.manage_revaloracion', patient_id=patient_id, selected_id=saved_id))

                except (PermissionError, ValueError, Exception) as e:
                    print(f"ERROR POST revaloracion: {e}")
                    try: connection.rollback()
                    except Error: pass
                    
                    if isinstance(e, PermissionError): flash(str(e), 'warning')
                    elif isinstance(e, ValueError): flash(f"Error en datos: {e}", 'danger')
                    else: flash(f'Error interno: {e}', 'danger')
                    
                    # (Aquí iría la lógica de re-renderizado en caso de error, 
                    #  por brevedad redirigimos para recargar limpio, que es más seguro)
                    return redirect(url_for('clinical.manage_revaloracion', patient_id=patient_id))
                finally:
                    if connection: connection.autocommit = True # Restaurar autocommit

            # --- Lógica GET (Ver) ---
            else:
                selected_id_str = request.args.get('selected_id')
                selected_id = int(selected_id_str) if selected_id_str else None
                all_records_info = get_revaloraciones_summary(connection, patient_id)
                
                current_data = None
                id_revaloracion_a_cargar = None
                fecha_cargada = None
                linked_anamnesis_id = None

                if selected_id:
                    current_data = get_specific_revaloracion(connection, selected_id) 
                    if current_data and current_data.get('id_px') == patient_id:
                        id_revaloracion_a_cargar = selected_id
                        fecha_cargada = current_data.get('fecha')
                        linked_anamnesis_id = current_data.get('id_anamnesis_inicial')
                    else:
                        current_data = None

                if current_data is None:
                     current_data = get_specific_revaloracion_by_date(connection, patient_id, today_str) 
                     if current_data: 
                         id_revaloracion_a_cargar = current_data.get('id_revaloracion')
                         fecha_cargada = today_str
                         linked_anamnesis_id = current_data.get('id_anamnesis_inicial')
                     else: 
                         current_data = {}
                         fecha_cargada = today_str

                is_editable = is_admin or (fecha_cargada == today_str)

                # Datos Auxiliares
                anamnesis_summary_list = get_anamnesis_summary(connection, patient_id)
                if linked_anamnesis_id is None and anamnesis_summary_list: 
                    linked_anamnesis_id = anamnesis_summary_list[0]['id_anamnesis']
                
                initial_anamnesis_data = None
                if linked_anamnesis_id:
                    initial_anamnesis_data = get_specific_anamnesis(connection, linked_anamnesis_id)
                if not initial_anamnesis_data:
                    initial_anamnesis_data = get_latest_anamnesis(connection, patient_id) or {}

                postura_data_for_date = get_specific_postura_by_date(connection, patient_id, fecha_cargada) or {}
                rx_list_for_date = get_radiografias_for_postura(connection, postura_data_for_date.get('id_postura')) if postura_data_for_date.get('id_postura') else []

                return render_template('revaloracion_form.html',
                                       patient=patient, 
                                       all_records_info=all_records_info, 
                                       current_data=current_data,
                                       is_editable=is_editable, 
                                       loaded_id_revaloracion=id_revaloracion_a_cargar,
                                       today_str=today_str, 
                                       anamnesis_summary_list=anamnesis_summary_list,
                                       linked_anamnesis_id=linked_anamnesis_id, 
                                       initial_anamnesis_data=initial_anamnesis_data,
                                       postura_data_for_date=postura_data_for_date,
                                       latest_rx_list=rx_list_for_date,
                                       DIAGRAMA_PUNTOS_COORDENADAS=DIAGRAMA_PUNTOS_COORDENADAS, 
                                       loaded_date=fecha_cargada)

    except Exception as e:
        print(f"Error general manage_revaloracion: {e}")
        flash('Ocurrió un error inesperado.', 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@clinical_bp.route('/plan_cuidado', methods=['GET', 'POST'])
@login_required
def manage_plan_cuidado(patient_id):
    today_str = datetime.now().strftime('%d/%m/%Y')
    today_date_obj = datetime.now().date()
    is_admin = session.get('is_admin', False)
    id_dr_actual_sesion = session.get('id_dr')
    id_centro_dr_logueado = session.get('id_centro_dr')

    if not id_dr_actual_sesion:
        flash("Error de sesión.", "danger")
        return redirect(url_for('auth.login'))

    try:
        # Usamos el gestor de contexto para la conexión
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                flash('Error conectando a la base de datos.', 'danger')
                return redirect(url_for('main'))
            
            patient = get_patient_by_id(connection, patient_id)
            if not patient:
                flash('Paciente no encontrado.', 'warning')
                return redirect(url_for('main'))

            # Datos comunes
            centro_para_filtrar = None if is_admin else id_centro_dr_logueado
            doctors_list = get_all_doctors(connection, include_inactive=False, filter_by_centro_id=centro_para_filtrar)
            adicionales_list = get_productos_servicios_by_type(connection, tipo_adicional=1)
            
            # Obtener costos base
            costo_qp_db = 0.0
            costo_tf_db = 0.0
            for prod in get_productos_servicios_by_type(connection, tipo_adicional=0):
                if 'ajuste' in prod.get('nombre', '').lower(): costo_qp_db = float(prod.get('costo', 0.0))
                elif 'terapia' in prod.get('nombre', '').lower(): costo_tf_db = float(prod.get('costo', 0.0))
            
            anamnesis_summary_list = get_anamnesis_summary(connection, patient_id)

            # --- Lógica POST (Guardar) ---
            if request.method == 'POST':
                try:
                    # Deshabilitar autocommit para transacción manual si es necesario
                    # (Aunque get_db_cursor(commit=True) ya hace commit al final, esto permite rollback manual)
                    
                    id_plan_editado = int(request.form.get('id_plan')) if request.form.get('id_plan') else None
                    fecha_guardada = request.form.get('fecha_cargada', today_str)
                    form_data = { k: request.form.get(k) for k in request.form }
                    
                    # Validar permisos
                    is_editable_post = False
                    record_original = None
                    if id_plan_editado:
                        record_original = get_specific_plan_cuidado(connection, id_plan_editado)
                        fecha_orig_obj = record_original.get('fecha') if record_original else None
                        fecha_orig_str = fecha_orig_obj.strftime('%d/%m/%Y') if fecha_orig_obj else None
                        
                        if is_admin or (fecha_orig_str == today_str): is_editable_post = True
                    else:
                        is_editable_post = is_admin or (fecha_guardada == today_str)

                    if not is_editable_post: raise PermissionError('Permiso denegado.')

                    # Cálculos Financieros
                    visitas_qp = int(form_data.get('visitas_qp') or 0)
                    visitas_tf = int(form_data.get('visitas_tf') or 0)
                    promocion_pct = int(form_data.get('promocion_pct') or 0)
                    
                    inversion_bruta = (visitas_qp * costo_qp_db) + (visitas_tf * costo_tf_db)
                    ahorro_calculado = (inversion_bruta * promocion_pct) / 100.0
                    inversion_total_neta = inversion_bruta - ahorro_calculado

                    data_to_save = {
                        'id_px': patient_id,
                        'id_plan': id_plan_editado,
                        'fecha': fecha_guardada if (is_admin and record_original) else today_str,
                        'id_dr': int(form_data.get('id_dr') or id_dr_actual_sesion),
                        'pb_diagnostico': form_data.get('pb_diagnostico', '').strip(),
                        'etapa': form_data.get('etapa', '').strip(),
                        'notas_plan': form_data.get('notas_plan', '').strip(),
                        'visitas_qp': visitas_qp,
                        'visitas_tf': visitas_tf,
                        'promocion_pct': promocion_pct,
                        'inversion_total': round(inversion_total_neta, 2),
                        'ahorro_calculado': round(ahorro_calculado, 2),
                        'adicionales_ids': '0,' + ','.join([aid for aid in request.form.getlist('adicionales_chk') if aid.isdigit()])
                    }

                    saved_id = save_plan_cuidado(connection, data_to_save)
                    if not saved_id: raise Exception("Error al guardar en BD.")

                    flash('Plan de Cuidado guardado exitosamente.', 'success')
                    return redirect(url_for('clinical.manage_plan_cuidado', patient_id=patient_id, selected_id=saved_id))

                except Exception as e:
                    print(f"ERROR POST manage_plan_cuidado: {e}")
                    flash(f"Error: {e}", 'danger')
                    return redirect(url_for('clinical.manage_plan_cuidado', patient_id=patient_id))

            # --- Lógica GET (Ver) ---
            else:
                selected_id = int(request.args.get('selected_id')) if request.args.get('selected_id') else None
                all_records_info = get_plan_cuidado_summary(connection, patient_id)
                
                current_data = None
                id_plan_a_cargar = None
                linked_doctor_id = id_dr_actual_sesion
                fecha_cargada_obj = today_date_obj

                if selected_id:
                    current_data = get_specific_plan_cuidado(connection, selected_id)
                    if current_data:
                        id_plan_a_cargar = selected_id
                        fecha_cargada_obj = current_data.get('fecha')
                        linked_doctor_id = current_data.get('id_dr')
                
                if not current_data:
                    current_data_today = get_specific_plan_cuidado_by_date(connection, patient_id, today_str)
                    if current_data_today:
                        current_data = current_data_today
                        id_plan_a_cargar = current_data.get('id_plan')
                        fecha_cargada_obj = current_data.get('fecha')
                        linked_doctor_id = current_data.get('id_dr')
                    else:
                        current_data = {}

                # Calcular progreso
                qp_completadas = 0; tf_completadas = 0
                seguimientos_del_plan = []
                adicionales_status = []
                
                if id_plan_a_cargar:
                    seguimientos_del_plan = get_seguimientos_for_plan(connection, id_plan_a_cargar) or []
                    qp_completadas = len(seguimientos_del_plan)
                    for seg in seguimientos_del_plan:
                        t_ids = seg.get('terapia', '0,').strip(',').split(',')
                        if any(tid != '0' and tid for tid in t_ids): tf_completadas += 1
                    adicionales_status = analizar_adicionales_plan(connection, id_plan_a_cargar)

                is_editable = is_admin or (fecha_cargada_obj == today_date_obj)
                current_selected_adicionales = current_data.get('adicionales_ids', '0,').split(',')

                return render_template('plan_cuidado_form.html',
                                       patient=patient, all_records_info=all_records_info, 
                                       current_data=current_data,
                                       is_editable=is_editable, loaded_id_plan=id_plan_a_cargar, 
                                       today_str=today_str,
                                       adicionales_list=adicionales_list, 
                                       current_selected_adicionales=current_selected_adicionales,
                                       doctors_list=doctors_list,
                                       linked_doctor_id=linked_doctor_id, 
                                       costo_qp_js=costo_qp_db, costo_tf_js=costo_tf_db,
                                       anamnesis_summary_list=anamnesis_summary_list,
                                       qp_completadas=qp_completadas,
                                       tf_completadas=tf_completadas,
                                       seguimientos_del_plan=seguimientos_del_plan,
                                       adicionales_status=adicionales_status)

    except Exception as e:
        print(f"Error general en manage_plan_cuidado: {e}")
        flash('Ocurrió un error inesperado.', 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@clinical_bp.route('/recibo', methods=['GET', 'POST'])
@clinical_bp.route('/recibo/<int:recibo_id>', methods=['GET'])
@login_required
def manage_recibos(patient_id, recibo_id=None):
    # --- Lógica POST (Guardar) ---
    if request.method == 'POST':
        try:
            # Usamos commit=True porque vamos a guardar
            with get_db_cursor(commit=True) as (connection_post, cursor):
                if not connection_post:
                    return jsonify({'success': False, 'message': 'Error de conexión DB.'}), 500
                
                # NO necesitamos start_transaction() manual porque el context manager lo maneja
                # Pero si tu función save_recibo espera una conexión con transacción iniciada, el CM ya lo hizo.
                
                form_datos_recibo = {
                    'id_px': patient_id,
                    'id_dr': session.get('id_dr'), 
                    'fecha': request.form.get('fecha_recibo'), 
                    'subtotal_bruto': float(request.form.get('subtotal_bruto_hidden', 0.0)),
                    'descuento_total': float(request.form.get('descuento_total_hidden', 0.0)),
                    'total_neto': float(request.form.get('total_neto_hidden', 0.0)),
                    'pago_efectivo': float(request.form.get('pago_efectivo', 0.0) or 0.0),
                    'pago_tarjeta': float(request.form.get('pago_tarjeta', 0.0) or 0.0),
                    'pago_transferencia': float(request.form.get('pago_transferencia', 0.0) or 0.0),
                    'pago_otro': float(request.form.get('pago_otro', 0.0) or 0.0), 
                    'pago_otro_desc': request.form.get('pago_otro_desc'),
                    'notas': request.form.get('notas_recibo')
                }
                
                detalles_json_str = request.form.get('recibo_detalles_json')
                if not detalles_json_str: raise ValueError("Detalles no enviados.")
                form_detalles_recibo = json.loads(detalles_json_str)
                if not form_detalles_recibo: raise ValueError("Detalles vacíos.")

                id_nuevo = save_recibo(connection_post, form_datos_recibo, form_detalles_recibo)
                
                if id_nuevo:
                    # El commit se hace automático al salir del 'with' si no hay error
                    flash('Recibo guardado.', 'success')
                    return jsonify({ 
                        'success': True, 
                        'message': f'Recibo #{id_nuevo} guardado exitosamente.',
                        'new_receipt_id': id_nuevo,
                        'view_receipt_url': url_for('clinical.manage_recibos', patient_id=patient_id, recibo_id=id_nuevo),
                        'pdf_url': url_for('clinical.generate_recibo_pdf', patient_id=patient_id, id_recibo=id_nuevo) 
                    }), 200
                else:
                    raise Exception("Fallo al guardar recibo (save_recibo devolvió None).")

        except (ValueError, TypeError, json.JSONDecodeError) as ve:
            print(f"Error de datos/JSON: {ve}")
            return jsonify({'success': False, 'message': f"Error en los datos: {str(ve)}"}), 400
        except Exception as e:
            print(f"Error general POST recibo: {e}")
            return jsonify({'success': False, 'message': 'Error inesperado al guardar.'}), 500

    # --- Lógica GET (Ver/Cargar) ---
    try:
        # Usamos conexión de solo lectura (o lectura/escritura sin commit forzado)
        with get_db_cursor() as (connection, cursor):
            if not connection:
                flash('Error conectando a la base de datos.', 'danger')
                return redirect(url_for('main'))

            patient_context = get_patient_by_id(connection, patient_id)
            if not patient_context:
                flash('Paciente no encontrado.', 'warning')
                return redirect(url_for('main'))

            productos_context = get_productos_servicios_venta(connection)
            recibos_anteriores_context = get_recibos_by_patient(connection, patient_id)
            historial_compras_context = get_historial_compras_paciente(connection, patient_id) or []

            # Defaults
            is_new_recibo_context = True 
            current_recibo_data_context = None 
            current_recibo_detalles_context = []
            id_dr_actual_context = session.get('id_dr')
            recibo_id_cargado_context = None
            today_str_context = datetime.now().strftime('%d/%m/%Y')

            if recibo_id: 
                current_recibo_data_context = get_recibo_by_id(connection, recibo_id)
                
                if current_recibo_data_context and current_recibo_data_context.get('id_px') == patient_id:
                    is_new_recibo_context = False
                    current_recibo_detalles_context = get_recibo_detalles_by_id(connection, recibo_id)
                    id_dr_actual_context = current_recibo_data_context.get('id_dr', session.get('id_dr'))
                    recibo_id_cargado_context = recibo_id
                    
                    # Filtrar historial para no mostrar el recibo actual
                    historial_compras_context = [item for item in historial_compras_context if int(item.get('id_recibo', 0)) != recibo_id]
                else:
                    flash("Recibo no encontrado o inválido. Mostrando nuevo.", "warning")
                    # Se mantienen los defaults de "Nuevo"

            return render_template('recibo_form.html', 
                                   patient=patient_context,
                                   productos=productos_context, 
                                   recibos_anteriores=recibos_anteriores_context,
                                   current_recibo_data=current_recibo_data_context, 
                                   current_recibo_detalles=current_recibo_detalles_context,
                                   is_new_recibo=is_new_recibo_context,
                                   id_dr_actual=id_dr_actual_context,
                                   today_str=today_str_context,
                                   recibo_id_cargado=recibo_id_cargado_context,
                                   historial_de_compras=historial_compras_context 
                                   )

    except Exception as e:
        print(f"Error GET manage_recibos: {e}")
        flash(f"Error al cargar recibos: {str(e)}", "danger")
        return redirect(url_for('patient.patient_detail', patient_id=patient_id) if patient_id else url_for('main'))

@clinical_bp.route('/reporte')
@login_required
def generate_patient_report(patient_id):
    try:
        # Usamos el gestor de contexto para manejo automático de la conexión
        with get_db_cursor() as (connection, cursor):
            if not connection:
                flash("Error de conexión.", "danger")
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))

            patient = get_patient_by_id(connection, patient_id)
            today_str = datetime.now().strftime('%d/%m/%Y')

            anamnesis_episodes_list = get_anamnesis_summary(connection, patient_id)
            if not anamnesis_episodes_list:
                flash("Este paciente aún no tiene registros de Anamnesis para generar un reporte de episodio.", "warning")
                report_data = {
                    'patient': patient, 'antecedente': {}, 'anamnesis': {}, 'postura': {}, 'rx_list': [],
                    'comparison_initial_anamnesis': {}, 'comparison_linked_revals': [],
                    'cond_gen_text': [], 'cond_diag_text': [], 'dolor_intenso_text': [],
                    'tipo_dolor_text': [], 'como_comenzo_text': '', 'diagrama_puntos': []
                }
                return render_template('reporte_paciente.html', data=report_data, anamnesis_episodes_list=[], 
                                       loaded_episode_id=None, today_str=today_str,
                                       CONDICIONES_GENERALES_MAP=CONDICIONES_GENERALES_MAP, 
                                       DIAGRAMA_PUNTOS_COORDENADAS=DIAGRAMA_PUNTOS_COORDENADAS)

            selected_episode_id_str = request.args.get('selected_episode_id')
            selected_episode_id = None
            valid_episode_ids = {ep['id_anamnesis'] for ep in anamnesis_episodes_list}

            if selected_episode_id_str:
                try:
                    selected_episode_id_temp = int(selected_episode_id_str)
                    if selected_episode_id_temp in valid_episode_ids:
                        selected_episode_id = selected_episode_id_temp
                    else: flash("ID de episodio seleccionado inválido.", "warning")
                except ValueError: flash("ID de episodio inválido.", "warning")

            if selected_episode_id is None:
                selected_episode_id = anamnesis_episodes_list[0]['id_anamnesis']

            episode_initial_anamnesis = get_specific_anamnesis(connection, selected_episode_id) or {}
            episode_start_date = episode_initial_anamnesis.get('fecha')

            antecedente_data, postura_data, rx_list, postura_images, centro_info = {}, {}, [], {}, {}
            
            if episode_start_date:
                episode_start_date_str = episode_start_date.strftime('%d/%m/%Y')
                antecedente_data = get_latest_antecedente_on_or_before_date(connection, patient_id, episode_start_date_str) or {}
                postura_data = get_first_postura_on_or_after_date(connection, patient_id, episode_start_date_str) or {}
                if postura_data.get('id_postura'):
                    rx_list = get_radiografias_for_postura(connection, postura_data['id_postura'])
                    postura_images = {
                        'frente': url_for('static', filename=postura_data['frente']) if postura_data.get('frente') else None,
                        'lado': url_for('static', filename=postura_data['lado']) if postura_data.get('lado') else None,
                        'extra': url_for('static', filename=postura_data.get('postura_extra')) if postura_data.get('postura_extra') else None,
                    }

            id_centro_sesion = session.get('id_centro_dr')
            centro_info = get_centro_by_id(connection, id_centro_sesion) if id_centro_sesion else {'nombre': 'Chiropractic Care Center', 'direccion': 'N/A', 'cel': 'N/A', 'tel': 'N/A'}

            comparison_linked_revals = get_revaloraciones_linked_to_anamnesis(connection, selected_episode_id) if selected_episode_id else []

            diagrama_anam_inicial_str = episode_initial_anamnesis.get('diagrama', '0,')
            diagrama_puntos_inicial = [p for p in diagrama_anam_inicial_str.split(',') if p and p != '0']

            cond_diag_str = antecedente_data.get('condicion_diagnosticada', '0,')
            cond_diag_ids = [cd_id for cd_id in cond_diag_str.split(',') if cd_id and cd_id != '0']
            cond_diag_text_list = [CONDICION_DIAGNOSTICADA_MAP.get(cd_id, f"ID Desconocido: {cd_id}") for cd_id in cond_diag_ids]

            cond_gen_str = antecedente_data.get('condiciones_generales', '0,')
            cond_gen_ids = [cg_id for cg_id in cond_gen_str.split(',') if cg_id and cg_id != '0']
            cond_gen_text_list = [CONDICIONES_GENERALES_MAP.get(cg_id, f"ID Desconocido: {cg_id}") for cg_id in cond_gen_ids]

            como_comenzo_id = episode_initial_anamnesis.get('como_comenzo')
            como_comenzo_text = COMO_COMENZO_MAP.get(como_comenzo_id, 'N/A')

            dolor_intenso_str = episode_initial_anamnesis.get('dolor_intenso', '0,')
            dolor_intenso_ids = [di_id for di_id in dolor_intenso_str.split(',') if di_id and di_id != '0']
            dolor_intenso_text_list = [DOLOR_INTENSO_MAP.get(di_id, '') for di_id in dolor_intenso_ids]

            tipo_dolor_str = episode_initial_anamnesis.get('tipo_dolor', '0,')
            tipo_dolor_ids = [td_id for td_id in tipo_dolor_str.split(',') if td_id and td_id != '0']
            tipo_dolor_text_list = [TIPO_DOLOR_MAP.get(td_id, '') for td_id in tipo_dolor_ids]

            report_data = {
                'patient': patient, 'antecedente': antecedente_data, 'anamnesis': episode_initial_anamnesis,
                'postura': postura_data, 'rx_list': rx_list, 'postura_images': postura_images, 'centro_info': centro_info,
                'comparison_initial_anamnesis': episode_initial_anamnesis, 'comparison_linked_revals': comparison_linked_revals,
                'diagrama_puntos': diagrama_puntos_inicial, 'cond_diag_text': cond_diag_text_list,
                'cond_gen_text': cond_gen_text_list, 'como_comenzo_text': como_comenzo_text,
                'dolor_intenso_text': dolor_intenso_text_list, 'tipo_dolor_text': tipo_dolor_text_list
            }

            return render_template('reporte_paciente.html', data=report_data, anamnesis_episodes_list=anamnesis_episodes_list,
                                   loaded_episode_id=selected_episode_id, today_str=today_str,
                                   CONDICIONES_GENERALES_MAP=CONDICIONES_GENERALES_MAP,
                                   CONDICION_DIAGNOSTICADA_MAP=CONDICION_DIAGNOSTICADA_MAP,
                                   DIAGRAMA_PUNTOS_COORDENADAS=DIAGRAMA_PUNTOS_COORDENADAS)

    except Exception as e:
        print(f"Error generando reporte para patient_id {patient_id}: {e}")
        flash('Ocurrió un error inesperado al generar el reporte.', 'danger')
        safe_redirect_url = url_for('patient.patient_detail', patient_id=patient_id) if 'patient_id' in locals() else url_for('main')
        return redirect(safe_redirect_url)

@clinical_bp.route('/api/get_reporte_visual_data')
@login_required
def get_reporte_visual_data(patient_id):
    """
    Endpoint de API para obtener los datos necesarios para el reporte visual
    de una fecha específica (anamnesis, postura, Rx). Devuelve JSON.
    """
    fecha_solicitada = request.args.get('fecha')
    if not fecha_solicitada:
        return jsonify({'error': 'No se proporcionó fecha.'}), 400

    try:
        # Usamos el gestor de contexto para manejo automático de la conexión
        with get_db_cursor() as (connection, cursor):
            if not connection:
                return jsonify({'error': 'Error de conexión a la BD.'}), 500

            # 1. Obtener datos de Postura para la fecha
            postura_data = get_specific_postura_by_date(connection, patient_id, fecha_solicitada)
            
            # Si no hay datos de postura, no podemos continuar
            if not postura_data:
                return jsonify({
                    'error': f'No se encontraron datos de pruebas para la fecha {fecha_solicitada}.',
                    'anamnesis': None, 
                    'postura': None, 
                    'radiografias': [] 
                }), 404 # Not Found

            # 2. Obtener la Anamnesis más reciente (general, no necesariamente de esa fecha)
            anamnesis_data = get_latest_anamnesis(connection, patient_id) or {} # Usar {} si no hay

            # 3. Obtener Radiografías asociadas al ID de postura
            radiografias_list = []
            id_postura_actual = postura_data.get('id_postura')
            if id_postura_actual:
                radiografias_db = get_radiografias_for_postura(connection, id_postura_actual)
                if radiografias_db:
                    # Convertimos las rutas a URLs completas
                    radiografias_list = [{'src': url_for('static', filename=rx['ruta_archivo'])} for rx in radiografias_db]

            # 4. Construir el objeto JSON de respuesta
            response_data = {
                'anamnesis': {
                    'condicion1': anamnesis_data.get('condicion1'),
                    'calif1': anamnesis_data.get('calif1'),
                    'historia': anamnesis_data.get('historia') 
                },
                'postura': {
                    'frontal': url_for('static', filename=postura_data.get('frente')) if postura_data.get('frente') else None,
                    'lateral': url_for('static', filename=postura_data.get('lado')) if postura_data.get('lado') else None,
                    'lateral_der': url_for('static', filename=postura_data.get('postura_extra')) if postura_data.get('postura_extra') else None,
                    'pies': url_for('static', filename=postura_data.get('pies')) if postura_data.get('pies') else None, # Plantografía
                    'pies_frontal': url_for('static', filename=postura_data.get('pies_frontal')) if postura_data.get('pies_frontal') else None,
                    'pies_trasera': url_for('static', filename=postura_data.get('pies_trasera')) if postura_data.get('pies_trasera') else None,
                    'termografia': url_for('static', filename=postura_data.get('termografia')) if postura_data.get('termografia') else None,
                },
                'radiografias': radiografias_list
            }
            
            return jsonify(response_data)

    except Exception as e:
        print(f"Error en get_reporte_visual_data (PID {patient_id}, Fecha {fecha_solicitada}): {e}")
        return jsonify({'error': f'Error interno del servidor al procesar la fecha {fecha_solicitada}.'}), 500

@clinical_bp.route('/pruebas/generar_informe_ia', methods=['POST'])
@login_required
def ajax_generar_informe_postura(patient_id):
    """
    Endpoint AJAX para generar el informe de postura.
    """
    # Obtener los datos del cuerpo de la solicitud JSON
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Solicitud inválida.'}), 400

    rutas_imagenes = {
        'frontal': data.get('ruta_frente'),
        'lateral_izq': data.get('ruta_lado'),
        'lateral_der': data.get('ruta_postura_extra')
    }
    notas_adicionales = data.get('notas_ortoneuro', '')

    # 1. Obtener la ruta absoluta de la imagen frontal para analizarla con OpenCV
    ruta_frontal_relativa = rutas_imagenes.get('frontal')
    ruta_frontal_absoluta = os.path.join(current_app.root_path, 'static', ruta_frontal_relativa) if ruta_frontal_relativa else None

    # 2. Llamar a nuestra función para obtener los datos objetivos (Hombros/Pelvis)
    hallazgos_calculados = analizar_coordenadas_postura(ruta_frontal_absoluta)

     # 3. Generar el informe con IA, pasando los hallazgos calculados
    informe_texto = generar_informe_postura_con_ia(
        rutas_imagenes, 
        notas_adicionales,
        hallazgos_calculados 
    )

    # Devolver el informe como JSON
    return jsonify({'informe': informe_texto})

@clinical_bp.route('/pruebas/generar_informe_podal_ia', methods=['POST'])
@login_required
def ajax_generar_informe_podal(patient_id):
    """
    Endpoint AJAX para generar el informe podal y devolver la imagen anotada.
    """
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Solicitud inválida.'}), 400

    rutas_imagenes = {
        'pies_frontal': data.get('ruta_pies_frontal'),
        'pies_trasera': data.get('ruta_pies_trasera'),
        'pies': data.get('ruta_pisada') # 'pies' es la clave para la plantografía
    }
    notas_adicionales = data.get('notas_plantillas', '')

    # 1. Analizar coordenadas (OpenCV/MediaPipe)
    ruta_trasera_relativa = rutas_imagenes.get('pies_trasera')
    ruta_trasera_absoluta = os.path.join(current_app.root_path, 'static', ruta_trasera_relativa) if ruta_trasera_relativa else None
    
    # Obtenemos tanto los hallazgos como la ruta de la imagen pintada
    hallazgos_podales, ruta_imagen_anotada = analizar_coordenadas_podal(ruta_trasera_absoluta)

    # 2. Generar texto con IA
    informe_texto = generar_informe_podal_unificado(rutas_imagenes, notas_adicionales, hallazgos_podales)

    # 3. Construir respuesta JSON
    response_data = {'informe': informe_texto}
    
    if ruta_imagen_anotada:
        # Generar URL web para la imagen guardada
        response_data['annotated_image_url'] = url_for('static', filename=ruta_imagen_anotada)
    else:
        response_data['annotated_image_url'] = None

    return jsonify(response_data)

@clinical_bp.route('/plan_cuidado/<int:id_plan>/pdf') 
@login_required
def generate_plan_pdf(patient_id, id_plan):
    # 1. Cargar Logo (Fuera de la conexión a BD)
    logo_base64_uri = None
    try:
        logo_path = os.path.join(current_app.static_folder, 'img', 'logo.png')
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                logo_base64_uri = f"data:image/png;base64,{encoded_string}"
    except Exception as e:
        print(f"WARN generate_plan_pdf: Error cargando logo: {e}")

    try:
        # 2. Conexión Segura con Context Manager
        with get_db_cursor() as (connection, cursor):
            if not connection:
                flash('Error de conexión.', 'danger')
                return redirect(url_for('clinical.manage_plan_cuidado', patient_id=patient_id, selected_id=id_plan))

            # 3. Lógica Original Restaurada
            
            # --- Información del centro ---
            id_centro_actual_dr = session.get('id_centro_dr')
            centro_info_for_pdf = None
            if id_centro_actual_dr and id_centro_actual_dr != 0:
                centro_info_for_pdf = get_centro_by_id(connection, id_centro_actual_dr)
            elif session.get('is_admin'):
                centro_info_for_pdf = get_centro_by_id(connection, 1) 
                if not centro_info_for_pdf:
                    centro_info_for_pdf = {'nombre': 'Chiropractic Care Center (Admin)', 'direccion': 'N/A', 'cel': 'N/A', 'tel': 'N/A'}
            else:
                centro_info_for_pdf = {'nombre': 'Chiropractic Care Center', 'direccion': 'N/A', 'cel': 'N/A', 'tel': 'N/A'}

            # --- Datos principales ---
            patient_obj = get_patient_by_id(connection, patient_id) 
            plan_obj = get_specific_plan_cuidado(connection, id_plan) 

            if not patient_obj or not plan_obj or plan_obj.get('id_px') != patient_id:
                flash('Datos no encontrados para generar PDF del plan.', 'warning')
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))

            # --- Nombre del Doctor ---
            doctor_name = "No especificado"
            if plan_obj.get('id_dr'): 
                doctors = get_all_doctors(connection) 
                found_doctor = next((doc for doc in doctors if doc['id_dr'] == plan_obj['id_dr']), None)
                if found_doctor: doctor_name = found_doctor.get('nombre', doctor_name)

            # --- Adicionales ---
            adicionales_seleccionados_obj = [] 
            adicional_ids_str = plan_obj.get('adicionales_ids', '0,')
            adicional_ids_list = [id_str for id_str in adicional_ids_str.split(',') if id_str.isdigit() and int(id_str) > 0]
            if adicional_ids_list: 
                adicionales_seleccionados_obj = get_productos_by_ids(connection, adicional_ids_list)

            # --- Costos ---
            costo_qp = 0.0; costo_tf = 0.0
            productos_base = get_productos_servicios_by_type(connection, tipo_adicional=0)
            for prod in productos_base:
                if 'ajuste quiropractico' in prod.get('nombre', '').lower(): costo_qp = float(prod.get('costo', 0.0))
                elif 'terapia fisica' in prod.get('nombre', '').lower(): costo_tf = float(prod.get('costo', 0.0))

            # --- Preparar datos para Template ---
            data_for_pdf = {
                'patient': patient_obj, 
                'plan': plan_obj,       
                'patient_nombre_completo': f"{patient_obj.get('nombre', '')} {patient_obj.get('apellidop', '')} {patient_obj.get('apellidom', '')}".strip(),
                'doctor_name': doctor_name,
                'adicionales_seleccionados': adicionales_seleccionados_obj,
                'costo_qp_display': costo_qp, 
                'costo_tf_display': costo_tf, 
                'ETAPA_CUIDADO_MAP': ETAPA_CUIDADO_MAP, 
                'logo_base64_uri': logo_base64_uri,
                'current_year_for_pdf': datetime.now().year,
                'centro_info': centro_info_for_pdf
            }

            # 4. Generar PDF
            html_content = render_template('plan_cuidado_pdf.html', data=data_for_pdf) 
            pdf_buffer = BytesIO()
            pisa_status = pisa.CreatePDF(html_content.encode('utf-8'), dest=pdf_buffer, encoding='utf-8')

            if pisa_status.err:
                print(f"Error pisa plan cuidado: {pisa_status.err}")
                flash('Ocurrió un error al generar el archivo PDF del plan.', 'danger')
                return redirect(url_for('clinical.manage_plan_cuidado', patient_id=patient_id, selected_id=id_plan))

            pdf_buffer.seek(0)
            response = Response(pdf_buffer, mimetype='application/pdf')
            response.headers['Content-Disposition'] = f'inline; filename=plan_cuidado_px{patient_id}_plan{id_plan}.pdf'
            return response

    except Exception as e:
        print(f"Error en generate_plan_pdf (PID {patient_id}, PlanID {id_plan}): {e}")
        flash('Error inesperado al generar el PDF del plan.', 'danger')
        safe_redirect_url = url_for('clinical.manage_plan_cuidado', patient_id=patient_id, selected_id=id_plan) if id_plan else url_for('patient.patient_detail', patient_id=patient_id)
        return redirect(safe_redirect_url)@clinical_bp.route('/pdf_plantillas') 

# --- AGREGAR ESTO EN src/blueprints/clinical.py ---

@clinical_bp.route('/pdf_plantillas') 
@login_required
def generate_plantillas_pdf(patient_id):
    connection = None
    logo_base64_uri = None
    try:
        logo_path = os.path.join(current_app.static_folder, 'img', 'logo.png')
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                logo_base64_uri = f"data:image/png;base64,{encoded_string}"
        
        connection = connect_to_db()
        if not connection:
            flash('Error conectando a la base de datos.', 'danger')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        patient = get_patient_by_id(connection, patient_id)
        if not patient:
            flash('Paciente no encontrado.', 'warning')
            return redirect(url_for('main'))

        # ---> OBTENER FECHA DE PRUEBAS DEL PARÁMETRO DE LA URL <---
        fecha_pruebas_solicitada = request.args.get('fecha_pruebas') # Formato 'dd/mm/yyyy'
        postura_data = None

        if fecha_pruebas_solicitada:
            # Asume que get_specific_postura_by_date ya selecciona todas las columnas necesarias
            postura_data = get_specific_postura_by_date(connection, patient_id, fecha_pruebas_solicitada)
            if not postura_data:
                 flash(f'No se encontraron datos de pruebas para la fecha {fecha_pruebas_solicitada}. Se usará el más reciente si existe.', 'info')
                 # Si no se encuentra para la fecha específica, intentamos el más reciente
                 postura_data = get_latest_postura_overall(connection, patient_id)
        else:
            postura_data = get_latest_postura_overall(connection, patient_id)
        # -------------------------------------------------------------

        if not postura_data:
            flash('No se encontraron datos de pruebas/postura para este paciente para generar el PDF de plantillas.', 'warning')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        # Obtener el peso del antecedente más reciente a la fecha de las pruebas DE postura_data
        peso_paciente = "N/A"
        fecha_postura_real_obj = postura_data.get('fecha') # Fecha del registro de postura que se usará
        fecha_postura_real_str = None
        if fecha_postura_real_obj:
            # 2. Convertir el objeto 'date' a un STRING 'dd/mm/YYYY'
            fecha_postura_real_str = fecha_postura_real_obj.strftime('%d/%m/%Y')
            
            # 3. Pasar el STRING a la función que espera un string
            antecedente_reciente = get_latest_antecedente_on_or_before_date(connection, patient_id, fecha_postura_real_str)
            if antecedente_reciente and antecedente_reciente.get('peso') is not None:
                peso_paciente = antecedente_reciente.get('peso')
        
        edad_paciente = calculate_age(patient.get('nacimiento'))
        current_year = datetime.now().year

        # ---> OBTENER INFORMACIÓN DEL CENTRO DEL DOCTOR LOGUEADO <---
        id_centro_actual_dr = session.get('id_centro_dr')
        if id_centro_actual_dr and id_centro_actual_dr != 0: # Si es un ID de centro válido (no admin)
            centro_info_for_pdf = get_centro_by_id(connection, id_centro_actual_dr)
        elif session.get('is_admin'): # Si es admin (centro 0)
            centro_info_for_pdf = get_centro_by_id(connection, 1) 
            if not centro_info_for_pdf: # Si el centro 1 no existe, usar datos genéricos
                centro_info_for_pdf = {'nombre': 'Chiropractic Care Center (Admin)', 'direccion': 'N/A', 'cel': 'N/A', 'tel': 'N/A'}
        else: # No se pudo determinar el centro
            centro_info_for_pdf = {'nombre': 'Chiropractic Care Center', 'direccion': 'N/A', 'cel': 'N/A', 'tel': 'N/A'}


        pdf_data = {
            'patient_nombre': f"{patient.get('nombre', '')} {patient.get('apellidop', '')} {patient.get('apellidom', '')}".strip(),
            'edad': edad_paciente,
            'peso': peso_paciente,
            'pie_cm': postura_data.get('pie_cm'),
            'zapato_cm': postura_data.get('zapato_cm'),
            'tipo_calzado': postura_data.get('tipo_calzado'),
            'foto_pies_general': postura_data.get('pies'),
            'foto_pies_frontal': postura_data.get('pies_frontal'),
            'foto_pies_trasera': postura_data.get('pies_trasera'),
            'notas_plantillas': postura_data.get('notas_plantillas'),
            'fecha_pruebas': fecha_postura_real_str, 
            'logo_base64_uri': logo_base64_uri,
            'current_year_for_pdf': current_year,
            'centro_info': centro_info_for_pdf 
        }

        html_content = render_template('plantillas_pdf_template.html', data=pdf_data)
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_content.encode('utf-8'), dest=pdf_buffer, encoding='utf-8')

        if pisa_status.err:
            print(f"Error al generar PDF de plantillas con pisa: {pisa_status.err}")
            flash('Ocurrió un error al generar el PDF para plantillas.', 'danger')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        pdf_buffer.seek(0)
        response = Response(pdf_buffer, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'inline; filename=plantillas_px{patient_id}_{pdf_data["fecha_pruebas"].replace("/", "-") if pdf_data["fecha_pruebas"] else "reciente"}.pdf'
        return response

    except Exception as e:
        print(f"Error en generate_plantillas_pdf (PID {patient_id}): {e}")
        flash('Error inesperado al generar PDF para plantillas.', 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))
    finally:
        if connection and connection.is_connected():
            connection.close()

@clinical_bp.route('/check_plantillas_data')
@login_required
def check_plantillas_data_exists(patient_id):
    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            return jsonify({'exists': False, 'message': 'Error de conexión a la base de datos.'}), 500

        patient = get_patient_by_id(connection, patient_id)
        if not patient:
            return jsonify({'exists': False, 'message': 'Paciente no encontrado.'}), 404

        # Obtener todas las fechas de registros de postura para este paciente
        available_postura_dates = get_postura_summary(connection, patient_id)

        if not available_postura_dates:
            return jsonify({
                'exists': False,
                'message': 'No se encontraron datos de pruebas/postura para este paciente.',
                'redirect_url': url_for('patient.patient_detail', patient_id=patient_id)
            })
        
        return jsonify({
            'exists': True,
            'available_dates': available_postura_dates,
            'pdf_url_base': url_for('clinical.generate_plantillas_pdf', patient_id=patient_id)
        })

    except Exception as e:
        print(f"Error en check_plantillas_data_exists (PID {patient_id}): {e}")
        return jsonify({'exists': False, 'message': 'Error interno al verificar datos.'}), 500
    finally:
        if connection and connection.is_connected():
            connection.close()
            
@clinical_bp.route('/recibo/pdf/<int:id_recibo>')
@login_required
def generate_recibo_pdf(patient_id, id_recibo):
    """Genera el PDF para un recibo específico. Refactorizado y completo."""
    
    # 1. Lógica del Logo (No requiere DB, se ejecuta antes)
    logo_base64_uri = None
    try:
        logo_path = os.path.join(current_app.static_folder, 'img', 'logo.png')
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                logo_base64_uri = f"data:image/png;base64,{encoded_string}"
    except Exception as e:
        print(f"WARN generate_recibo_pdf: No se pudo cargar el logo: {e}")

    try:
        # 2. Conexión segura con Context Manager
        with get_db_cursor() as (connection, cursor):
            if not connection:
                flash('Error conectando a la base de datos.', 'danger')
                return redirect(url_for('clinical.manage_recibos', patient_id=patient_id))

            # 3. Obtener y validar Paciente
            patient = get_patient_by_id(connection, patient_id)
            if not patient:
                flash('Paciente no encontrado.', 'warning')
                return redirect(url_for('main'))

            # 4. Obtener datos del recibo
            receipt_data = get_specific_recibo(connection, id_recibo)

            # Verificar que el recibo exista y pertenezca al paciente
            if not receipt_data or receipt_data.get('id_px') != patient_id:
                flash(f'Recibo #{id_recibo} no encontrado o no pertenece a este paciente.', 'warning')
                return redirect(url_for('clinical.manage_recibos', patient_id=patient_id))

            # 5. Lógica de Información del Centro (RESTAURADA)
            id_centro_actual_dr = session.get('id_centro_dr')
            centro_info_for_pdf = None

            if id_centro_actual_dr and id_centro_actual_dr != 0:
                centro_info_for_pdf = get_centro_by_id(connection, id_centro_actual_dr)
            elif session.get('is_admin'):
                # Admin por defecto usa centro 1, o genérico si falla
                centro_info_for_pdf = get_centro_by_id(connection, 1)
                if not centro_info_for_pdf:
                    centro_info_for_pdf = {'nombre': 'Chiropractic Care Center (Admin)', 'direccion': 'N/A', 'cel': 'N/A', 'tel': 'N/A'}
            else:
                centro_info_for_pdf = {'nombre': 'Chiropractic Care Center', 'direccion': 'N/A', 'cel': 'N/A', 'tel': 'N/A'}

            # 6. Preparar datos para la plantilla
            receipt_data['patient_nombre_completo'] = f"{patient.get('nombre', '')} {patient.get('apellidop', '')} {patient.get('apellidom', '')}".strip()
            receipt_data['logo_base64_uri'] = logo_base64_uri
            receipt_data['current_year_for_pdf'] = datetime.now().year
            receipt_data['centro_info'] = centro_info_for_pdf

            # 7. Renderizar HTML
            html_content = render_template('recibo_pdf_template.html', data=receipt_data)

            # 8. Generar PDF en memoria
            pdf_buffer = BytesIO()
            pisa_status = pisa.CreatePDF(
                html_content.encode('utf-8'),
                dest=pdf_buffer,
                encoding='utf-8'
            )

            if pisa_status.err:
                print(f"Error pisa: {pisa_status.err}")
                flash('Ocurrió un error al generar el PDF.', 'danger')
                return redirect(url_for('clinical.manage_recibos', patient_id=patient_id, selected_id=id_recibo))

            pdf_buffer.seek(0)
            response = Response(pdf_buffer, mimetype='application/pdf')
            response.headers['Content-Disposition'] = f'inline; filename=recibo_px{patient_id}_rec{id_recibo}.pdf'
            return response

    except Exception as e:
        print(f"Error en generate_recibo_pdf (PID {patient_id}): {e}")
        flash('Error inesperado al generar PDF del recibo.', 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@clinical_bp.route('/reporte_integral_pdf')
@login_required
def generar_reporte_integral_pdf(patient_id):
    # 1. Lógica del Logo (Fuera de DB)
    logo_base64_uri = None
    try:
        logo_path = os.path.join(current_app.static_folder, 'img', 'logo.png')
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                logo_base64_uri = f"data:image/png;base64,{encoded_string}"
    except Exception as e:
        print(f"WARN: Error cargando logo: {e}")

    try:
        # 2. Conexión Segura
        with get_db_cursor() as (connection, cursor):
            if not connection:
                flash("Error de conexión.", "danger")
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))

            # 3. Recopilar Datos (Lógica Original Restaurada)
            patient_data = get_patient_by_id(connection, patient_id)
            anamnesis_data = get_latest_anamnesis(connection, patient_id)
            pruebas_data = get_latest_postura_overall(connection, patient_id)

            if not patient_data or not anamnesis_data or not pruebas_data:
                flash("Faltan datos esenciales (anamnesis o pruebas) para generar el informe.", "warning")
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))

            # 3.1 Obtener ruta absoluta de imagen frontal
            ruta_frontal_relativa = pruebas_data.get('frente')
            ruta_frontal_absoluta = os.path.join(current_app.root_path, 'static', ruta_frontal_relativa) if ruta_frontal_relativa else None

            # 3.2 Análisis objetivo
            hallazgos_calculados = analizar_coordenadas_postura(ruta_frontal_absoluta)

            # 3.3 Generar informe con IA (Importante: esta función debe existir en clinical_tools.py)
            informe_ia_texto = generar_informe_integral_con_ia(patient_data, anamnesis_data, pruebas_data, hallazgos_calculados)

            # 3.4 Datos del Doctor y Centro
            id_centro_sesion = session.get('id_centro_dr')
            centro_info = get_centro_by_id(connection, id_centro_sesion) if id_centro_sesion else None
            if not centro_info:
                centro_info = {'nombre': 'Chiropractic Care Center'}

            # 4. Preparar Datos para PDF
            def get_safe_path(key):
                path = pruebas_data.get(key)
                return os.path.join(current_app.root_path, 'static', path) if path else ''

            data_for_pdf = {
                'patient': patient_data,
                'anamnesis': anamnesis_data,
                'pruebas': pruebas_data,
                'informe_ia': informe_ia_texto,
                'today_str': datetime.now().strftime('%d/%m/%Y'),
                'logo_uri': logo_base64_uri,
                'edad_paciente': calculate_age(patient_data.get('nacimiento')),
                'doctor_name': session.get('nombre_dr', 'No especificado'),
                'centro_info': centro_info,
                'imagenes': {
                    'frente': get_safe_path('frente'),
                    'lado': get_safe_path('lado'),
                    'postura_extra': get_safe_path('postura_extra'),
                    'pies_frontal': get_safe_path('pies_frontal'),
                    'pies_trasera': get_safe_path('pies_trasera'),
                    'pies': get_safe_path('pies'), 
                }
            }
            
            # 5. Generar PDF con PISA
            html_content = render_template('reporte_integral_pdf.html', data=data_for_pdf)
            pdf_buffer = BytesIO()
            pisa_status = pisa.CreatePDF(html_content.encode('utf-8'), dest=pdf_buffer, encoding='utf-8')

            if pisa_status.err:
                flash('Ocurrió un error al generar el archivo PDF.', 'danger')
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))
            
            pdf_buffer.seek(0)
            return Response(pdf_buffer, mimetype='application/pdf', headers={'Content-Disposition': f'inline; filename=informe_integral_px{patient_id}.pdf'})

    except Exception as e:
        print(f"Error generando informe integral para PID {patient_id}: {e}")
        flash('Error inesperado al generar el informe integral.', 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@clinical_bp.route('/comparador')
@login_required
def comparador_postura(patient_id):
    """
    Muestra la página del comparador de posturas con las fechas disponibles.
    Refactorizado con get_db_cursor y validación de mínimos.
    """
    try:
        # 1. Conexión Optimizada
        with get_db_cursor() as (connection, cursor):
            if not connection:
                flash("Error de conexión a la base de datos.", "danger")
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))

            # 2. Validar Paciente
            patient = get_patient_by_id(connection, patient_id)
            if not patient:
                flash("Paciente no encontrado.", "warning")
                return redirect(url_for('main'))

            # 3. Obtener fechas disponibles
            available_dates = get_postura_summary(connection, patient_id)
            
            # 4. Validación de Negocio (Mínimo 2 registros para comparar)
            if not available_dates or len(available_dates) < 2:
                flash("Se necesitan al menos dos registros de pruebas de postura para comparar.", "info")
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))

            # 5. Renderizar
            return render_template('comparador_postura.html', 
                                   patient=patient, 
                                   available_dates=available_dates)

    except Exception as e:
        print(f"Error en comparador_postura (PID {patient_id}): {e}")
        flash("Ocurrió un error al cargar el comparador de posturas.", "danger")
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@clinical_bp.route('/reporte_visual_fechado')
@login_required
def reporte_visual_fechado(patient_id):
    """
    Muestra la página del reporte visual con selector de fecha.
    Refactorizado con get_db_cursor y lógica completa.
    """
    try:
        # 1. Conexión Optimizada
        with get_db_cursor() as (connection, cursor):
            if not connection:
                flash("Error de conexión.", "danger")
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))

            # 2. Lógica Original Restaurada
            patient = get_patient_by_id(connection, patient_id)
            if not patient:
                flash("Paciente no encontrado.", "warning")
                return redirect(url_for('main'))

            # Obtenemos las fechas donde hay registros de postura
            available_dates = get_postura_summary(connection, patient_id)

            if not available_dates:
                flash("No hay registros de pruebas de postura disponibles para este paciente.", "info")
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))

            # Renderizamos la plantilla
            return render_template('reporte_visual_fechado.html',
                                   patient=patient,
                                   available_dates=available_dates)

    except Exception as e:
        print(f"Error en reporte_visual_fechado (PID {patient_id}): {e}")
        flash("Ocurrió un error al cargar el reporte visual.", "danger")
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@clinical_bp.route('/api/add_note', methods=['POST'])
@login_required
def api_add_general_note(patient_id):
    """
    API endpoint para añadir una nueva nota general.
    Refactorizado con get_db_cursor.
    """
    data = request.get_json()
    note_text = data.get('note_text')
    
    # 1. Validación original restaurada
    if not note_text or not note_text.strip():
        return jsonify({'success': False, 'message': 'El texto de la nota no puede estar vacío.'}), 400

    try:
        # 2. Conexión optimizada
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                return jsonify({'success': False, 'message': 'Error de conexión DB.'}), 500
            
            # 3. Lógica original
            new_note_id = add_general_note(connection, patient_id, note_text.strip())
            
            return jsonify({'success': True, 'message': f'Nota #{new_note_id} guardada.'})

    except Exception as ex:
        print(f"Error en API add_general_note: {ex}")
        return jsonify({'success': False, 'message': 'Error del servidor al guardar la nota.'}), 500

@clinical_bp.route('/api/get_ultimo_seguimiento')
@login_required
def get_ultimo_seguimiento_api(patient_id):
    """
    Devuelve los detalles del último seguimiento registrado para copiarlo.
    Refactorizado con get_db_cursor.
    """
    try:
        # Usamos el gestor de contexto para manejo automático de la conexión
        with get_db_cursor() as (connection, cursor):
            if not connection:
                return jsonify({'success': False, 'message': 'Error de conexión a BD.'})

            # 1. Obtener lista de seguimientos (ya viene ordenada por fecha DESC)
            summary = get_seguimiento_summary(connection, patient_id)
            
            if not summary:
                return jsonify({'success': False, 'message': 'No hay seguimientos previos.'})
                
            # 2. Tomar el ID del más reciente (el primero de la lista)
            last_id = summary[0]['id_seguimiento']
            
            # 3. Obtener el detalle completo
            details = get_specific_seguimiento(connection, last_id)
            
            if details:
                # Limpiamos datos que no queremos copiar (como la fecha o el ID)
                # y devolvemos TODOS los campos necesarios
                datos_a_copiar = {
                    'success': True,
                    # Segmentos vertebrales
                    'occipital': details.get('occipital'),
                    'atlas': details.get('atlas'),
                    'axis': details.get('axis'),
                    'c3': details.get('c3'), 'c4': details.get('c4'), 'c5': details.get('c5'),
                    'c6': details.get('c6'), 'c7': details.get('c7'),
                    't1': details.get('t1'), 't2': details.get('t2'), 't3': details.get('t3'),
                    't4': details.get('t4'), 't5': details.get('t5'), 't6': details.get('t6'),
                    't7': details.get('t7'), 't8': details.get('t8'), 't9': details.get('t9'),
                    't10': details.get('t10'), 't11': details.get('t11'), 't12': details.get('t12'),
                    'l1': details.get('l1'), 'l2': details.get('l2'), 'l3': details.get('l3'),
                    'l4': details.get('l4'), 'l5': details.get('l5'),
                    'sacro': details.get('sacro'), 'coxis': details.get('coxis'),
                    'iliaco_d': details.get('iliaco_d'), 'iliaco_i': details.get('iliaco_i'),
                    'pubis': details.get('pubis'),
                    # Otros datos
                    'notas': details.get('notas'),
                    'terapia': details.get('terapia', '0,') 
                }
                return jsonify(datos_a_copiar)
            else:
                return jsonify({'success': False, 'message': 'Error al leer el detalle del último seguimiento.'})

    except Exception as e:
        print(f"Error API copiar seguimiento: {e}")
        return jsonify({'success': False, 'message': 'Error interno del servidor.'})


@clinical_bp.route('/api/mark_notes_seen', methods=['POST'])
@login_required
def api_mark_notes_seen(patient_id):
    """
    API endpoint para marcar una lista de notas como vistas.
    """
    data = request.get_json()
    note_ids = data.get('note_ids')
    
    # 1. Validación original restaurada
    if not note_ids or not isinstance(note_ids, list):
        return jsonify({'success': False, 'message': 'IDs de nota no proporcionados.'}), 400

    try:
        # 2. Conexión optimizada
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                return jsonify({'success': False, 'message': 'Error de conexión DB.'}), 500
            
            rows_affected = mark_notes_as_seen(connection, note_ids)
            
            # 3. Mensaje de éxito original restaurado
            return jsonify({'success': True, 'message': f'{rows_affected} notas marcadas como vistas.'})

    except Exception as ex:
        print(f"Error en API mark_notes_seen: {ex}")
        return jsonify({'success': False, 'message': 'Error del servidor.'}), 500

@clinical_bp.route('/api/get_postura_data')
@login_required
def get_postura_data_for_date(patient_id):
    """
    Endpoint de API para obtener las rutas de las imágenes de postura para una fecha específica.
    Devuelve los datos en formato JSON.
    """
    # Obtenemos la fecha que nos pide el JavaScript desde los parámetros de la URL
    fecha_solicitada = request.args.get('fecha')
    if not fecha_solicitada:
        return jsonify({'error': 'No se proporcionó una fecha.'}), 400

    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            return jsonify({'error': 'Error de conexión a la base de datos.'}), 500

        # Usamos una función que ya existe para obtener los datos de ese día
        postura_data = get_specific_postura_by_date(connection, patient_id, fecha_solicitada)

        if not postura_data:
            # Si no hay datos para esa fecha, devolvemos un JSON vacío
            return jsonify({})

        # Si encontramos datos, preparamos un diccionario con las rutas
        image_paths = {
            'frontal': url_for('static', filename=postura_data.get('frente')) if postura_data.get('frente') else None,
            'lateral': url_for('static', filename=postura_data.get('lado')) if postura_data.get('lado') else None,
            'lateral_der': url_for('static', filename=postura_data.get('postura_extra')) if postura_data.get('postura_extra') else None
        }
        
        return jsonify(image_paths)

    except Exception as e:
        print(f"Error en get_postura_data_for_date (PID {patient_id}): {e}")
        return jsonify({'error': 'Error interno del servidor.'}), 500
    finally:
        if connection and connection.is_connected():
            connection.close()


@clinical_bp.route('/recibo/<int:recibo_id>/abonar', methods=['POST'])
@login_required
def abonar_recibo_route(patient_id, recibo_id):
    try:
        monto = request.form.get('monto_abono', type=float)
        metodo = request.form.get('metodo_pago_abono')
        notas = request.form.get('notas_abono', '')

        if not monto or monto <= 0:
            return jsonify({'success': False, 'message': "El monto debe ser mayor a 0."}), 400

        with get_db_cursor(commit=True) as (connection, cursor):
            exito = registrar_abono(connection, recibo_id, monto, metodo, notas)
            
            if exito:
                # 1. Guardamos el mensaje para que salga al recargar la página
                flash("Abono registrado exitosamente.", "success")
                
                # 2. Enviamos la URL del PDF al navegador
                return jsonify({
                    'success': True,
                    'pdf_url': url_for('clinical.generate_recibo_pdf', patient_id=patient_id, id_recibo=recibo_id)
                })
            else:
                return jsonify({'success': False, 'message': "Error al registrar el abono."}), 400

    except Exception as e:
        current_app.logger.error(f"Error en abono: {e}")
        return jsonify({'success': False, 'message': "Ocurrió un error interno."}), 500
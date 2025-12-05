import os
from flask import (
    Blueprint, render_template, request, redirect, jsonify, session, flash, url_for, current_app
)
from datetime import datetime

from forms import PatientForm

# 1. IMPORTAMOS LA NUEVA HERRAMIENTA
from db.connection import connect_to_db, get_db_cursor

from db.patients import (
    add_patient, get_patient_by_id, search_patients_by_name,
    update_patient_details, get_unseen_notes_for_patient,
    get_patient_history_timeline
)
from db.clinical import (
    get_specific_antecedente_by_date, get_postura_summary
)
from db.finance import (
    get_plan_cuidado_activo_para_paciente, analizar_adicionales_plan,
    get_active_plan_status,get_total_deuda_paciente, get_primer_recibo_pendiente
)

from utils.date_manager import to_frontend_str, parse_date
from decorators import login_required, admin_required

patient_bp = Blueprint('patient', 
                       __name__, 
                       template_folder='../../templates')

@patient_bp.route('/paciente/nuevo', methods=['GET', 'POST'])
@login_required 
def add_patient_route():
    form = PatientForm()
    if form.validate_on_submit():
        try:
            id_dr_actual = session.get('id_dr')
            if id_dr_actual is None: 
                flash("Error de sesión. Inicie sesión de nuevo.", 'danger')
                return redirect(url_for('auth.login'))

            fecha_registro = to_frontend_str(datetime.now())
            
            nacimiento_fmt = None
            if form.nacimiento.data:
                nacimiento_fmt = to_frontend_str(form.nacimiento.data)
            
            telcasa_num = form.telcasa.data or 0
            emergencia_num = form.emergencia.data or 0
            cel_num = form.cel.data 

            # Usamos commit=True para guardar el nuevo paciente
            with get_db_cursor(commit=True) as (connection, cursor):
                if not connection:
                    flash('Error conectando a la base de datos.', 'danger')
                else:
                    nuevo_id = add_patient(
                        connection=connection, id_dr=id_dr_actual, fecha=fecha_registro,
                        comoentero=form.comoentero.data, 
                        nombre=form.nombre.data, 
                        apellidop=form.apellidop.data, 
                        apellidom=form.apellidom.data,
                        nacimiento=nacimiento_fmt, 
                        direccion=form.direccion.data, 
                        estadocivil=form.estadocivil.data,
                        hijos=form.hijos.data, 
                        ocupacion=form.ocupacion.data, 
                        telcasa=telcasa_num, 
                        cel=cel_num,
                        correo=form.correo.data, 
                        emergencia=emergencia_num, 
                        contacto=form.contacto.data, 
                        parentesco=form.parentesco.data
                    )

                    if nuevo_id:
                        flash(f'Paciente {form.nombre.data} {form.apellidop.data} registrado con éxito (ID: {nuevo_id}).', 'success')
                        return redirect(url_for('patient.patient_detail', patient_id=nuevo_id))
                    else:
                        flash('Hubo un error al registrar el paciente.', 'danger')

        except Exception as ex:
            current_app.logger.error(f"Error inesperado en add_patient_route: {ex}")
            flash(f"Ocurrió un error inesperado.", 'danger')

    return render_template('add_patient.html', form=form)

@patient_bp.route('/paciente/detalle/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    try:
        # Solo lectura, no necesitamos commit=True
        with get_db_cursor() as (connection, cursor):
            if not connection:
                flash('Error conectando a la base de datos.', 'danger')
                return redirect(url_for('main'))

            patient = get_patient_by_id(connection, patient_id)
            if not patient:
                flash('Paciente no encontrado.', 'warning')
                return redirect(url_for('main'))
            
            postura_records = get_postura_summary(connection, patient_id)
            num_postura_records = len(postura_records) if postura_records else 0
            
            active_plan_info = get_active_plan_status(connection, patient_id)
            adicionales_status = []

            if active_plan_info:
                adicionales_status = analizar_adicionales_plan(connection, active_plan_info['id_plan'])

            today_str = to_frontend_str(datetime.now())
            todays_antecedente = get_specific_antecedente_by_date(connection, patient_id, today_str)
            has_antecedentes_today = (todays_antecedente is not None)
            todays_antecedente_id = todays_antecedente.get('id_antecedente') if todays_antecedente else None

            unseen_notes_list = get_unseen_notes_for_patient(connection, patient_id)
            historial_clinico = get_patient_history_timeline(connection, patient_id)

            deuda_total = get_total_deuda_paciente(connection, patient_id)
            id_recibo_deuda = get_primer_recibo_pendiente(connection, patient_id)

            return render_template('patient_detail.html',
                                   patient=patient,
                                   has_antecedentes_today=has_antecedentes_today,
                                   todays_antecedente_id=todays_antecedente_id,
                                   active_plan_info=active_plan_info,      
                                   adicionales_status=adicionales_status,
                                   num_postura_records=num_postura_records,
                                   unseen_notes=unseen_notes_list,
                                   historial=historial_clinico,
                                   deuda_total=deuda_total,
                                   id_recibo_deuda=id_recibo_deuda
                                   )

    except Exception as e:
        current_app.logger.error(f"Error en patient_detail para patient_id {patient_id}: {e}")
        flash('Ocurrió un error al cargar los detalles del paciente.', 'danger')
        return redirect(url_for('main'))

@patient_bp.route('/paciente/editar/<int:patient_id>', methods=['GET', 'POST'])
@admin_required
def edit_patient_route(patient_id):
    try:
        # Usamos commit=True para soportar las ediciones (POST)
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                flash('Error conectando a la base de datos.', 'danger')
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))

            patient = get_patient_by_id(connection, patient_id)
            if not patient:
                flash('Paciente no encontrado.', 'warning')
                return redirect(url_for('main'))

            form = PatientForm()

            if form.validate_on_submit():
                patient_data_to_update = {'id_px': patient_id}
                
                patient_data_to_update['comoentero'] = form.comoentero.data
                patient_data_to_update['nombre'] = form.nombre.data
                patient_data_to_update['apellidop'] = form.apellidop.data
                patient_data_to_update['apellidom'] = form.apellidom.data
                
                if form.nacimiento.data:
                    patient_data_to_update['nacimiento'] = to_frontend_str(form.nacimiento.data)
                else:
                    patient_data_to_update['nacimiento'] = None
                
                patient_data_to_update['direccion'] = form.direccion.data
                patient_data_to_update['estadocivil'] = form.estadocivil.data
                patient_data_to_update['hijos'] = form.hijos.data
                patient_data_to_update['ocupacion'] = form.ocupacion.data
                
                patient_data_to_update['telcasa'] = int(form.telcasa.data) if form.telcasa.data else 0
                patient_data_to_update['cel'] = int(form.cel.data)
                patient_data_to_update['emergencia'] = int(form.emergencia.data) if form.emergencia.data else 0
                
                patient_data_to_update['correo'] = form.correo.data
                patient_data_to_update['contacto'] = form.contacto.data
                patient_data_to_update['parentesco'] = form.parentesco.data

                success = update_patient_details(connection, patient_data_to_update)
                
                if success:
                    flash('Datos del paciente actualizados exitosamente.', 'success')
                    return redirect(url_for('patient.patient_detail', patient_id=patient_id))
                else:
                    flash('Error al actualizar los datos del paciente.', 'danger')

            elif request.method == 'GET':
                patient_data_for_form = patient.copy()
                if patient_data_for_form.get('nacimiento'):
                    patient_data_for_form['nacimiento'] = parse_date(patient_data_for_form['nacimiento'])
                
                form = PatientForm(data=patient_data_for_form)

            return render_template('edit_patient.html', form=form, patient=patient)

    except Exception as e:
        current_app.logger.error(f"Error en edit_patient_route (PID {patient_id}): {e}")
        flash('Ocurrió un error inesperado al editar el paciente.', 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))

@patient_bp.route('/api/search_patients') 
@login_required
def api_search_patients():
    try:
        search_term = request.args.get('term', '') 
        
        # Lectura rápida para la barra de búsqueda
        with get_db_cursor() as (connection, cursor):
            if not connection:
                 return jsonify({"error": "Database connection failed"}), 500 
            
            patients = search_patients_by_name(connection, search_term)
            return jsonify(patients) 

    except Exception as e:
        current_app.logger.error(f"Error en API search_patients: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500
import os
from flask import (
    Blueprint, render_template, request, redirect, jsonify, session, flash, url_for, current_app
)
from mysql.connector import Error
from datetime import datetime

from forms import PatientForm

# Importar funciones de base de datos necesarias para ESTAS rutas
from database import (
    connect_to_db, add_patient, get_patient_by_id, search_patients_by_name,
    update_patient_details, get_specific_antecedente_by_date, 
    get_plan_cuidado_activo_para_paciente, analizar_adicionales_plan,
    get_postura_summary, get_active_plan_status, get_unseen_notes_for_patient
)
from utils.date_manager import to_frontend_str, to_db_str, parse_date, parse_date
# Importar los decoradores
from decorators import login_required, admin_required

# 1. Crear el Blueprint
# No usamos url_prefix porque tenemos rutas como /api/search_patients
patient_bp = Blueprint('patient', 
                       __name__, 
                       template_folder='../../templates')

# 2. Mover las rutas de 'main.py' aquí
# 3. Cambiar @app.route por @patient_bp.route
# 4. Actualizar todos los url_for() para que usen prefijos

@patient_bp.route('/paciente/nuevo', methods=['GET', 'POST'])
@login_required 
def add_patient_route():
    
    # --- USAR FLASK-WTF ---
    form = PatientForm() # 1. Instanciar el formulario

    # 2. Remplazar 'request.method == POST' con 'form.validate_on_submit()'
    if form.validate_on_submit():
        connection = None 
        try:
            id_dr_actual = session.get('id_dr')
            if id_dr_actual is None: 
                flash("Error de sesión. Inicie sesión de nuevo.", 'danger')
                return redirect(url_for('auth.login'))

            fecha_registro = to_frontend_str(datetime.now())
            
            # --- 3. Obtener datos limpios desde form.campo.data ---
            # ¡Adiós a todos los request.form.get() y .strip()!
            
            # Manejo especial para la fecha (viene como objeto date)
            nacimiento_fmt = ''
            if form.nacimiento.data:
                nacimiento_fmt = to_frontend_str(form.nacimiento.data)
            
            # Manejo de números (vienen como None si están vacíos gracias a Optional())
            # La base de datos espera 0 si está vacío, o el número.
            telcasa_num = form.telcasa.data or 0
            emergencia_num = form.emergencia.data or 0
            # 'cel' es requerido, así que debe tener valor
            cel_num = form.cel.data 

            connection = connect_to_db()
            if not connection:
                flash('Error conectando a la base de datos.', 'danger')
                return render_template('add_patient.html', form=form) # 4. Pasar el form

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
        finally:
            if connection and connection.is_connected():
                connection.close()

    # Si es GET o la validación falla, renderizar el template con el formulario.
    # Los errores se mostrarán automáticamente.
    return render_template('add_patient.html', form=form) # 4. Pasar el form

@patient_bp.route('/paciente/detalle/<int:patient_id>')
@login_required
def patient_detail(patient_id):
    connection = None
    num_postura_records = 0
    try:
        connection = connect_to_db()
        if not connection:
            flash('Error conectando a la base de datos.', 'danger')
            return redirect(url_for('main')) # CAMBIO: 'main'

        patient = get_patient_by_id(connection, patient_id)
        if not patient:
            flash('Paciente no encontrado.', 'warning')
            return redirect(url_for('main')) # CAMBIO: 'main'
        
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

        return render_template('patient_detail.html',
                               patient=patient,
                               has_antecedentes_today=has_antecedentes_today,
                               todays_antecedente_id=todays_antecedente_id,
                               active_plan_info=active_plan_info,      
                               adicionales_status=adicionales_status,
                               num_postura_records=num_postura_records,
                               unseen_notes=unseen_notes_list
                               )

    except Exception as e:
        current_app.logger.error(f"Error en patient_detail para patient_id {patient_id}: {e}")
        flash('Ocurrió un error al cargar los detalles del paciente.', 'danger')
        return redirect(url_for('main')) # CAMBIO: 'main'
    finally:
        if connection and connection.is_connected():
            connection.close()

@patient_bp.route('/paciente/editar/<int:patient_id>', methods=['GET', 'POST'])
@admin_required # Mantenemos admin_required
def edit_patient_route(patient_id):
    connection = None
    patient = None
    try:
        connection = connect_to_db()
        if not connection:
            flash('Error conectando a la base de datos.', 'danger')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        # 1. Obtener los datos del paciente (como ya lo hacías)
        patient = get_patient_by_id(connection, patient_id)
        if not patient:
            flash('Paciente no encontrado.', 'warning')
            return redirect(url_for('main'))

        # 2. Instanciar el formulario
        form = PatientForm()

        # 3. Lógica de POST (reemplaza 'request.method == POST')
        if form.validate_on_submit():
            
            # 4. El formulario es válido, armar el diccionario para la BBDD
            patient_data_to_update = {'id_px': patient_id}
            
            patient_data_to_update['comoentero'] = form.comoentero.data
            patient_data_to_update['nombre'] = form.nombre.data
            patient_data_to_update['apellidop'] = form.apellidop.data
            patient_data_to_update['apellidom'] = form.apellidom.data
            
            # Convertir objeto 'date' de WTForms a string 'dd/mm/YYYY'
            if form.nacimiento.data:
                patient_data_to_update['nacimiento'] = to_frontend_str(form.nacimiento.data)
            else:
                patient_data_to_update['nacimiento'] = '' # O None, según tu BBDD
            
            patient_data_to_update['direccion'] = form.direccion.data
            patient_data_to_update['estadocivil'] = form.estadocivil.data
            patient_data_to_update['hijos'] = form.hijos.data
            patient_data_to_update['ocupacion'] = form.ocupacion.data
            
            # Convertir strings del form a int para la BBDD (si es necesario)
            patient_data_to_update['telcasa'] = int(form.telcasa.data) if form.telcasa.data else 0
            patient_data_to_update['cel'] = int(form.cel.data) # Este es requerido
            patient_data_to_update['emergencia'] = int(form.emergencia.data) if form.emergencia.data else 0
            
            patient_data_to_update['correo'] = form.correo.data
            patient_data_to_update['contacto'] = form.contacto.data
            patient_data_to_update['parentesco'] = form.parentesco.data

            # 5. Llamar a la BBDD (como ya lo hacías)
            success = update_patient_details(connection, patient_data_to_update)
            
            if success:
                flash('Datos del paciente actualizados exitosamente.', 'success')
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))
            else:
                flash('Error al actualizar los datos del paciente.', 'danger')
                # La función continuará al render_template de abajo

        elif request.method == 'GET':
            # 6. Lógica de GET: Pre-poblar el formulario
            # Copiamos los datos del paciente para no modificar el original
            patient_data_for_form = patient.copy()
            
            # Convertir el string 'dd/mm/YYYY' de la BBDD a un objeto 'date'
            # que el campo DateField de WTForms puede entender.
            if patient_data_for_form.get('nacimiento'):
                patient_data_for_form['nacimiento'] = parse_date(patient_data_for_form['nacimiento'])
            
            # Instanciar el formulario CON los datos del paciente
            form = PatientForm(data=patient_data_for_form)

        # 7. Renderizar la plantilla
        # Si es GET, muestra el form poblado.
        # Si es POST y falló, muestra el form con los errores.
        return render_template('edit_patient.html', form=form, patient=patient)

    except Exception as e:
        current_app.logger.error(f"Error en edit_patient_route (PID {patient_id}): {e}")
        flash('Ocurrió un error inesperado al editar el paciente.', 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))
    finally:
        if connection and connection.is_connected():
            connection.close()

@patient_bp.route('/api/search_patients') 
@login_required
def api_search_patients():
    connection = None
    try:
        search_term = request.args.get('term', '') 
        connection = connect_to_db()
        if not connection:
             return jsonify({"error": "Database connection failed"}), 500 
        
        patients = search_patients_by_name(connection, search_term)
        return jsonify(patients) 

    except Exception as e:
        current_app.logger.error(f"Error en API search_patients: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500
    finally:
        if connection and connection.is_connected():
            connection.close()
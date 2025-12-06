import os
from flask import (
    Blueprint, render_template, request, redirect, jsonify, session, flash, url_for,
    current_app
)
from mysql.connector import Error
from datetime import datetime, date
from werkzeug.security import generate_password_hash
from decimal import Decimal

# 1. IMPORTAR LA NUEVA HERRAMIENTA
from db.connection import connect_to_db, get_db_cursor

# Importar funciones de base de datos
from forms import (RegisterForm, EditDoctorForm, ChangePasswordForm, ClinicaForm, ProductoServicioForm,
                   FormIngresos, FormUtilidad, FormNuevosPacientes, FormPacientesFrecuentes, FormSeguimientos, 
                   FormUsoPlanes, FormCuentasPorCobrar, FormCorteCaja)
from db.auth import (
    add_user, get_all_doctors, get_doctor_by_id,
    update_doctor_details, update_doctor_password, set_doctor_active_status,
    count_total_doctores, get_all_centros, get_centro_by_id, add_centro, update_centro
)
from db.patients import count_total_pacientes
from db.reports import (
    count_seguimientos_hoy, get_ingresos_por_periodo, get_ingresos_por_doctor_periodo,
    get_utilidad_estimada_por_periodo, get_utilidad_estimada_por_doctor_periodo,
    get_pacientes_nuevos_por_periodo, get_pacientes_mas_frecuentes,
    get_seguimientos_por_doctor_periodo, get_uso_planes_de_cuidado,
    get_cuentas_por_cobrar, get_corte_caja_detallado
)
from db.finance import (
    get_all_productos_servicios, get_producto_servicio_by_id,
    add_producto_servicio, update_producto_servicio, 
    set_producto_servicio_active_status, actualizar_stock_producto
)
from utils.date_manager import to_frontend_str
from decorators import login_required, admin_required

admin_bp = Blueprint('admin', 
                     __name__, 
                     template_folder='../../templates',
                     url_prefix='/admin') 

@admin_bp.route('/register', methods=['GET', 'POST']) 
@admin_required
def register():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        usuario = request.form.get('usuario', '').strip()
        password = request.form.get('contraseña')
        confirm_password = request.form.get('confirm_password')
        es_admin_nuevo_dr_str = request.form.get('es_admin_nuevo_dr')
        centro_nuevo_dr = 0 if es_admin_nuevo_dr_str == 'on' else 1

        if not nombre or not usuario or not password or not confirm_password:
            flash('Todos los campos son requeridos.', 'danger')
        elif len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'warning')
        elif password != confirm_password:
            flash('Las contraseñas no coinciden.', 'danger')
        else:
            try:
                # Usamos commit=True porque vamos a escribir en la DB
                with get_db_cursor(commit=True) as (connection, cursor):
                    if not connection:
                        flash('Error de conexión a la base de datos.', 'danger')
                    else:
                        user_status = add_user(connection, nombre, usuario, password, centro_nuevo_dr)
                        
                        if user_status == "exists":
                            flash('El nombre de usuario ya está en uso.', 'danger')
                        elif user_status:
                            flash(f"Doctor '{nombre}' registrado exitosamente.", 'success')
                            return redirect(url_for('admin.admin_manage_doctores'))
                        else:
                            flash('Error al registrar el doctor en la base de datos.', 'danger')
            except Exception as e:
                print(f"Error en register: {e}")
                flash("Ocurrió un error inesperado durante el registro.", "danger")
        
        return render_template('register.html', 
                               nombre_prev=request.form.get('nombre',''), 
                               usuario_prev=request.form.get('usuario',''),
                               es_admin_prev = (request.form.get('es_admin_nuevo_dr') == 'on')
                               )
    return render_template('register.html', nombre_prev='', usuario_prev='', es_admin_prev=False)

@admin_bp.route('/doctor/crear', methods=['GET', 'POST']) 
@admin_required
def admin_create_doctor():
    form = RegisterForm()
    
    # 1. Cargar centros (Lectura)
    try:
        with get_db_cursor() as (conn, cursor):
            if conn:
                centros = get_all_centros(conn)
                form.centro.choices = [(c['id_centro'], c['nombre']) for c in centros if c['id_centro'] > 0]
                form.centro.default = 1
                form.process(request.form)
            else:
                flash("Error de conexión al cargar centros.", "danger")
    except Exception as e:
        flash(f"Error al cargar centros: {e}", "danger")

    # 2. Guardar nuevo doctor (Escritura)
    if form.validate_on_submit():
        try:
            nombre = form.nombre.data
            usuario = form.usuario.data
            password = form.contraseña.data
            es_admin = form.es_admin_nuevo_dr.data
            centro_id_form = form.centro.data

            centro_a_usar = 0 if es_admin else (centro_id_form if centro_id_form and centro_id_form > 0 else 1)

            with get_db_cursor(commit=True) as (connection, cursor):
                if not connection:
                    flash('Error de conexión a la base de datos.', 'danger')
                else:
                    nuevo_id_dr = add_user(connection, nombre, usuario, password, centro_a_usar)
                    if nuevo_id_dr:
                        flash(f'Doctor {nombre} creado exitosamente con ID: {nuevo_id_dr}.', 'success')
                        return redirect(url_for('admin.admin_manage_doctores'))
                    else:
                        flash('El nombre de usuario ya existe o hubo un error.', 'danger')
        
        except Exception as e:
            flash(f"Error al crear doctor: {e}", "danger")
        
        return render_template('admin/doctor_crear_form.html', form=form, es_admin_prev=form.es_admin_nuevo_dr.data)

    es_admin_prev = request.form.get('es_admin_nuevo_dr') == 'on' if request.method == 'POST' else False
    return render_template('admin/doctor_crear_form.html', form=form, es_admin_prev=es_admin_prev)


@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    admin_name = session.get('nombre_dr', 'Admin')
    num_pacientes = 0
    num_doctores = 0
    num_seguimientos_hoy = 0

    try:
        with get_db_cursor() as (connection, cursor):
            if not connection:
                flash("Error de conexión a la base de datos.", "danger")
            else:
                num_pacientes = count_total_pacientes(connection)
                num_doctores = count_total_doctores(connection)
                today_for_db = to_frontend_str(datetime.now())
                num_seguimientos_hoy = count_seguimientos_hoy(connection, today_for_db)
    except Exception as e:
        print(f"Error en admin_dashboard: {e}")
        flash("Ocurrió un error al cargar el dashboard.", "danger")
        
    return render_template('admin/dashboard_admin.html',
                           admin_name=admin_name,
                           num_pacientes=num_pacientes,
                           num_doctores=num_doctores,
                           num_seguimientos_hoy=num_seguimientos_hoy)

# --- RUTAS DE GESTIÓN DE PRODUCTOS ---

@admin_bp.route('/productos')
@admin_required
def admin_manage_productos():
    productos = []
    try:
        with get_db_cursor() as (connection, cursor):
            if connection:
                productos = get_all_productos_servicios(connection, include_inactive=True)
            else:
                flash("Error de conexión.", "danger")
    except Exception as e:
        print(f"Error en admin_manage_productos: {e}")
        flash("Error al cargar productos.", "danger")
    
    return render_template('admin/productos_lista.html', productos=productos)

@admin_bp.route('/producto/nuevo', methods=['GET', 'POST'])
@admin_required
def admin_add_producto():
    form = ProductoServicioForm()
    
    if form.validate_on_submit():
        try:
            data_to_create = {
                'nombre': form.nombre.data,
                'costo': form.costo.data,
                'venta': form.venta.data,
                'adicional': form.adicional.data
            }
            
            with get_db_cursor(commit=True) as (connection, cursor):
                if connection:
                    success = add_producto_servicio(connection, data_to_create)
                    if success:
                        flash(f'Producto/Servicio "{data_to_create["nombre"]}" creado exitosamente.', 'success')
                        return redirect(url_for('admin.admin_manage_productos'))
                    else:
                        flash('Error al crear el producto (posible nombre duplicado).', 'danger')
                else:
                    flash('Error de conexión.', 'danger')
        
        except Exception as e:
            flash(f"Error inesperado: {e}", "danger")

    return render_template('admin/producto_form.html', form=form, title="Crear Nuevo Producto/Servicio", producto=None)


@admin_bp.route('/producto/editar/<int:id_prod>', methods=['GET', 'POST'])
@admin_required
def admin_edit_producto(id_prod):
    try:
        # Usamos commit=True para manejar tanto GET (lectura) como POST (escritura) en un solo bloque seguro
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                flash('Error conectando a la base de datos.', 'danger')
                return redirect(url_for('admin.admin_manage_productos'))

            producto = get_producto_servicio_by_id(connection, id_prod)
            if not producto:
                flash('Producto o servicio no encontrado.', 'warning')
                return redirect(url_for('admin.admin_manage_productos'))

            form = ProductoServicioForm()

            if form.validate_on_submit():
                # Lógica de detección de cambios
                form_nombre = form.nombre.data or ""
                form_costo = form.costo.data if form.costo.data is not None else Decimal('0.00')
                form_venta = form.venta.data if form.venta.data is not None else Decimal('0.00')
                form_adicional = form.adicional.data
                
                db_nombre = str(producto.get('nombre')) if producto.get('nombre') is not None else ""
                db_costo = Decimal(str(producto.get('costo'))) if producto.get('costo') is not None else Decimal('0.00')
                db_venta = Decimal(str(producto.get('venta'))) if producto.get('venta') is not None else Decimal('0.00')
                db_adicional = int(producto.get('adicional')) if producto.get('adicional') is not None else 0
                
                data_changed = (
                    form_nombre != db_nombre or
                    form_costo != db_costo or
                    form_venta != db_venta or
                    form_adicional != db_adicional
                )
                
                if not data_changed:
                    flash("No se detectaron cambios en los datos.", "info")
                    return redirect(url_for('admin.admin_manage_productos'))
                
                data_to_update = {
                    'id_prod': id_prod,
                    'nombre': form.nombre.data,
                    'costo': form.costo.data,
                    'venta': form.venta.data,
                    'adicional': form.adicional.data
                }

                success = update_producto_servicio(connection, data_to_update)
                if success:
                    flash(f'Producto/Servicio "{data_to_update["nombre"]}" actualizado exitosamente.', 'success')
                    return redirect(url_for('admin.admin_manage_productos'))
                else:
                    flash('Error al actualizar el producto.', 'danger')

            elif request.method == 'GET':
                form = ProductoServicioForm(data=producto)

            return render_template('admin/producto_form.html', 
                                   form=form, 
                                   title=f'Editar Producto/Servicio: {producto["nombre"]}', 
                                   producto=producto)

    except Exception as e:
        print(f"Error en admin_edit_producto (ID {id_prod}): {e}")
        flash('Ocurrió un error inesperado al editar.', 'danger')
        return redirect(url_for('admin.admin_manage_productos'))


@admin_bp.route('/producto/toggle_status/<int:id_prod>', methods=['POST'])
@admin_required
def admin_toggle_producto_status(id_prod):
    try:
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                flash("Error de conexión.", "danger")
                return redirect(url_for('admin.admin_manage_productos'))

            producto = get_producto_servicio_by_id(connection, id_prod)
            if not producto:
                flash("Producto no encontrado.", "warning")
            else:
                nuevo_estado = not producto['esta_activo']
                success = set_producto_servicio_active_status(connection, id_prod, nuevo_estado)
                
                if success:
                    accion = "habilitado" if nuevo_estado else "deshabilitado"
                    flash(f"Producto '{producto['nombre']}' {accion}.", "success")
                else:
                    flash("Error al cambiar el estado.", "danger")
    except Exception as e:
        print(f"Error en toggle_status: {e}")
        flash("Error inesperado.", "danger")
        
    return redirect(url_for('admin.admin_manage_productos'))
    

@admin_bp.route('/doctores')
@admin_required
def admin_manage_doctores():
    doctores = []
    try:
        with get_db_cursor() as (connection, cursor):
            if connection:
                doctores = get_all_doctors(connection, include_inactive=True)
            else:
                flash("Error de conexión.", "danger")
    except Exception as e:
        print(f"Error en admin_manage_doctores: {e}")
        flash("Error al cargar doctores.", "danger")
    
    return render_template('admin/doctores_lista.html', doctores=doctores)

@admin_bp.route('/doctor/editar/<int:id_dr>', methods=['GET', 'POST'])
@admin_required
def admin_edit_doctor(id_dr):
    try:
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                flash('Error conectando a la base de datos.', 'danger')
                return redirect(url_for('admin.admin_manage_doctores'))

            doctor = get_doctor_by_id(connection, id_dr)
            if not doctor:
                flash('Doctor no encontrado.', 'warning')
                return redirect(url_for('admin.admin_manage_doctores'))

            centros = get_all_centros(connection)
            form = EditDoctorForm()
            form.centro.choices = [(c['id_centro'], c['nombre']) for c in centros if c['id_centro'] > 0]

            if form.validate_on_submit():
                nombre = form.nombre.data
                usuario = form.usuario.data
                es_admin = form.es_admin_nuevo_dr.data
                centro_id_form = form.centro.data

                centro_a_usar = 0 if es_admin else (centro_id_form if centro_id_form and centro_id_form > 0 else 1)
                
                doctor_data_to_update = {
                    'id_dr': id_dr,
                    'nombre': nombre,
                    'usuario': usuario,
                    'centro': centro_a_usar
                }
                
                success = update_doctor_details(connection, doctor_data_to_update)
                if success:
                    flash('Datos actualizados exitosamente.', 'success')
                    return redirect(url_for('admin.admin_manage_doctores'))
                else:
                    flash('Error al actualizar (posible usuario duplicado).', 'danger')

            elif request.method == 'GET':
                doctor_data_for_form = doctor.copy()
                doctor_data_for_form['es_admin_nuevo_dr'] = (doctor.get('centro') == 0)
                form = EditDoctorForm(data=doctor_data_for_form)
                form.centro.choices = [(c['id_centro'], c['nombre']) for c in centros if c['id_centro'] > 0]
                if not doctor_data_for_form['es_admin_nuevo_dr']:
                    form.centro.data = doctor_data_for_form.get('centro')

            return render_template('admin/doctor_form.html', form=form, doctor=doctor)

    except Exception as e:
        print(f"Error en admin_edit_doctor: {e}")
        flash('Ocurrió un error inesperado.', 'danger')
        return redirect(url_for('admin.admin_manage_doctores'))


@admin_bp.route('/doctor/cambiar_password/<int:id_dr>', methods=['GET', 'POST'])
@admin_required
def admin_change_doctor_password(id_dr):
    form = ChangePasswordForm()
    try:
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                return redirect(url_for('admin.admin_manage_doctores'))

            doctor = get_doctor_by_id(connection, id_dr)
            if not doctor:
                flash('Doctor no encontrado.', 'warning')
                return redirect(url_for('admin.admin_manage_doctores'))

            if form.validate_on_submit():
                nueva_password = form.nueva_contraseña.data
                success = update_doctor_password(connection, id_dr, nueva_password)
                
                if success:
                    flash(f'Contraseña actualizada exitosamente.', 'success')
                    return redirect(url_for('admin.admin_manage_doctores'))
                else:
                    flash('Error al actualizar la contraseña.', 'danger')

            return render_template('admin/doctor_cambiar_password_form.html', form=form, doctor=doctor)

    except Exception as e:
        print(f"Error en cambiar_password: {e}")
        flash('Ocurrió un error inesperado.', 'danger')
        return redirect(url_for('admin.admin_manage_doctores'))


@admin_bp.route('/doctor/toggle_status/<int:id_dr>', methods=['POST'])
@admin_required
def admin_toggle_doctor_status(id_dr):
    try:
        with get_db_cursor(commit=True) as (connection, cursor):
            if connection:
                doctor = get_doctor_by_id(connection, id_dr)
                if doctor:
                    nuevo_estado = not doctor['esta_activo']
                    success = set_doctor_active_status(connection, id_dr, nuevo_estado)
                    if success:
                        flash(f"Estado del doctor actualizado.", "success")
                    else:
                        flash("Error al actualizar estado.", "danger")
                else:
                    flash("Doctor no encontrado.", "warning")
    except Exception as e:
        print(f"Error en toggle_status doctor: {e}")
        flash("Error inesperado.", "danger")
            
    return redirect(url_for('admin.admin_manage_doctores'))


@admin_bp.route('/clinicas')
@admin_required
def admin_manage_clinicas():
    centros = []
    try:
        with get_db_cursor() as (connection, cursor):
            if connection:
                centros = get_all_centros(connection)
    except Exception as e:
        print(f"Error en clinicas: {e}")
        flash("Error al cargar clínicas.", "danger")
        
    return render_template('admin/clinicas_lista.html', centros=centros)

@admin_bp.route('/clinica/editar/<int:id_centro>', methods=['GET', 'POST'])
@admin_required
def admin_edit_clinica(id_centro):
    try:
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                return redirect(url_for('admin.admin_manage_clinicas'))

            centro = get_centro_by_id(connection, id_centro) 
            if not centro:
                flash('Clínica no encontrada.', 'warning')
                return redirect(url_for('admin.admin_manage_clinicas'))

            form = ClinicaForm()

            if form.validate_on_submit():
                form_nombre = form.nombre.data or ""
                form_direccion = form.direccion.data or ""
                form_cel = form.cel.data or ""
                form_tel = form.tel.data or ""

                db_nombre = str(centro.get('nombre')) if centro.get('nombre') is not None else ""
                db_direccion = str(centro.get('direccion')) if centro.get('direccion') is not None else ""
                db_cel = str(centro.get('cel')) if centro.get('cel') is not None else ""
                db_tel = str(centro.get('tel')) if centro.get('tel') is not None else ""
                
                data_changed = (
                    form_nombre != db_nombre or
                    form_direccion != db_direccion or
                    form_cel != db_cel or
                    form_tel != db_tel
                )

                if not data_changed:
                    flash("No se detectaron cambios.", "info")
                    return redirect(url_for('admin.admin_manage_clinicas'))
                
                data_to_update = {
                    'id_centro': id_centro,
                    'nombre': form.nombre.data,
                    'direccion': form.direccion.data,
                    'cel': form.cel.data,
                    'tel': form.tel.data
                }
                
                success = update_centro(connection, data_to_update)
                if success:
                    flash(f'Clínica actualizada exitosamente.', 'success')
                    return redirect(url_for('admin.admin_manage_clinicas'))
                else:
                    flash('Error al actualizar la clínica.', 'danger')

            elif request.method == 'GET':
                form = ClinicaForm(data=centro)

            return render_template('admin/clinica_form.html', 
                                   form=form, 
                                   title=f'Editar Clínica: {centro["nombre"]}', 
                                   centro=centro)

    except Exception as e:
        print(f"Error en edit_clinica: {e}")
        flash('Ocurrió un error inesperado.', 'danger')
        return redirect(url_for('admin.admin_manage_clinicas'))

@admin_bp.route('/clinica/nueva', methods=['GET', 'POST'])
@admin_required
def admin_add_clinica():
    form = ClinicaForm()
    
    if form.validate_on_submit():
        try:
            data_from_form = {
                'nombre': form.nombre.data,
                'direccion': form.direccion.data,
                'cel': form.cel.data,
                'tel': form.tel.data
            }
            
            with get_db_cursor(commit=True) as (connection, cursor):
                if connection:
                    new_id = add_centro(connection, data_from_form)
                    if new_id:
                        flash(f'Clínica creada con éxito.', 'success')
                        return redirect(url_for('admin.admin_manage_clinicas'))
                    else:
                        flash('Error al crear la clínica.', 'danger')
        except Exception as e:
            flash(f"Error inesperado: {e}", "danger")

    return render_template('admin/clinica_form.html', form=form, title="Crear Nueva Clínica", centro=None)


@admin_bp.route('/reportes', methods=['GET', 'POST'])
@admin_required
def admin_reportes_dashboard():
    default_date_data = {}
    if request.method == 'GET':
        today = date.today()
        first_day_of_month = today.replace(day=1)
        default_date_data = {'fecha_inicio': first_day_of_month, 'fecha_fin': today}

    # Inicializar Forms
    if request.method == 'POST':
        form_ingresos = FormIngresos(request.form)
        form_utilidad = FormUtilidad(request.form)
        form_nuevos_pac = FormNuevosPacientes(request.form)
        form_pac_frec = FormPacientesFrecuentes(request.form)
        form_seguimientos = FormSeguimientos(request.form)
        form_uso_planes = FormUsoPlanes(request.form)
        form_cxc = FormCuentasPorCobrar(request.form) # Nuevo
        form_caja = FormCorteCaja(request.form)       # Nuevo
    else:
        form_ingresos = FormIngresos(data=default_date_data)
        form_utilidad = FormUtilidad(data=default_date_data)
        form_nuevos_pac = FormNuevosPacientes(data=default_date_data)
        form_pac_frec = FormPacientesFrecuentes(data=default_date_data) 
        form_seguimientos = FormSeguimientos(data=default_date_data)
        form_uso_planes = FormUsoPlanes(data=default_date_data)
        form_cxc = FormCuentasPorCobrar()             # Nuevo
        form_caja = FormCorteCaja(data=default_date_data) # Nuevo

    # Variables de datos vacías por defecto
    datos_ingresos = labels_ingresos = data_values_ingresos = None
    datos_utilidad = labels_utilidad = data_values_utilidad = None
    datos_nuevos_pacientes = labels_nuevos_pac = data_values_nuevos_pac = None
    datos_pacientes_frecuentes = None
    datos_seguimientos = labels_seguimientos = data_values_seguimientos = None
    datos_uso_planes = labels_uso_planes = data_values_uso_planes = None
    datos_cxc = None # Nuevo
    datos_caja = None # Nuevo

    try:
        with get_db_cursor() as (connection, cursor):
            if not connection:
                flash('Error conectando a la base de datos.', 'danger')
            else:
                # Poblar selectores
                doctores = get_all_doctors(connection)
                doctor_choices = [(dr['id_dr'], dr['nombre']) for dr in doctores]
                doctor_choices.insert(0, (0, "Todos los Doctores"))

                for f in [form_ingresos, form_utilidad, form_nuevos_pac, form_seguimientos, form_cxc, form_caja]:
                    f.doctor_id.choices = doctor_choices

                # --- PROCESAMIENTO ---
                
                # 1. Ingresos
                if form_ingresos.submit_ingresos.data and form_ingresos.validate_on_submit():
                    datos_ingresos_lista = []
                    fi, ff = form_ingresos.fecha_inicio.data.strftime('%Y-%m-%d'), form_ingresos.fecha_fin.data.strftime('%Y-%m-%d')
                    did = form_ingresos.doctor_id.data
                    if did == 0:
                        datos_ingresos_lista = get_ingresos_por_periodo(connection, fi, ff)
                        labels_ingresos = [i['periodo'] for i in datos_ingresos_lista]
                        data_values_ingresos = [i['total_ingresos_periodo'] for i in datos_ingresos_lista]
                    else:
                        datos_ingresos_lista = get_ingresos_por_doctor_periodo(connection, fi, ff, did)
                        labels_ingresos = [i['nombre_doctor'] for i in datos_ingresos_lista]
                        data_values_ingresos = [i['total_ingresos_doctor'] for i in datos_ingresos_lista]
                    datos_ingresos = datos_ingresos_lista
                    if not datos_ingresos: flash("No hay datos de ingresos.", "info")

                # 2. Utilidad
                elif form_utilidad.submit_utilidad.data and form_utilidad.validate_on_submit():
                    fi, ff = form_utilidad.fecha_inicio.data.strftime('%Y-%m-%d'), form_utilidad.fecha_fin.data.strftime('%Y-%m-%d')
                    did = form_utilidad.doctor_id.data
                    datos_lista = []
                    if did == 0:
                        datos_lista = get_utilidad_estimada_por_periodo(connection, fi, ff)
                        labels_utilidad = [i['periodo'] for i in datos_lista]
                        data_values_utilidad = [i['total_utilidad_estimada_periodo'] for i in datos_lista]
                    else:
                        datos_lista = get_utilidad_estimada_por_doctor_periodo(connection, fi, ff, did)
                        labels_utilidad = [i['nombre_doctor'] for i in datos_lista]
                        data_values_utilidad = [i['total_utilidad_estimada_doctor'] for i in datos_lista]
                    datos_utilidad = datos_lista
                    if not datos_utilidad: flash("No hay datos de utilidad.", "info")

                # 3. Corte de Caja (NUEVO)
                elif form_caja.submit_caja.data and form_caja.validate_on_submit():
                    fi, ff = form_caja.fecha_inicio.data.strftime('%Y-%m-%d'), form_caja.fecha_fin.data.strftime('%Y-%m-%d')
                    did = form_caja.doctor_id.data
                    datos_caja = get_corte_caja_detallado(connection, fi, ff, did)
                    if not datos_caja['movimientos']: flash("No hay movimientos de caja en este periodo.", "info")

                # 4. Cuentas por Cobrar (NUEVO)
                elif form_cxc.submit_cxc.data and form_cxc.validate_on_submit():
                    did = form_cxc.doctor_id.data
                    datos_cxc = get_cuentas_por_cobrar(connection, did)
                    if not datos_cxc: flash("¡Felicidades! No hay cuentas por cobrar pendientes.", "success")

                # 5. Pacientes Nuevos
                elif form_nuevos_pac.submit_nuevos_pac.data and form_nuevos_pac.validate_on_submit():
                    fi, ff = form_nuevos_pac.fecha_inicio.data.strftime('%Y-%m-%d'), form_nuevos_pac.fecha_fin.data.strftime('%Y-%m-%d')
                    did = form_nuevos_pac.doctor_id.data
                    lista, grafica = get_pacientes_nuevos_por_periodo(connection, fi, ff, did)
                    datos_nuevos_pacientes = lista
                    if datos_nuevos_pacientes:
                        labels_nuevos_pac = [i['periodo_label'] for i in grafica]
                        data_values_nuevos_pac = [i['conteo'] for i in grafica]
                    else: flash("No hay pacientes nuevos.", "info")

                # 6. Pacientes Frecuentes
                elif form_pac_frec.submit_pac_frec.data and form_pac_frec.validate_on_submit():
                    datos_pacientes_frecuentes = get_pacientes_mas_frecuentes(connection, 
                        form_pac_frec.fecha_inicio.data.strftime('%Y-%m-%d'),
                        form_pac_frec.fecha_fin.data.strftime('%Y-%m-%d'),
                        form_pac_frec.top_n.data)
                    if not datos_pacientes_frecuentes: flash("No hay datos.", "info")

                # 7. Seguimientos
                elif form_seguimientos.submit_seguimientos.data and form_seguimientos.validate_on_submit():
                    fi, ff = form_seguimientos.fecha_inicio.data.strftime('%Y-%m-%d'), form_seguimientos.fecha_fin.data.strftime('%Y-%m-%d')
                    did = form_seguimientos.doctor_id.data
                    lista = get_seguimientos_por_doctor_periodo(connection, fi, ff, did)
                    datos_seguimientos = lista
                    if lista:
                        labels_seguimientos = [i['nombre_doctor'] for i in lista]
                        data_values_seguimientos = [i['numero_consultas'] for i in lista]
                    else: flash("No hay seguimientos.", "info")

                # 8. Uso de Planes
                elif form_uso_planes.submit_uso_planes.data and form_uso_planes.validate_on_submit():
                    fi, ff = form_uso_planes.fecha_inicio.data.strftime('%Y-%m-%d'), form_uso_planes.fecha_fin.data.strftime('%Y-%m-%d')
                    dic = get_uso_planes_de_cuidado(connection, fi, ff)
                    if dic and dic['total_creados'] > 0:
                        datos_uso_planes = dic
                        labels_uso_planes = ['Activos', 'Completados']
                        data_values_uso_planes = [dic['activos'], dic['completados']]
                    else: flash("No hay planes.", "info")

    except Exception as e:
        print(f"Error reportes: {e}")
        flash(f"Error al procesar el reporte.", "danger")

    return render_template(
        'admin/reportes_dashboard.html',
        form_ingresos=form_ingresos, form_utilidad=form_utilidad,
        form_nuevos_pac=form_nuevos_pac, form_pac_frec=form_pac_frec,
        form_seguimientos=form_seguimientos, form_uso_planes=form_uso_planes,
        form_cxc=form_cxc, form_caja=form_caja, # <--- Pasamos los nuevos forms
        datos_ingresos=datos_ingresos, labels_ingresos=labels_ingresos, data_values_ingresos=data_values_ingresos,
        datos_utilidad=datos_utilidad, labels_utilidad=labels_utilidad, data_values_utilidad=data_values_utilidad,
        datos_nuevos_pacientes=datos_nuevos_pacientes, labels_nuevos_pac=labels_nuevos_pac, data_values_nuevos_pac=data_values_nuevos_pac,
        datos_pacientes_frecuentes=datos_pacientes_frecuentes,
        datos_seguimientos=datos_seguimientos, labels_seguimientos=labels_seguimientos, data_values_seguimientos=data_values_seguimientos,
        datos_uso_planes=datos_uso_planes, labels_uso_planes=labels_uso_planes, data_values_uso_planes=data_values_uso_planes,
        datos_cxc=datos_cxc, datos_caja=datos_caja 
    )

@admin_bp.route('/producto/stock/actualizar', methods=['POST'])
@login_required
@admin_required
def actualizar_stock_route():
    try:
        id_prod = request.form.get('id_prod')
        cantidad = request.form.get('cantidad_stock')
        
        if not id_prod or not cantidad:
            flash('Datos incompletos.', 'warning')
            return redirect(url_for('admin.admin_manage_productos'))

        with get_db_cursor(commit=True) as (connection, cursor):
            cant_int = int(cantidad)
            exito = actualizar_stock_producto(connection, id_prod, cant_int)
            
            if exito:
                flash(f'Stock actualizado correctamente ({cant_int:+d} unidades).', 'success')
            else:
                flash('Error al actualizar el stock.', 'danger')
                
        return redirect(url_for('admin.admin_manage_productos'))

    except Exception as e:
        current_app.logger.error(f"Error stock: {e}")
        flash('Ocurrió un error interno.', 'danger')
        return redirect(url_for('admin.admin_manage_productos'))


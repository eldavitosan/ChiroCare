import os
from flask import (
    Blueprint, render_template, request, redirect, jsonify, session, flash, url_for
)
from mysql.connector import Error
from datetime import datetime, date
from werkzeug.security import generate_password_hash
from decimal import Decimal
# Importar funciones de base de datos necesarias para ESTAS rutas
from forms import (RegisterForm, EditDoctorForm, ChangePasswordForm, ClinicaForm, ProductoServicioForm,
                   FormIngresos, FormUtilidad, FormNuevosPacientes, FormPacientesFrecuentes, FormSeguimientos, 
                   FormUsoPlanes)
from database import (
    add_user, connect_to_db, get_all_doctors, get_doctor_by_id,
    update_doctor_details, update_doctor_password, set_doctor_active_status,
    count_total_pacientes, count_total_doctores, count_seguimientos_hoy,
    get_all_centros, get_centro_by_id, add_centro, update_centro,
    get_ingresos_por_periodo, get_ingresos_por_doctor_periodo,
    get_utilidad_estimada_por_periodo, get_utilidad_estimada_por_doctor_periodo,
    get_pacientes_nuevos_por_periodo, get_pacientes_mas_frecuentes,
    get_seguimientos_por_doctor_periodo, get_uso_planes_de_cuidado,
    get_all_productos_servicios, get_producto_servicio_by_id,
    add_producto_servicio, update_producto_servicio, 
    set_producto_servicio_active_status
)
from utils.date_manager import to_frontend_str

# Importar los decoradores
from decorators import login_required, admin_required

# 1. Crear el Blueprint con prefijo /admin
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
            connection = None
            try:
                connection = connect_to_db()
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
            except Error as db_err:
                print(f"Error de BD en register: {db_err}") # CAMBIO
                flash(f"Error de base de datos: {db_err}", "danger")
            except Exception as e:
                print(f"Error inesperado en register: {e}") # CAMBIO
                flash("Ocurrió un error inesperado durante el registro.", "danger")
            finally:
                if connection and connection.is_connected():
                    connection.close()
        
        return render_template('register.html', 
                               nombre_prev=request.form.get('nombre',''), 
                               usuario_prev=request.form.get('usuario',''),
                               es_admin_prev = (request.form.get('es_admin_nuevo_dr') == 'on')
                               )
    return render_template('register.html', nombre_prev='', usuario_prev='', es_admin_prev=False)

@admin_bp.route('/doctor/crear', methods=['GET', 'POST']) 
@admin_required
def admin_create_doctor():
    # 1. Instanciar el formulario
    form = RegisterForm()
    
    # 2. Obtener la lista de centros para poblar el <select>
    connection_centros = None
    centros = []
    try:
        connection_centros = connect_to_db()
        if connection_centros:
            centros = get_all_centros(connection_centros)
            # 3. Poblar las opciones del campo 'centro' en el formulario
            #    Se excluye "Admin (Centro 0)" de la lista de asignación
            form.centro.choices = [(c['id_centro'], c['nombre']) for c in centros if c['id_centro'] > 0]
            # Opcional: Poner Centro 1 como default si no se selecciona nada
            form.centro.default = 1
            form.process(request.form) # Para que el default se procese en la carga inicial
        else:
            flash("Error de conexión a la base de datos.", "danger")
    except Error as e:
        flash(f"Error al cargar centros: {e}", "danger")
    finally:
        if connection_centros and connection_centros.is_connected():
            connection_centros.close()

    # 4. Validar al enviar (esto incluye la validación CSRF)
    if form.validate_on_submit():
        connection_add = None
        try:
            nombre = form.nombre.data
            usuario = form.usuario.data
            password = form.contraseña.data
            es_admin = form.es_admin_nuevo_dr.data
            centro_id_form = form.centro.data # Viene de WTForms, ya es int o None

            # 5. Lógica para asignar el centro
            # (Esta es la lógica que ya tenías, pero ahora con datos del form)
            centro_a_usar = 0 if es_admin else (centro_id_form if centro_id_form and centro_id_form > 0 else 1)

            connection_add = connect_to_db()
            if not connection_add:
                flash('Error de conexión a la base de datos.', 'danger')
            else:
                # 6. Llamar a add_user (que ya hashea la contraseña)
                nuevo_id_dr = add_user(connection_add, nombre, usuario, password, centro_a_usar)
                if nuevo_id_dr:
                    flash(f'Doctor {nombre} creado exitosamente con ID: {nuevo_id_dr}.', 'success')
                    return redirect(url_for('admin.admin_manage_doctores'))
                else:
                    # Esto ocurre si add_user devuelve None (ej. usuario duplicado)
                    flash('El nombre de usuario ya existe o hubo un error.', 'danger')
        
        except Error as db_err:
            flash(f"Error de base de datos al crear doctor: {db_err}", "danger")
        except Exception as e:
            flash(f"Error inesperado al crear doctor: {e}", "danger")
        finally:
            if connection_add and connection_add.is_connected():
                connection_add.close()
        
        # Si algo falla en el POST, se recarga la página con el form (y los errores)
        return render_template('admin/doctor_crear_form.html', form=form, es_admin_prev=form.es_admin_nuevo_dr.data)

    # 7. Si es GET, o si la validación (POST) falló
    # Pasa 'form' al template. Los errores se mostrarán solos.
    es_admin_prev = request.form.get('es_admin_nuevo_dr') == 'on' if request.method == 'POST' else False
    return render_template('admin/doctor_crear_form.html', form=form, es_admin_prev=es_admin_prev)


@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    connection = None 
    try:
        connection = connect_to_db()
        if not connection:
            flash("Error de conexión a la base de datos.", "danger")
            return render_template('main.html') 

        num_pacientes = 0
        num_doctores = 0
        num_seguimientos_hoy = 0
        admin_name = session.get('nombre_dr', 'Admin')
        
        num_pacientes = count_total_pacientes(connection)
        num_doctores = count_total_doctores(connection)
        today_for_db = to_frontend_str(datetime.now())
        num_seguimientos_hoy = count_seguimientos_hoy(connection, today_for_db)
        
        return render_template('admin/dashboard_admin.html',
                               admin_name=admin_name,
                               num_pacientes=num_pacientes,
                               num_doctores=num_doctores,
                               num_seguimientos_hoy=num_seguimientos_hoy
                               )
    except Exception as e:
        print(f"Error en admin_dashboard: {e}") # CAMBIO (eliminado exc_info)
        flash("Ocurrió un error al cargar el dashboard de administrador.", "danger")
        return render_template('admin/dashboard_admin.html',
                               admin_name=session.get('nombre_dr', 'Admin'),
                               num_pacientes=0,
                               num_doctores=0,
                               num_seguimientos_hoy=0
                               )
    finally:
        if connection and connection.is_connected():
            connection.close()

# --- RUTAS DE GESTIÓN DE PRODUCTOS ---

@admin_bp.route('/productos')
@admin_required
def admin_manage_productos():
    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            flash("Error de conexión.", "danger")
            return redirect(url_for('admin.admin_dashboard'))
        
        productos = get_all_productos_servicios(connection, include_inactive=True)
        return render_template('admin/productos_lista.html', productos=productos)
    except Exception as e:
        print(f"Error en admin_manage_productos: {e}") # CAMBIO
        flash("Error al cargar la lista de productos.", "danger")
        return redirect(url_for('admin.admin_dashboard'))
    finally:
        if connection and connection.is_connected():
            connection.close()

@admin_bp.route('/producto/nuevo', methods=['GET', 'POST'])
@admin_required
def admin_add_producto():
    # 1. Instanciar el formulario
    form = ProductoServicioForm()
    
    # 2. Validar al enviar (esto incluye la validación CSRF)
    if form.validate_on_submit():
        connection = None
        try:
            # 3. Obtener los datos limpios del formulario
            data_to_create = {
                'nombre': form.nombre.data,
                'costo': form.costo.data,
                'venta': form.venta.data,
                'adicional': form.adicional.data
            }
            
            connection = connect_to_db()
            if not connection:
                flash('Error de conexión a la base de datos.', 'danger')
            else:
                # 4. Llamar a la BBDD (tu función ya acepta estos tipos)
                success = add_producto_servicio(connection, data_to_create)
                if success:
                    # 5. Hacer Commit (como ya lo hacías)
                    connection.commit()
                    flash(f'Producto/Servicio "{data_to_create["nombre"]}" creado exitosamente.', 'success')
                    return redirect(url_for('admin.admin_manage_productos'))
                else:
                    connection.rollback()
                    flash('Error al crear el producto (posible nombre duplicado).', 'danger')
        
        except Error as db_err:
            if connection: connection.rollback()
            flash(f"Error de base de datos: {db_err}", "danger")
        except Exception as e:
            if connection: connection.rollback()
            flash(f"Error inesperado: {e}", "danger")
        finally:
            if connection and connection.is_connected():
                connection.close()

    # 6. Si es GET o la validación falla, renderizar el template
    #    pasando el 'form' y un título.
    return render_template('admin/producto_form.html', form=form, title="Crear Nuevo Producto/Servicio", producto=None)


@admin_bp.route('/producto/editar/<int:id_prod>', methods=['GET', 'POST'])
@admin_required
def admin_edit_producto(id_prod):
    connection = None
    producto = None
    
    try:
        connection = connect_to_db()
        if not connection:
            flash('Error conectando a la base de datos.', 'danger')
            return redirect(url_for('admin.admin_manage_productos'))

        # 1. Obtener los datos del producto (como ya lo hacías)
        producto = get_producto_servicio_by_id(connection, id_prod)
        if not producto:
            flash('Producto o servicio no encontrado.', 'warning')
            return redirect(url_for('admin.admin_manage_productos'))

        # 2. Instanciar el formulario
        form = ProductoServicioForm()

        # 3. Lógica de POST
        if form.validate_on_submit():
            
            # --- Lógica para "No hay cambios" ---
            # 4. Normalizar datos del form (Decimal y Boolean)
            form_nombre = form.nombre.data or ""
            form_costo = form.costo.data if form.costo.data is not None else Decimal('0.00')
            form_venta = form.venta.data if form.venta.data is not None else Decimal('0.00')
            form_adicional = form.adicional.data
            
            # 5. Normalizar datos de la BBDD (convertir a Decimal y Boolean)
            db_nombre = str(producto.get('nombre')) if producto.get('nombre') is not None else ""
            db_costo = Decimal(str(producto.get('costo'))) if producto.get('costo') is not None else Decimal('0.00')
            db_venta = Decimal(str(producto.get('venta'))) if producto.get('venta') is not None else Decimal('0.00')
            db_adicional = int(producto.get('adicional')) if producto.get('adicional') is not None else 0
            
            # 6. Comparar
            data_changed = (
                form_nombre != db_nombre or
                form_costo != db_costo or
                form_venta != db_venta or
                form_adicional != db_adicional
            )
            
            if not data_changed:
                flash("No se detectaron cambios en los datos.", "info")
                return redirect(url_for('admin.admin_manage_productos'))
            # --- Fin lógica "No hay cambios" ---

            # 7. Si hay cambios, crear el DICCIONARIO 'data'
            data_to_update = {
                'id_prod': id_prod, # Tu BBDD la necesita para el WHERE
                'nombre': form.nombre.data,
                'costo': form.costo.data,
                'venta': form.venta.data,
                'adicional': form.adicional.data
            }

            # 8. Llamar a la BBDD con 2 argumentos: (connection, data)
            success = update_producto_servicio(connection, data_to_update)
            if success:
                connection.commit()
                flash(f'Producto/Servicio "{data_to_update["nombre"]}" actualizado exitosamente.', 'success')
                return redirect(url_for('admin.admin_manage_productos'))
            else:
                connection.rollback()
                flash('Error al actualizar el producto (posible nombre duplicado).', 'danger')

        elif request.method == 'GET':
            # 8. Lógica de GET: Pre-poblar el formulario
            # Los nombres de los campos (nombre, costo, venta, adicional)
            # coinciden entre tu BBDD y tu Formulario, así que esto funciona directo.
            form = ProductoServicioForm(data=producto)

        # 9. Renderizar la plantilla
        return render_template('admin/producto_form.html', 
                               form=form, 
                               title=f'Editar Producto/Servicio: {producto["nombre"]}', 
                               producto=producto)

    except Exception as e:
        if connection: connection.rollback()
        print(f"Error en admin_edit_producto (ID {id_prod}): {e}")
        flash('Ocurrió un error inesperado al editar.', 'danger')
        return redirect(url_for('admin.admin_manage_productos'))
    finally:
        if connection and connection.is_connected():
            connection.close()


@admin_bp.route('/producto/toggle_status/<int:id_prod>', methods=['POST'])
@admin_required
def admin_toggle_producto_status(id_prod):
    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            flash("Error de conexión a la base de datos.", "danger")
            return redirect(url_for('admin.admin_manage_productos'))

        producto = get_producto_servicio_by_id(connection, id_prod)
        if not producto:
            flash("Producto/Servicio no encontrado.", "warning")
            return redirect(url_for('admin.admin_manage_productos'))

        nuevo_estado = not producto['esta_activo']
        success = set_producto_servicio_active_status(connection, id_prod, nuevo_estado)
        
        if success:
            accion = "habilitado" if nuevo_estado else "deshabilitado"
            flash(f"Producto/Servicio '{producto['nombre']}' {accion}.", "success")
        else:
            flash(f"Error al cambiar el estado del producto/servicio '{producto['nombre']}'.", "danger")
        
        return redirect(url_for('admin.admin_manage_productos'))
    except Exception as e:
        print(f"Error en admin_toggle_producto_status (ID {id_prod}): {e}") # CAMBIO
        flash("Error inesperado al cambiar estado del producto.", "danger")
        return redirect(url_for('admin.admin_manage_productos'))
    finally:
        if connection and connection.is_connected():
            connection.close()
    

@admin_bp.route('/doctores')
@admin_required
def admin_manage_doctores():
    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            flash("Error de conexión a la base de datos.", "danger")
            return redirect(url_for('admin.admin_dashboard'))
        
        doctores = get_all_doctors(connection, include_inactive=True)
        return render_template('admin/doctores_lista.html', doctores=doctores)
    except Exception as e:
        print(f"Error en admin_manage_doctores: {e}") # CAMBIO
        flash("Error al cargar la lista de doctores.", "danger")
        return redirect(url_for('admin.admin_dashboard'))
    finally:
        if connection and connection.is_connected():
            connection.close()

@admin_bp.route('/doctor/editar/<int:id_dr>', methods=['GET', 'POST'])
@admin_required
def admin_edit_doctor(id_dr):
    connection = None
    doctor = None
    centros = []
    
    try:
        connection = connect_to_db()
        if not connection:
            flash('Error conectando a la base de datos.', 'danger')
            return redirect(url_for('admin.admin_manage_doctores'))

        # 1. Obtener los datos del doctor (como ya lo hacías)
        doctor = get_doctor_by_id(connection, id_dr)
        if not doctor:
            flash('Doctor no encontrado.', 'warning')
            return redirect(url_for('admin.admin_manage_doctores'))

        # 2. Obtener lista de centros (para el <select>)
        centros = get_all_centros(connection)
        
        # 3. Instanciar el formulario
        form = EditDoctorForm()
        
        # 4. Poblar las opciones del campo 'centro'
        #    (Esto es necesario tanto para GET como para la validación de POST)
        form.centro.choices = [(c['id_centro'], c['nombre']) for c in centros if c['id_centro'] > 0]

        # 5. Lógica de POST (reemplaza la lógica de request.form)
        if form.validate_on_submit():
            # El formulario es válido y tiene el token CSRF
            nombre = form.nombre.data
            usuario = form.usuario.data
            es_admin = form.es_admin_nuevo_dr.data
            centro_id_form = form.centro.data

            # Lógica para asignar el centro
            centro_a_usar = 0 if es_admin else (centro_id_form if centro_id_form and centro_id_form > 0 else 1)
            
            doctor_data_to_update = {
                'id_dr': id_dr,
                'nombre': nombre,
                'usuario': usuario,
                'centro': centro_a_usar
            }
            
            # Llamar a la BBDD (como ya lo hacías)
            success = update_doctor_details(connection, doctor_data_to_update)
            
            if success:
                flash('Datos del doctor actualizados exitosamente.', 'success')
                return redirect(url_for('admin.admin_manage_doctores'))
            else:
                flash('Error al actualizar los datos (posible usuario duplicado).', 'danger')
                # La función continuará al render_template de abajo

        elif request.method == 'GET':
            # 6. Lógica de GET: Pre-poblar el formulario
            # Preparamos un diccionario con los datos del doctor
            doctor_data_for_form = doctor.copy()
            
            # El formulario espera un booleano para el checkbox
            doctor_data_for_form['es_admin_nuevo_dr'] = (doctor.get('centro') == 0)
            
            # Instanciamos el formulario CON los datos
            form = EditDoctorForm(data=doctor_data_for_form)
            
            # (Tenemos que re-poblar las 'choices' en esta nueva instancia del form)
            form.centro.choices = [(c['id_centro'], c['nombre']) for c in centros if c['id_centro'] > 0]
            
            # Asignamos manualmente el valor del 'centro' si no es Admin
            if not doctor_data_for_form['es_admin_nuevo_dr']:
                form.centro.data = doctor_data_for_form.get('centro')

        # 7. Renderizar la plantilla
        # Si es GET, muestra el form poblado.
        # Si es POST y falló, muestra el form con los errores.
        return render_template('admin/doctor_form.html', form=form, doctor=doctor)

    except Exception as e:
        print(f"Error en admin_edit_doctor (ID {id_dr}): {e}")
        flash('Ocurrió un error inesperado al editar el doctor.', 'danger')
        return redirect(url_for('admin.admin_manage_doctores'))
    finally:
        if connection and connection.is_connected():
            connection.close()


@admin_bp.route('/doctor/cambiar_password/<int:id_dr>', methods=['GET', 'POST'])
@admin_required
def admin_change_doctor_password(id_dr):
    connection = None
    doctor = None
    
    # 1. Instanciar el formulario
    form = ChangePasswordForm()

    try:
        connection = connect_to_db()
        if not connection:
            flash('Error conectando a la base de datos.', 'danger')
            return redirect(url_for('admin.admin_manage_doctores'))

        # 2. Obtener los datos del doctor (para mostrar el nombre)
        doctor = get_doctor_by_id(connection, id_dr)
        if not doctor:
            flash('Doctor no encontrado.', 'warning')
            return redirect(url_for('admin.admin_manage_doctores'))

        # 3. Lógica de POST (reemplaza 'request.method == POST')
        #    Esto validará el CSRF, que los campos no estén vacíos,
        #    y que las contraseñas coincidan (gracias a 'EqualTo')
        if form.validate_on_submit():
            
            # 4. Obtener la contraseña validada del formulario
            nueva_password = form.nueva_contraseña.data
            
            # 5. Llamar a la BBDD (como ya lo hacías)
            #    (Asumiendo que update_doctor_password se encarga del hashing)
            success = update_doctor_password(connection, id_dr, nueva_password)
            
            if success:
                flash(f'Contraseña del Dr. {doctor["nombre"]} actualizada exitosamente.', 'success')
                return redirect(url_for('admin.admin_manage_doctores'))
            else:
                flash('Error al actualizar la contraseña.', 'danger')
                # La función continuará al render_template de abajo

        # 6. Renderizar la plantilla
        # Si es GET, muestra el form vacío.
        # Si es POST y falló (ej. contraseñas no coinciden), 
        # muestra el form con los errores de validación.
        return render_template('admin/doctor_cambiar_password_form.html', form=form, doctor=doctor)

    except Exception as e:
        print(f"Error en admin_change_doctor_password (ID {id_dr}): {e}")
        flash('Ocurrió un error inesperado al cambiar la contraseña.', 'danger')
        return redirect(url_for('admin.admin_manage_doctores'))
    finally:
        if connection and connection.is_connected():
            connection.close()


@admin_bp.route('/doctor/toggle_status/<int:id_dr>', methods=['POST'])
@admin_required
def admin_toggle_doctor_status(id_dr):
    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            flash("Error de conexión.", "danger")
            return redirect(url_for('admin.admin_manage_doctores'))

        doctor = get_doctor_by_id(connection, id_dr)
        if not doctor:
            flash("Doctor no encontrado.", "warning")
            return redirect(url_for('admin.admin_manage_doctores'))

        nuevo_estado = not doctor['esta_activo']
        success = set_doctor_active_status(connection, id_dr, nuevo_estado)
        
        if success:
            accion = "habilitado" if nuevo_estado else "deshabilitado"
            flash(f"Doctor '{doctor['nombre']}' {accion}.", "success")
        else:
            flash(f"Error al cambiar el estado del doctor '{doctor['nombre']}'.", "danger")
    except Exception as e:
        print(f"Error en admin_toggle_doctor_status (ID {id_dr}): {e}") # CAMBIO
        flash("Error inesperado al cambiar estado del doctor.", "danger")
    finally:
        if connection and connection.is_connected():
            connection.close()
            
    return redirect(url_for('admin.admin_manage_doctores'))


@admin_bp.route('/clinicas')
@admin_required
def admin_manage_clinicas():
    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            flash("Error de conexión a la base de datos.", "danger")
            return redirect(url_for('admin.admin_dashboard'))
        
        centros = get_all_centros(connection)
        return render_template('admin/clinicas_lista.html', centros=centros)
    except Exception as e:
        print(f"Error en admin_manage_clinicas: {e}") # CAMBIO
        flash("Error al cargar la lista de clínicas.", "danger")
        return redirect(url_for('admin.admin_dashboard'))
    finally:
        if connection and connection.is_connected():
            connection.close()

@admin_bp.route('/clinica/editar/<int:id_centro>', methods=['GET', 'POST'])
@admin_required
def admin_edit_clinica(id_centro):
    connection = None
    centro = None
    
    try:
        connection = connect_to_db()
        if not connection:
            flash('Error conectando a la base de datos.', 'danger')
            return redirect(url_for('admin.admin_manage_clinicas'))

        # (Usamos 'get_centro_by_id' que sí debe existir en tu database.py)
        centro = get_centro_by_id(connection, id_centro) 
        if not centro:
            flash('Clínica no encontrada.', 'warning')
            return redirect(url_for('admin.admin_manage_clinicas'))

        form = ClinicaForm()

        if form.validate_on_submit():
            # 1. Comprobar si los datos realmente cambiaron
            #    (Usamos .get() para evitar errores si un campo es None en la BBDD)
            form_nombre = form.nombre.data or ""
            form_direccion = form.direccion.data or ""
            form_cel = form.cel.data or ""
            form_tel = form.tel.data or ""

            # 2. Normalizar datos de la BBDD (convertir None a "", y TODO a string)
            #    str(centro.get('tel')) convierte el entero 12345 en el string "12345"
            db_nombre = str(centro.get('nombre')) if centro.get('nombre') is not None else ""
            db_direccion = str(centro.get('direccion')) if centro.get('direccion') is not None else ""
            db_cel = str(centro.get('cel')) if centro.get('cel') is not None else ""
            db_tel = str(centro.get('tel')) if centro.get('tel') is not None else ""
            
            # 3. Comparar (ahora es "12345" != "12345", lo cual es False)
            data_changed = (
                form_nombre != db_nombre or
                form_direccion != db_direccion or
                form_cel != db_cel or
                form_tel != db_tel
            )

            if not data_changed:
                # 2. Si no hay cambios, solo informa y redirige.
                flash("No se detectaron cambios en los datos.", "info") # Usamos 'info' (azul)
                return redirect(url_for('admin.admin_manage_clinicas'))
            
            # 1. Crear el diccionario 'data' para actualizar
            data_to_update = {
                'id_centro': id_centro, # Importante para el WHERE
                'nombre': form.nombre.data,
                'direccion': form.direccion.data,
                'cel': form.cel.data,
                'tel': form.tel.data
            }
            
            # 2. Llamar a tu función de BBDD
            success = update_centro(connection, data_to_update)
            
            if success:
                # 3. ¡Hacer COMMIT!
                connection.commit()
                flash(f'Clínica "{data_to_update["nombre"]}" actualizada exitosamente.', 'success')
                return redirect(url_for('admin.admin_manage_clinicas'))
            else:
                connection.rollback()
                flash('Error al actualizar la clínica (posible nombre duplicado).', 'danger')

        elif request.method == 'GET':
            # 4. Pre-poblar el formulario con los datos existentes
            #    (Tus claves en BBDD 'tel' y 'cel' coinciden con el form)
            form = ClinicaForm(data=centro)

        return render_template('admin/clinica_form.html', 
                               form=form, 
                               title=f'Editar Clínica: {centro["nombre"]}', 
                               centro=centro)

    except Exception as e:
        if connection: connection.rollback()
        print(f"Error en admin_edit_centro (ID {id_centro}): {e}")
        flash('Ocurrió un error inesperado al editar la clínica.', 'danger')
        return redirect(url_for('admin.admin_manage_clinicas'))
    finally:
        if connection and connection.is_connected():
            connection.close()

@admin_bp.route('/clinica/nueva', methods=['GET', 'POST'])
@admin_required
def admin_add_clinica():
    form = ClinicaForm()
    
    if form.validate_on_submit():
        connection = None
        try:
            # 1. Crear el diccionario 'data' desde el formulario
            data_from_form = {
                'nombre': form.nombre.data,
                'direccion': form.direccion.data,
                'cel': form.cel.data,
                'tel': form.tel.data
            }
            
            connection = connect_to_db()
            if not connection:
                flash('Error de conexión a la base de datos.', 'danger')
            else:
                # 2. Llamar a tu función de BBDD con el diccionario
                new_id = add_centro(connection, data_from_form)
                
                if new_id:
                    # 3. ¡Hacer COMMIT! (Porque tu función no lo hace)
                    connection.commit()
                    flash(f'Clínica "{data_from_form["nombre"]}" creada con ID: {new_id}.', 'success')
                    return redirect(url_for('admin.admin_manage_clinicas'))
                else:
                    connection.rollback() # Revertir si add_centro falló
                    flash('Error al crear la clínica (posible nombre duplicado).', 'danger')
        
        except Error as db_err:
            if connection: connection.rollback()
            flash(f"Error de base de datos: {db_err}", "danger")
        except Exception as e:
            if connection: connection.rollback()
            flash(f"Error inesperado: {e}", "danger")
        finally:
            if connection and connection.is_connected():
                connection.close()

    return render_template('admin/clinica_form.html', form=form, title="Crear Nueva Clínica", centro=None)


@admin_bp.route('/reportes', methods=['GET', 'POST'])
@admin_required
def admin_reportes_dashboard():
    # 0. Calcular fechas por defecto (SOLO para peticiones GET)
    default_date_data = {}
    if request.method == 'GET':
        today = date.today()
        first_day_of_month = today.replace(day=1)
        
        default_date_data = {
            'fecha_inicio': first_day_of_month,
            'fecha_fin': today
        }
        print(f"DEBUG: Aplicando fechas por defecto: {default_date_data}") # Opcional

    # 1. Instanciar todos los formularios
    if request.method == 'POST':
        # En POST, WTForms toma 'request.form' directamente.
        form_ingresos = FormIngresos(request.form)
        form_utilidad = FormUtilidad(request.form)
        form_nuevos_pac = FormNuevosPacientes(request.form)
        form_pac_frec = FormPacientesFrecuentes(request.form)
        form_seguimientos = FormSeguimientos(request.form)
        form_uso_planes = FormUsoPlanes(request.form)
    else:
        # En GET, poblamos con los datos por defecto usando 'data='
        form_ingresos = FormIngresos(data=default_date_data)
        form_utilidad = FormUtilidad(data=default_date_data)
        form_nuevos_pac = FormNuevosPacientes(data=default_date_data)
        form_pac_frec = FormPacientesFrecuentes(data=default_date_data) 
        form_seguimientos = FormSeguimientos(data=default_date_data)
        form_uso_planes = FormUsoPlanes(data=default_date_data)

    # 2. Variables para pasar al template
    doctores = []
    # Datos para Reporte Ingresos
    datos_ingresos = None
    labels_ingresos = None
    data_values_ingresos = None
    # Datos para Reporte Utilidad
    datos_utilidad = None
    labels_utilidad = None
    data_values_utilidad = None
    # Datos para Reporte Nuevos Pacientes
    datos_nuevos_pacientes = None # Lista para la tabla
    labels_nuevos_pac = None
    data_values_nuevos_pac = None
    # Datos para Reporte Pacientes Frecuentes
    datos_pacientes_frecuentes = None
    # Datos para Reporte Seguimientos
    datos_seguimientos = None
    labels_seguimientos = None
    data_values_seguimientos = None
    # Datos para Reporte Uso de Planes
    datos_uso_planes = None
    labels_uso_planes = None
    data_values_uso_planes = None

    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            flash('Error conectando a la base de datos.', 'danger')
            # Renderizar con formularios vacíos si falla la conexión
            return render_template('admin/reportes_dashboard.html',
                form_ingresos=form_ingresos, form_utilidad=form_utilidad,
                form_nuevos_pac=form_nuevos_pac, form_pac_frec=form_pac_frec,
                form_seguimientos=form_seguimientos, form_uso_planes=form_uso_planes
            )

        # 3. Poblar los selectores de Doctores (para GET y POST)
        doctores = get_all_doctors(connection) # Asumiendo que get_all_doctors es correcto
        doctor_choices = [(dr['id_dr'], dr['nombre']) for dr in doctores]
        doctor_choices.insert(0, (0, "Todos los Doctores"))

        form_ingresos.doctor_id.choices = doctor_choices
        form_utilidad.doctor_id.choices = doctor_choices
        form_nuevos_pac.doctor_id.choices = doctor_choices
        form_seguimientos.doctor_id.choices = doctor_choices

        # --- 4. LÓGICA DE PROCESAMIENTO DE FORMULARIOS (POST) ---
        
        # --- Reporte 1 y 2: Ingresos ---
        if form_ingresos.submit_ingresos.data and form_ingresos.validate_on_submit():
            fecha_inicio_str = form_ingresos.fecha_inicio.data.strftime('%Y-%m-%d')
            fecha_fin_str = form_ingresos.fecha_fin.data.strftime('%Y-%m-%d')
            doctor_id = form_ingresos.doctor_id.data

            if doctor_id == 0: # Todos los doctores, agrupados por periodo
                datos_ingresos_lista = get_ingresos_por_periodo(connection, fecha_inicio_str, fecha_fin_str)
                if datos_ingresos_lista:
                    datos_ingresos = datos_ingresos_lista # Para la tabla
                    labels_ingresos = [item['periodo'] for item in datos_ingresos_lista]
                    data_values_ingresos = [item['total_ingresos_periodo'] for item in datos_ingresos_lista]
                else:
                    flash("No se encontraron ingresos en el periodo seleccionado.", "info")
            
            else: # Ingresos agrupados por doctor
                # NOTA: La lógica original parecía confundir dos reportes.
                # Esta llamada es para "Ingresos POR DOCTOR"
                datos_ingresos_lista = get_ingresos_por_doctor_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id)
                if datos_ingresos_lista:
                    datos_ingresos = datos_ingresos_lista # Para la tabla
                    labels_ingresos = [item['nombre_doctor'] for item in datos_ingresos_lista]
                    data_values_ingresos = [item['total_ingresos_doctor'] for item in datos_ingresos_lista]
                else:
                    flash("No se encontraron ingresos para el doctor/periodo seleccionado.", "info")

        # --- Reporte 3 y 4: Utilidad ---
        elif form_utilidad.submit_utilidad.data and form_utilidad.validate_on_submit():
            fecha_inicio_str = form_utilidad.fecha_inicio.data.strftime('%Y-%m-%d')
            fecha_fin_str = form_utilidad.fecha_fin.data.strftime('%Y-%m-%d')
            doctor_id = form_utilidad.doctor_id.data
            
            if doctor_id == 0: # Todos los doctores, agrupado por periodo
                datos_utilidad_lista = get_utilidad_estimada_por_periodo(connection, fecha_inicio_str, fecha_fin_str)
                if datos_utilidad_lista:
                    datos_utilidad = datos_utilidad_lista # Para la tabla
                    labels_utilidad = [item['periodo'] for item in datos_utilidad_lista]
                    data_values_utilidad = [item['total_utilidad_estimada_periodo'] for item in datos_utilidad_lista]
                else:
                    flash("No se encontraron datos de utilidad en el periodo seleccionado.", "info")
            else: # Utilidad agrupada por doctor
                datos_utilidad_lista = get_utilidad_estimada_por_doctor_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id)
                if datos_utilidad_lista:
                    datos_utilidad = datos_utilidad_lista # Para la tabla
                    labels_utilidad = [item['nombre_doctor'] for item in datos_utilidad_lista]
                    data_values_utilidad = [item['total_utilidad_estimada_doctor'] for item in datos_utilidad_lista]
                else:
                    flash("No se encontraron datos de utilidad para el doctor/periodo seleccionado.", "info")


        # --- Reporte 5: Nuevos Pacientes ---
        elif form_nuevos_pac.submit_nuevos_pac.data and form_nuevos_pac.validate_on_submit():
            fecha_inicio_str = form_nuevos_pac.fecha_inicio.data.strftime('%Y-%m-%d')
            fecha_fin_str = form_nuevos_pac.fecha_fin.data.strftime('%Y-%m-%d')
            doctor_id = form_nuevos_pac.doctor_id.data # 0 = Todos
            
            # --- CORRECCIÓN: Capturar AMBOS valores de retorno ---
            datos_nuevos_pacientes_lista, datos_nuevos_pacientes_grafica = get_pacientes_nuevos_por_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id)
            
            if not datos_nuevos_pacientes_lista:
                flash("No se encontraron pacientes nuevos en el periodo seleccionado.", "info")
            else:
                # Pasar la lista para la tabla
                datos_nuevos_pacientes = datos_nuevos_pacientes_lista
                # Procesar datos para la gráfica
                labels_nuevos_pac = [item['periodo_label'] for item in datos_nuevos_pacientes_grafica]
                data_values_nuevos_pac = [item['conteo'] for item in datos_nuevos_pacientes_grafica]


        # --- Reporte 6: Pacientes Frecuentes ---
        elif form_pac_frec.submit_pac_frec.data and form_pac_frec.validate_on_submit():
            top_n = form_pac_frec.top_n.data
            
            # --- CAMBIO ---
            # Ahora leemos las fechas desde su PROPIO formulario
            fecha_inicio_str = form_pac_frec.fecha_inicio.data.strftime('%Y-%m-%d')
            fecha_fin_str = form_pac_frec.fecha_fin.data.strftime('%Y-%m-%d')

            datos_pacientes_frecuentes = get_pacientes_mas_frecuentes(connection, fecha_inicio_str, fecha_fin_str, top_n)
            if not datos_pacientes_frecuentes:
                flash("No se encontraron datos de pacientes frecuentes.", "info")

        # --- Reporte 7: Seguimientos (Consultas) por Doctor ---
        elif form_seguimientos.submit_seguimientos.data and form_seguimientos.validate_on_submit():
            fecha_inicio_str = form_seguimientos.fecha_inicio.data.strftime('%Y-%m-%d')
            fecha_fin_str = form_seguimientos.fecha_fin.data.strftime('%Y-%m-%d')
            doctor_id = form_seguimientos.doctor_id.data # 0 = Todos
            
            datos_seguimientos_lista = get_seguimientos_por_doctor_periodo(connection, fecha_inicio_str, fecha_fin_str, doctor_id)
            
            if datos_seguimientos_lista:
                datos_seguimientos = datos_seguimientos_lista
                labels_seguimientos = [item['nombre_doctor'] for item in datos_seguimientos_lista]
                data_values_seguimientos = [item['numero_consultas'] for item in datos_seguimientos_lista]
            else:
                flash("No se encontraron seguimientos en el periodo seleccionado.", "info")

        # --- Reporte 8: Uso de Planes ---
        elif form_uso_planes.submit_uso_planes.data and form_uso_planes.validate_on_submit():
            fecha_inicio_str = form_uso_planes.fecha_inicio.data.strftime('%Y-%m-%d')
            fecha_fin_str = form_uso_planes.fecha_fin.data.strftime('%Y-%m-%d')
            
            datos_uso_planes_dict = get_uso_planes_de_cuidado(connection, fecha_inicio_str, fecha_fin_str)
            
            if datos_uso_planes_dict and datos_uso_planes_dict['total_creados'] > 0:
                datos_uso_planes = datos_uso_planes_dict # Pasamos el dict completo
                labels_uso_planes = ['Planes Activos', 'Planes Completados']
                data_values_uso_planes = [datos_uso_planes_dict['activos'], datos_uso_planes_dict['completados']]
            else:
                flash("No se encontraron planes de cuidado creados en el periodo seleccionado.", "info")

    except Exception as e:
        print(f"Error generando reporte: {e}")
        flash(f"Error al procesar la solicitud del reporte: {str(e)}", "danger")
    finally:
        if connection and connection.is_connected():
            connection.close()

    # 5. Renderizar el template, pasando TODOS los formularios y datos
    return render_template(
        'admin/reportes_dashboard.html',
        # Formularios
        form_ingresos=form_ingresos,
        form_utilidad=form_utilidad,
        form_nuevos_pac=form_nuevos_pac,
        form_pac_frec=form_pac_frec,
        form_seguimientos=form_seguimientos,
        form_uso_planes=form_uso_planes,
        # Datos para Ingresos
        datos_ingresos=datos_ingresos,
        labels_ingresos=labels_ingresos,
        data_values_ingresos=data_values_ingresos,
        # Datos para Utilidad
        datos_utilidad=datos_utilidad,
        labels_utilidad=labels_utilidad,
        data_values_utilidad=data_values_utilidad,
        # Datos para Nuevos Pacientes
        datos_nuevos_pacientes=datos_nuevos_pacientes,
        labels_nuevos_pac=labels_nuevos_pac,
        data_values_nuevos_pac=data_values_nuevos_pac,
        # Datos para Pacientes Frecuentes
        datos_pacientes_frecuentes=datos_pacientes_frecuentes,
        # Datos para Seguimientos
        datos_seguimientos=datos_seguimientos,
        labels_seguimientos=labels_seguimientos,
        data_values_seguimientos=data_values_seguimientos,
        # Datos para Uso de Planes
        datos_uso_planes=datos_uso_planes,
        labels_uso_planes=labels_uso_planes,
        data_values_uso_planes=data_values_uso_planes
    )

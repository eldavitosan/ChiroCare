import os
from flask import (
    Blueprint, render_template, request, redirect, jsonify, session, flash, url_for
)
from database import verify_login, connect_to_db 
from mysql.connector import Error
from forms import LoginForm

# 1. Crear el Blueprint
# El 'template_folder' apunta dos niveles arriba (de 'src/blueprints/' a 'templates/')
auth_bp = Blueprint('auth', 
                    __name__, 
                    template_folder='../../templates')

# 2. Mover las rutas de 'main.py' aquí, cambiando '@app.route' por '@auth_bp.route'

@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'id_dr' in session:
        return redirect(url_for('main'))

    # --- USAR FLASK-WTF ---
    form = LoginForm() # 1. Instanciar el formulario

    # 2. Remplazar 'request.method == POST' con 'form.validate_on_submit()'
    if form.validate_on_submit():
        # 3. Acceder a los datos con form.campo.data
        usuario = form.usuario.data.strip()
        password_form = form.contraseña.data

        # La validación (ej. campos vacíos) ya la hizo el formulario
        
        connection = None
        try:
            connection = connect_to_db()
            if not connection:
                flash('Error de conexión a la base de datos.', 'danger')
                return render_template('index.html', form=form) # 4. Pasar el form al template

            user_data = verify_login(connection, usuario, password_form) 
            
            if user_data:
                if not user_data.get('esta_activo', False): 
                    flash('Esta cuenta de doctor ha sido desactivada.', 'danger')
                    return render_template('index.html', form=form) # 4. Pasar el form

                session['id_dr'] = user_data['id_dr']
                session['nombre_dr'] = user_data['nombre']
                session['usuario_dr'] = user_data['usuario']
                session['is_admin'] = (user_data.get('centro') == 0)
                session['id_centro_dr'] = user_data.get('centro') 
                
                flash(f"Bienvenido Dr. {user_data['nombre']}!", 'success')
                return redirect(url_for('main'))
            else:
                flash('Usuario o contraseña incorrectos.', 'danger')
        
        except Error as db_err:
            # ... (manejo de errores) ...
            flash("Error de base de datos durante el inicio de sesión.", "danger")
        except Exception as e:
            # ... (manejo de errores) ...
            flash("Ocurrió un error inesperado.", "danger")
        finally:
            if connection and connection.is_connected():
                connection.close()
        
        # Si el login falla, renderizar la página con el formulario
        # Los errores de validación (si los hubo) se mostrarán solos
        return render_template('index.html', form=form) # 4. Pasar el form

    # Si es GET, simplemente renderizar
    return render_template('index.html', form=form) # 4. Pasar el form
    
    
@auth_bp.route('/logout')
def logout():
    session.pop('usuario', None)
    session.pop('id_dr', None) 
    session.pop('nombre', None)
    session.pop('is_admin', None) # Asegúrate de limpiar todos los datos de sesión
    session.pop('nombre_dr', None)
    session.pop('usuario_dr', None)
    session.pop('id_centro_dr', None)

    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('auth.login')) # 'auth.login' es esta nueva ruta
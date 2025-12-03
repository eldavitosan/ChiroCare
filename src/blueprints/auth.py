import os
from flask import (
    Blueprint, render_template, request, redirect, jsonify, session, flash, url_for
)
from db.auth import verify_login, get_doctor_profile, update_doctor_preferences
from db.connection import connect_to_db, get_db_cursor 
from mysql.connector import Error
from forms import LoginForm
from decorators import login_required
from flask_wtf.csrf import generate_csrf

auth_bp = Blueprint('auth', 
                    __name__, 
                    template_folder='../../templates')

# 2. Mover las rutas de 'main.py' aquí, cambiando '@app.route' por '@auth_bp.route'

@auth_bp.route('/', methods=['GET', 'POST'])
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'id_dr' in session:
        return redirect(url_for('main'))

    form = LoginForm()

    if form.validate_on_submit():
        usuario = form.usuario.data.strip()
        password_form = form.contraseña.data

        # --- CAMBIO IMPORTANTE: USAMOS EL GESTOR DE CONTEXTO ---
        # Ya no necesitamos try...finally manual para cerrar la conexión
        try:
            with get_db_cursor() as (connection, cursor):
                if not connection:
                    flash('Error de conexión a la base de datos.', 'danger')
                    return render_template('index.html', form=form)

                user_data = verify_login(connection, usuario, password_form)
                
                if user_data:
                    if not user_data.get('esta_activo', False): 
                        flash('Esta cuenta de doctor ha sido desactivada.', 'danger')
                        return render_template('index.html', form=form)

                    session['id_dr'] = user_data['id_dr']
                    session['nombre_dr'] = user_data['nombre']
                    session['usuario_dr'] = user_data['usuario']
                    session['is_admin'] = (user_data.get('centro') == 0)
                    session['id_centro_dr'] = user_data.get('centro') 
                    
                    flash(f"Bienvenido Dr. {user_data['nombre']}!", 'success')
                    return redirect(url_for('main'))
                else:
                    flash('Usuario o contraseña incorrectos.', 'danger')
        
        except Exception as e:
            # En producción, es útil imprimir el error en consola para depurar
            print(f"Error en login: {e}") 
            flash("Ocurrió un error inesperado al iniciar sesión.", "danger")
        
        # El bloque 'with' cierra la conexión automáticamente aquí
        return render_template('index.html', form=form)

    return render_template('index.html', form=form)
    
    
@auth_bp.route('/logout')
def logout():
    session.clear() # Forma más rápida de limpiar todo
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    id_dr = session.get('id_dr')
    token = generate_csrf()
    
    # --- CAMBIO EN PERFIL ---
    try:
        # El parámetro commit=True es para guardar cambios si es POST
        with get_db_cursor(commit=True) as (connection, cursor):
            if not connection:
                flash('Error de conexión', 'danger')
                return redirect(url_for('main'))

            if request.method == 'POST':
                nueva_config = request.form.get('redireccion_select')
                if nueva_config and nueva_config.isdigit():
                    exito = update_doctor_preferences(connection, id_dr, int(nueva_config))
                    if exito:
                        flash('Preferencias actualizadas correctamente.', 'success')
                    else:
                        flash('Error al guardar preferencias.', 'danger')
                return redirect(url_for('auth.perfil'))

            # Método GET
            doctor_data = get_doctor_profile(connection, id_dr)
            return render_template('perfil.html', doctor=doctor_data, csrf_token=token)

    except Exception as e:
        print(f"Error en perfil: {e}")
        flash("Error al cargar el perfil.", "danger")
        return redirect(url_for('main'))
        

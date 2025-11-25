from functools import wraps
from flask import session, flash, redirect, url_for
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'id_dr' not in session:
            flash('Debes iniciar sesión para ver esta página.', 'warning')
            return redirect(url_for('auth.login')) # Apunta al blueprint de autenticación
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_admin_function(*args, **kwargs):
        # 1. Verificar si está logueado
        if 'id_dr' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth.login'))
        
        # 2. Verificar si es admin
        if not session.get('is_admin'):
            flash('Acceso denegado. Se requieren privilegios de administrador.', 'danger')
            # Redirige al dashboard principal (que sigue en main.py)
            return redirect(url_for('main')) 
        
        return f(*args, **kwargs)
    return decorated_admin_function
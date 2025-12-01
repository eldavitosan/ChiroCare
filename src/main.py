import os
import json
import google.generativeai as genai
from groq import Groq
from flask import Flask, render_template, request, redirect, jsonify, session, flash, url_for, Response, current_app
from dotenv import load_dotenv
from datetime import datetime, date, timedelta
from db.connection import connect_to_db
from db.reports import get_resumen_dia_anterior
from db.patients import get_patients_by_recent_followup
load_dotenv()  # Cargar variables de entorno desde el archivo .env
from utils.date_manager import to_frontend_str

from blueprints.auth import auth_bp
from blueprints.admin import admin_bp
from blueprints.patient import patient_bp 
from blueprints.clinical import clinical_bp

from decorators import login_required#, admin_required


app = Flask(__name__, static_folder='static', template_folder='../templates')
port = int(os.environ.get('PORT', 8080))
app.secret_key = os.environ.get('FLASK_SECRET_KEY')
if not app.secret_key:
    raise ValueError("No se encontró FLASK_SECRET_KEY en el archivo .env")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(BASE_DIR, 'ia_config.json')
ia_config = {}

try:
    # 2. Cargar el JSON
    with open(config_path, 'r') as f:
        ia_config = json.load(f)
    print(f"INFO: Configuración de IA cargada desde: {config_path}")
except Exception as e:
    print(f"ERROR: No se pudo cargar '{config_path}'. Usando defaults. Error: {e}")
    ia_config = {
        "text_models": ["meta-llama/llama-4-scout-17b-16e-instruct"],
        "vision_model": "gemini-1.5-pro-latest" # Usar un default
    }

# 3. Guardar la configuración RAW (para los modelos de texto)
app.config['IA_MODELS_CONFIG'] = ia_config 
# --- 5. Configurar e INICIALIZAR el modelo de TEXTO (Groq) ---
groq_api_key = os.environ.get("GROQ_API_KEY")
if groq_api_key:
    try:
        print(f"INFO: Inicializando cliente Groq...")
        # Creamos el cliente
        client_groq = Groq(api_key=groq_api_key)
            
        # ¡ESTA ES LA LÍNEA QUE FALTABA! Lo guardamos en la config
        app.config['GROQ_CLIENT'] = client_groq 
            
        print("✅ Cliente Groq inicializado y guardado en app.config")
    except Exception as e:
        print(f"ERROR: Falló al crear cliente Groq: {e}")
        app.config['GROQ_CLIENT'] = None
else:
    print("WARN: GROQ_API_KEY no encontrada. El modelo de texto Groq estará deshabilitado.")
    app.config['GROQ_CLIENT'] = None

# 4. Configurar e INICIALIZAR el modelo de VISIÓN (Gemini)
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
    # Leemos el nombre del modelo de visión del JSON
    vision_model_name = ia_config.get('vision_model', 'gemini-2.5-flash')
    print(f"INFO: Inicializando modelo de visión Gemini: {vision_model_name}")
    try:
        # Creamos el cliente con ESE modelo y lo guardamos
        app.config['GENERATIVE_MODEL'] = genai.GenerativeModel(vision_model_name)
    except Exception as e:
        print(f"ERROR: No se pudo inicializar el modelo Gemini '{vision_model_name}'. Error: {e}")
        app.config['GENERATIVE_MODEL'] = None
else:
    print("WARN: GEMINI_API_KEY no encontrada. El modelo generativo de visión estará deshabilitado.")
    app.config['GENERATIVE_MODEL'] = None


    
    
@app.template_filter('f_date')
def format_date(value):
    """Formatea un objeto date/datetime a DD/MM/YYYY."""
    if value and isinstance(value, (date, datetime)):
        return value.strftime('%d/%m/%Y')
    # Si es None, '0000-00-00', o ya es un string, devuélvelo tal cual
    return value

# --- Filto Jinja2 para campos <input type="date"> ---
@app.template_filter('f_date_html')
def format_date_html(value):
    """Formatea un objeto date/datetime a YYYY-MM-DD para HTML."""
    if value and isinstance(value, (date, datetime)):
        # El formato para <input type="date"> debe ser YYYY-MM-DD
        return value.strftime('%Y-%m-%d')
    return value


# --- Configuración de Subida de Archivos ---
# Define la carpeta donde se guardarán las imágenes. ¡Debe existir!
# Construimos la ruta absoluta basándonos en la ubicación de este archivo (main.py)
# app.root_path apunta a la carpeta 'src'
BASE_DIR = app.root_path 
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'patient_images')
RX_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'rx')
REVAL_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'revaloracion')

# Crea las carpetas si no existen usando la ruta absoluta
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RX_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REVAL_UPLOAD_FOLDER, exist_ok=True)

# Guardamos las rutas absolutas en la configuración de Flask
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['REVAL_UPLOAD_FOLDER'] = REVAL_UPLOAD_FOLDER
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}






# === REGISTRAR EL BLUEPRINT ===
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(patient_bp)
app.register_blueprint(clinical_bp)

def index():
     # Si ya está logueado, redirigir a main directo desde el index
    if 'usuario' in session:
        return redirect(url_for('main'))
    return render_template("index.html") # Muestra login si no hay sesión

@app.route("/main")
@login_required 
def main():
    connection = None
    ##recent_patients_list = [] # Lista vacía por defecto
    try:
        # Obtener nombre de usuario para saludo (como antes)
        nombre_usuario = session.get('nombre', session.get('usuario', 'Usuario'))

        # --- Obtener pacientes recientes ---
        connection = connect_to_db()
        ##if connection:
        ##    recent_patients_list = get_recent_patients(connection, limit=5) # Obtener los últimos 5
        ##    connection.close() # Cerrar conexión después de usarla
        ##else:
        ##    flash("No se pudo conectar a la base de datos para cargar pacientes recientes.", "warning")
        # ---------------------------------

        # Pasar la lista a la plantilla
        ##return render_template("main.html", username=nombre_usuario, recent_patients=recent_patients_list)

        if connection:
            # Llama a la nueva función con limit=10
            patients_list_for_template = get_patients_by_recent_followup(connection, limit=10) # Cambiado
            if not patients_list_for_template: # Si está vacía, muestra un mensaje amigable
                flash("No hay pacientes con seguimientos recientes para mostrar.", "info")
            connection.close()
        else:
            flash("No se pudo conectar a la base de datos para cargar pacientes.", "warning")
            patients_list_for_template = [] # Asegura que sea una lista vacía en caso de error de conexión
        # Pasa la lista a la plantilla con el mismo nombre de variable ('recent_patients')
        # o puedes cambiar el nombre si prefieres y actualizar la plantilla.
        # Por ahora, usaremos 'recent_patients' para minimizar cambios en el HTML.
        return render_template("main.html", username=nombre_usuario, recent_patients=patients_list_for_template)


    except Exception as e:
         # Manejo básico de errores si algo más falla
         app.logger.error(f"Error en la ruta /main: {e}", exc_info=True)
         flash("Ocurrió un error al cargar el dashboard.", "danger")
         # Asegurarse de cerrar conexión si quedó abierta por el error
         if connection and connection.is_connected():
             connection.close()
         # Redirigir a login podría ser una opción segura en caso de error grave
         # return redirect(url_for('login'))
         # O intentar renderizar con lo que se tenga
         return render_template("main.html", username=session.get('nombre', session.get('usuario', 'Usuario')), recent_patients=[])

@app.route('/resumen_ayer')
@login_required 
def resumen_dia_anterior():
    """
    Muestra la página de resumen de los pacientes atendidos el día anterior.
    """
    connection = None
    resumen_data = []
    fecha_ayer_str = to_frontend_str(datetime.now() - timedelta(days=1))

    try:
        connection = connect_to_db()
        if not connection:
            flash("Error de conexión a la base de datos.", "danger")
        else:
            # Llama a la función de la base de datos que creamos
            resumen_data = get_resumen_dia_anterior(connection)
            if not resumen_data:
                flash(f"No se encontraron seguimientos para el día {fecha_ayer_str}.", "info")

        # Renderiza la nueva plantilla, pasando los datos y la fecha
        return render_template('resumen_dia_anterior.html',
                               resumen_pacientes=resumen_data,
                               fecha_resumen=fecha_ayer_str)

    except Exception as e:
        print(f"Error en resumen_dia_anterior: {e}")
        flash("Ocurrió un error al generar el resumen del día anterior.", "danger")
        # Redirige al dashboard principal en caso de error grave
        return redirect(url_for('main'))
    finally:
        if connection and connection.is_connected():
            connection.close()



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port, debug=True)
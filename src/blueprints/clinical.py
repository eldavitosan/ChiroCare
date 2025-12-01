import os
import time
from db.connection import connect_to_db
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
from db.patients import (
    get_patient_by_id, mark_notes_as_seen, add_general_note
)
from db.finance import (
    get_active_plans_for_patient, get_terapias_fisicas, get_plan_cuidado_summary,
    get_specific_plan_cuidado, get_specific_plan_cuidado_by_date, save_plan_cuidado,
    get_productos_servicios_by_type, get_productos_by_ids, get_productos_servicios_venta,
    save_recibo, get_specific_recibo, get_plan_cuidado_activo_para_paciente,
    get_recibo_detalles_by_id, get_recibos_by_patient, get_recibo_by_id,
    get_active_plan_status, analizar_adicionales_plan, get_historial_compras_paciente
)
from db.auth import (
    get_all_doctors, get_centro_by_id
)
from datetime import datetime, timedelta, date
import uuid
import base64
import json
from PIL import Image
from flask import (
    Blueprint, render_template, request, redirect, jsonify, session, flash, url_for, Response, current_app
)
from flask_wtf.csrf import CSRFProtect
from mysql.connector import Error
from io import BytesIO
from xhtml2pdf import pisa
import cv2
import mediapipe as mp
from werkzeug.utils import secure_filename
import traceback

from forms import AntecedentesForm,AnamnesisForm
# Importar funciones de base de datos necesarias para ESTAS rutas

from utils.date_manager import to_frontend_str, to_db_str, calculate_age, parse_date

# Importar los decoradores
from decorators import login_required#, admin_required

# --- Mapeos (copiados de main.py) ---
CONDICIONES_GENERALES_MAP = {
    '1': 'Dolor de cuello', '2': 'Dolor de cabeza', '3': 'Alteraciones auditivas',
    '4': 'Hipertensión', '5': 'Entumecimiento brazos/manos', '6': 'Dolor hombros/brazos/manos',
    '7': 'Resfriados/gripe recurrentes', '8': 'Mareo', '9': 'Alergias/fiebre',
    '10': 'Hormigueo brazos/mano', '11': 'Debilidad', '12': 'Alteraciones visuales',
    '13': 'Falta de energía/fatiga', '14': 'Dolor parte media espalda/hombros', '15': 'Asma/sibilancia',
    '16': 'Dificultad para respirar/expirar', '17': 'Náuseas', '18': 'Indigestión/acidez estomacal/reflujo',
    '19': 'Cansancio/irritable', '20': 'Bronquitis', '21': 'Falta de aliento',
    '22': 'Ataques al corazón/angina', '23': 'Dolor de costillas/pecho', '24': 'Hipoglucemia',
    '25': 'Palpitaciones', '26': 'Úlceras/gastritis', '27': 'Dolor de espalda baja',
    '28': 'Entumecimiento piernas/pies', '29': 'Dificultades para orinar', '30': 'Calambres musculares piernas/pies',
    '31': 'Lesión cadera/rodilla/tobillo', '32': 'Dolor cadera/piernas/pies', '33': 'Frialdad piernas/pies',
    '34': 'Infecciones urinarias recurrentes', '35': 'Menstruaciones dolorosas', '36': 'Hormigueo piernas/pies',
    '37': 'Debilidad piernas/pies', '38': 'Ciática'
}
CONDICION_DIAGNOSTICADA_MAP = {
    '1': 'Dislocación (Pasado)', '2': 'Dislocación (Actual)', '3': 'Fractura (Pasado)',
    '4': 'Fractura (Actual)', '5': 'Tumor (Pasado)', '6': 'Tumor (Actual)',
    '7': 'Cáncer (Pasado)', '8': 'Cáncer (Actual)', '9': 'Embarazo (Pasado)',
    '10': 'Embarazo (Actual)', '11': 'Osteoartritis (Pasado)', '12': 'Osteoartritis (Actual)',
    '13': 'Implante Metálico (Pasado)', '14': 'Implante Metálico (Actual)', '15': 'Ataque Cardiaco (Pasado)',
    '16': 'Ataque Cardiaco (Actual)', '17': 'Epilepsia (Pasado)', '18': 'Epilepsia (Actual)'
}
DOLOR_INTENSO_MAP = {
    '1': 'al despertar', '2': 'por la mañana', '3': 'por la tarde',
    '4': 'por la noche', '5': 'durante el sueño', '6': 'todo el día/continuo'
}
TIPO_DOLOR_MAP = {
    '1': 'constante', '2': 'intermitente', '3': 'tensión', '4': 'adormecimiento',
    '5': 'rigidez', '6': 'opresivo', '7': 'punzante', '8': 'calambre',
    '9': 'ardor', '10': 'hormigueo', '11': 'debilidad'
}
COMO_COMENZO_MAP = { 1: 'Gradual', 2: 'Súbito', 3: 'Desconocido' }
DIAGRAMA_PUNTOS_COORDENADAS = {
    "cabeza": {"top": "5%", "left": "25%"},
    "hombrod": {"top": "17%", "left": "17%"},
    "hombroi": {"top": "17%", "left": "33%"},
    "bicepd": {"top": "27%", "left": "16%"},
    "bicepi": {"top": "27%", "left": "35%"},
    "antebrazod": {"top": "38%", "left": "12%"},
    "antebrazoi": {"top": "37%", "left": "38%"},
    "muñecad": {"top": "43%", "left": "9%"},
    "muñecai": {"top": "43%", "left": "41%"},
    "manod": {"top": "48%", "left": "7%"},
    "manoi": {"top": "48%", "left": "43%"},
    "pechod": {"top": "22%", "left": "21%"},
    "pechoi": {"top": "22%", "left": "29%"},
    "abdomen": {"top": "35%", "left": "25%"},
    "caderad": {"top": "45%", "left": "21%"},
    "caderai": {"top": "45%", "left": "29%"},
    "ingled": {"top": "49%", "left": "23%"},
    "inglei": {"top": "49%", "left": "27%"},
    "muslod": {"top": "57%", "left": "20%"},
    "musloi": {"top": "57%", "left": "30%"},
    "rodilladt": {"top": "68%", "left": "20%"},
    "rodillai": {"top": "68%", "left": "30%"},
    "piernad": {"top": "82%", "left": "20%"},
    "piernai": {"top": "82%", "left": "31%"},
    "pied": {"top": "93%", "left": "20%"},
    "piei": {"top": "93%", "left": "32%"},
    "cervicales": {"top": "11%", "left": "73%"},
    "trapecioi": {"top": "19%", "left": "68%"},
    "trapeciod": {"top": "19%", "left": "78%"},
    "codoi": {"top": "37%", "left": "61%"},
    "codod": {"top": "37%", "left": "84%"},
    "omoplatoi": {"top": "25%", "left": "68%"},
    "omoplatod": {"top": "25%", "left": "76%"},
    "dorsales": {"top": "30%", "left": "73%"},
    "lumbares": {"top": "39%", "left": "73%"},
    "coxis": {"top": "48%", "left": "73%"},
    "sacro": {"top": "54%", "left": "73%"},
    "gluteoi": {"top": "51%", "left": "70%"},
    "gluteod": {"top": "51%", "left": "76%"},
    "isquioi": {"top": "63%", "left": "68%"},
    "isquiod": {"top": "63%", "left": "77%"},
    "gastroi": {"top": "82%", "left": "67%"},
    "gastrod": {"top": "82%", "left": "77%"},
    "taloni": {"top": "95%", "left": "66%"},
    "talond": {"top": "96%", "left": "77%"}
}
ETAPA_CUIDADO_MAP = {
    'Sintomatico': 'Sintomático',
    'Correctivo': 'Correctivo',
    'Sintmatico-Correctico':'Sintomático-Correctivo',
    'Mantenimiento': 'Mantenimiento'
}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
# --- Fin Mapeos ---


# 1. Crear el Blueprint con prefijo de URL dinámico
clinical_bp = Blueprint('clinical', 
                        __name__, 
                        template_folder='../../templates',
                        url_prefix='/paciente/<int:patient_id>') # <--- ¡IMPORTANTE!


def get_generative_model():
    # Accede al modelo desde la configuración de la app
    return current_app.config.get('GENERATIVE_MODEL')

def get_groq_client():
    # Accede al cliente de Groq desde la configuración de la app
    return current_app.config.get('GROQ_CLIENT')

def generar_historia_con_ia(datos_formulario, mapas):
    generative_model = get_generative_model()
    groq_client = get_groq_client()
    # ... (TODA la lógica de 'generar_historia_con_ia' va aquí) ...
    # 1. Extraer y traducir datos (igual que antes)
    condicion_principal = datos_formulario.get('condicion1') or "No especificada"
    calificacion_principal = datos_formulario.get('calif1') or "N/A"
    
    dolor_intenso_ids = datos_formulario.get('dolor_intenso', '0,').strip('0,').split(',')
    tipo_dolor_ids = datos_formulario.get('tipo_dolor', '0,').strip('0,').split(',')
    
    dolor_intenso_textos = [mapas['dolor_intenso'].get(id.strip()) for id in dolor_intenso_ids if id.strip()]
    tipo_dolor_textos = [mapas['tipo_dolor'].get(id.strip()) for id in tipo_dolor_ids if id.strip()]
    
    como_comenzo_texto = mapas['como_comenzo'].get(datos_formulario.get('como_comenzo'), 'no especificado')

    # 2. Construir el prompt (unificado para todos los modelos)
    system_prompt = (
        "Eres un quiropráctico experto redactando la sección de anamnesis de una historia clínica. "
        "Tu tono debe ser profesional, objetivo y clínico. Tu respuesta debe ser únicamente el párrafo "
        "de la anamnesis, sin frases introductorias como 'Claro, aquí tienes...' o cualquier otro texto adicional."
    )
    user_prompt = (
        "Genera un párrafo narrativo coherente basado en la siguiente información del paciente. "
        "No incluyas los títulos de cada punto en la redacción final, solo úsalos para estructurar tu texto.\n\n"
        "--- DATOS DEL PACIENTE ---\n"
        f"- Motivo de Consulta Principal: {condicion_principal}\n"
        f"- Severidad del Motivo Principal (Escala 0-10): {calificacion_principal} (especificar en la redacción que es 'según la escala de Borg')\n"
        f"- Antigüedad del Padecimiento: {datos_formulario.get('primera_vez') or 'No especificado'}\n"
        f"- Modo de Inicio: {como_comenzo_texto}\n"
        f"- Causa Atribuida (según el paciente): {datos_formulario.get('como_ocurrio') or 'No especificado'}\n"
        f"- Características del Dolor: {', '.join(tipo_dolor_textos) if tipo_dolor_textos else 'No especificado'}\n"
        f"- Momentos de Mayor Intensidad: {', '.join(dolor_intenso_textos) if dolor_intenso_textos else 'No especificado'}\n"
        f"- Factores Agravantes: {datos_formulario.get('empeora') or 'No especificado'}\n"
        f"- Factores Atenuantes: {datos_formulario.get('alivia') or 'No especificado'}\n"
        f"- Actividades de la Vida Diaria Afectadas: {datos_formulario.get('actividades_afectadas') or 'No especificado'}\n"
        "--- FIN DE DATOS ---"
    )
   
    # --- CADENA DE RESPALDO DE IA (NUEVA LÓGICA) ---
    historia_generada = None
    
    # 1. Leer la lista de modelos desde la config
    text_models_list = current_app.config['IA_MODELS_CONFIG'].get('text_models', [])

    # ---------------------------------------------------------
    # DIAGNÓSTICO: ¿Por qué se salta Groq?
    # ---------------------------------------------------------
    print(f"--- DIAGNÓSTICO PREVIO ---")
    print(f"Estado de groq_client: {'ACTIVO' if groq_client else 'NONE (No existe)'}")
    print(f"Lista de modelos: {text_models_list}")

    # 2. Intentar con Groq (si está disponible)
    if groq_client and text_models_list:
        for model_name in text_models_list:
            print(f"INFO: Intentando generar historia con Groq (Modelo: {model_name})...")
            try:
                chat_completion = groq_client.chat.completions.create(
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    model=model_name
                )
                historia_generada = chat_completion.choices[0].message.content.strip()
                if historia_generada:
                    print(f"--- ÉXITO CON GROQ ({model_name}) ---")
                    break # ¡Éxito! Salimos del bucle
                raise ValueError("Respuesta de Groq vacía.")
            except Exception as e:
                print(f"\n🔴 ERROR DETALLADO DE GROQ: {e}")
                print("--- Traceback (Rastro del error) ---")
                traceback.print_exc() 
                print("------------------------------------\n")

                print("INFO1: Groq falló. Intentando generar historia con Gemini...")
        
        if historia_generada:
            return historia_generada # Devolver si Groq tuvo éxito

    # 3. Intentar con Gemini (si Groq falló o no estaba disponible)
    if not historia_generada and generative_model:
        print("INFO2: Groq falló. Intentando generar historia con Gemini...")
        try:
            full_prompt_gemini = f"{system_prompt}\n{user_prompt}"
            response = generative_model.generate_content(full_prompt_gemini)
            historia_generada = response.text.strip()
            if historia_generada:
                print(f"--- ÉXITO CON GEMINI ---")
                return historia_generada
            raise ValueError("Respuesta de Gemini vacía.")
        except Exception as e:
            print(f"ADVERTENCIA: La llamada a Gemini falló: {e}.")

    # 4. Último Recurso (si todo lo demás falla)
    print("ADVERTENCIA: Todas las APIs de IA fallaron. Usando el generador de historia de respaldo.")
    historia_respaldo = (
        f"Paciente refiere dolor de '{condicion_principal}' ({calificacion_principal}/10 según la escala de Borg) "
        # ... (tu texto de respaldo) ...
    )
    return historia_respaldo

def procesar_y_guardar_imagen_postura(file_storage, save_folder, base_filename, view_type='frontal'):
    """
    Procesa una imagen de postura replicando EXACTAMENTE la lógica y apariencia de pose.py.
    """
    # ... (la parte inicial de manejo de archivos no cambia)
    if not file_storage or file_storage.filename == '' or not allowed_file(file_storage.filename):
        return None, "Archivo no válido o no proporcionado."
    os.makedirs(save_folder, exist_ok=True)
    extension = file_storage.filename.rsplit('.', 1)[1].lower()
    unique_id = uuid.uuid4().hex[:6]
    final_filename = f"{base_filename}_{unique_id}.{extension}"
    final_save_path = os.path.join(save_folder, final_filename)
    temp_path = os.path.join(save_folder, f"temp_{unique_id}.{extension}")
    file_storage.save(temp_path)

    image_to_save = None
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(static_image_mode=True, model_complexity=2, min_detection_confidence=0.5)

    try:
        image = cv2.imread(temp_path)
        if image is None: raise ValueError("OpenCV no pudo leer la imagen.")

        # Replicar el re-escalado del script para consistencia
        image = cv2.resize(image, (600, 800), interpolation=cv2.INTER_AREA)
        h, w, _ = image.shape
        
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = pose.process(image_rgb)
        annotated_image = image.copy()

        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # --- LÓGICA FRONTAL (IDÉNTICA A POSE.PY) ---
            if view_type == 'frontal':
                # Extraer coordenadas
                p = {id: (int(landmarks[id].x * w), int(landmarks[id].y * h)) for id in [0, 2, 5, 11, 12, 13, 14, 23, 24, 25, 26, 27, 28]}
                
                cv2.circle(annotated_image, (p[0]), 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, (p[2]), 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, (p[5]), 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, (p[11]), 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, (p[12]), 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, (p[13]), 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, (p[14]), 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, (p[23]), 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, (p[24]), 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, (p[25]), 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, (p[26]), 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, (p[27]), 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, (p[28]), 6, (0, 255, 255), -1)

                # Dibujar esqueleto básico (opcional, pero ayuda a visualizar)
                
                cv2.line(annotated_image, (p[5]), (p[2]), (0, 0, 255), 2)
                cv2.line(annotated_image, (p[11]), (p[12]), (0, 0, 255), 2)
                cv2.line(annotated_image, (p[13]), (p[14]), (0, 0, 255), 2)
                cv2.line(annotated_image, (p[23]), (p[24]), (0, 0, 255), 2)
                cv2.line(annotated_image, (p[25]), (p[26]), (0, 0, 255), 2)
                cv2.line(annotated_image, (p[27]), (p[28]), (0, 0, 255), 2)

                # Líneas horizontales de nivelación (ROJO en tu script)
                cv2.line(annotated_image, p[11], p[12], (0, 0, 255), 2)
                cv2.line(annotated_image, p[23], p[24], (0, 0, 255), 2)
                
                # Puntos medios y Línea de Plomada (ROJO en tu script)
                puntos_medios = [
                    ((p[2][0] + p[5][0]) // 2, (p[2][1] + p[5][1]) // 2),
                    ((p[11][0] + p[12][0]) // 2, (p[11][1] + p[12][1]) // 2),
                    ((p[13][0] + p[14][0]) // 2, (p[13][1] + p[14][1]) // 2),
                    ((p[23][0] + p[24][0]) // 2, (p[23][1] + p[24][1]) // 2),
                    ((p[25][0] + p[26][0]) // 2, (p[25][1] + p[26][1]) // 2),
                    ((p[27][0] + p[28][0]) // 2, (p[27][1] + p[28][1]) // 2),
                ]
                for i in range(len(puntos_medios) - 1):
                    cv2.line(annotated_image, puntos_medios[i], puntos_medios[i+1], (0, 0, 255), 2)
                xm=int((p[27][0] + p[28][0])/2)
                ym=int((p[27][1] + p[28][1])/2)
                cv2.line(annotated_image, (xm, ym+50), (xm, 1), (50, 205, 50), 2)
                

            # --- LÓGICA LATERAL (IDÉNTICA A POSE.PY) ---
            elif view_type in ['lateral_izq', 'lateral_der']:
                side_map = {'lateral_der': (7, 11, 23, 25, 27), 'lateral_izq': (8, 12, 24, 26, 28)}
                ids = side_map[view_type]
                p = {
                    'oreja': (int(landmarks[ids[0]].x * w), int(landmarks[ids[0]].y * h)),
                    'hombro': (int(landmarks[ids[1]].x * w), int(landmarks[ids[1]].y * h)),
                    'cadera': (int(landmarks[ids[2]].x * w), int(landmarks[ids[2]].y * h)),
                    'rodilla': (int(landmarks[ids[3]].x * w), int(landmarks[ids[3]].y * h)),
                    'tobillo': (int(landmarks[ids[4]].x * w), int(landmarks[ids[4]].y * h)),
                }
                
                # Líneas de conexión (ROJO)
                cv2.line(annotated_image, p['oreja'], p['hombro'], (0, 0, 255), 2)
                cv2.line(annotated_image, p['hombro'], p['cadera'], (0, 0, 255), 2)
                cv2.line(annotated_image, p['cadera'], p['rodilla'], (0, 0, 255), 2)
                cv2.line(annotated_image, p['rodilla'], p['tobillo'], (0, 0, 255), 2)

                # Círculos en las articulaciones (AMARILLO)
                cv2.circle(annotated_image, p['oreja'], 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, p['hombro'], 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, p['cadera'], 6, (0, 255, 255), -1)
                cv2.circle(annotated_image, p['rodilla'], 6 ,(0 , 255, 255), -1)
                cv2.circle(annotated_image, p['tobillo'], 6, (0, 255, 255), -1)
                
                # Líneas de referencia para CVA (VERDE)
                cv2.line(annotated_image, (p['tobillo'][0], p['tobillo'][1]+50), (p['tobillo'][0], 1), (0, 255, 0), 2)



            image_to_save = annotated_image
        else:
            print(f"ADVERTENCIA: No se detectó pose en {final_filename}.")
            image_to_save = image # Guardar la imagen re-escalada pero sin anotar

    except Exception as e:
        print(f"ERROR durante el procesamiento de pose: {e}. Se guardará la imagen original.")
        image_to_save = cv2.imread(temp_path)
    finally:
        pose.close()
        if os.path.exists(temp_path):
            os.remove(temp_path)

    if image_to_save is not None:
        save_success = cv2.imwrite(final_save_path, image_to_save)
        if save_success:
            print(f"ÉXITO: Imagen guardada en {final_save_path}")
            relative_path = os.path.join('uploads', 'patient_images', final_filename).replace("\\", "/")
            return relative_path, None
        else:
            return None, f"OpenCV no pudo guardar la imagen en {final_save_path}."
    else:
        return None, "La imagen a guardar estaba vacía."

def guardar_imagen_original(file_storage, save_folder, base_filename):
    """Función de respaldo para guardar la imagen sin procesar."""
    if not file_storage or file_storage.filename == '' or not allowed_file(file_storage.filename):
        return None, "Archivo no válido."
        
    extension = file_storage.filename.rsplit('.', 1)[1].lower()
    unique_id = uuid.uuid4().hex[:6]
    filename = f"{base_filename}_{unique_id}.{extension}"
    save_path = os.path.join(save_folder, filename)
    file_storage.save(save_path)
    relative_path = os.path.join('uploads', 'patient_images', filename).replace("\\", "/")
    return relative_path, None

def generar_informe_postura_con_ia(rutas_imagenes, notas_adicionales, hallazgos_calculados):
    """
    Llama a la IA multimodal (Gemini) con imágenes y texto para generar un informe.
    """
    generative_model = get_generative_model()
    if not generative_model:
        return "Error: El modelo de IA generativa no está configurado."
    

    # Construir el prompt con instrucciones claras
    system_prompt = (
        "Eres un quiropráctico y Fisioterapeuta experto en biomecánica. Tu tarea es realizar un análisis postural "
        "objetivo basado en las imágenes clínicas que se te proporcionarán. Interpreta las líneas, "
        "puntos y ángulos dibujados sobre las imágenes para identificar desviaciones y asimetrías. "
        "Tu lenguaje debe ser técnico, preciso y profesional. "
        "REGLAS DE FORMATO Y ESTILO:\n"
        "1. **Usa etiquetas HTML para el formato:** Utiliza <b> para títulos y énfasis, y <br><br> para separar párrafos. NO uses Markdown (asteriscos).\n"
        "2. **No incluyas encabezados:** Tu respuesta debe empezar directamente con el primer apartado del análisis, sin nombres de paciente o fechas.\n"
        "3. **Sé directo en el análisis visual:** Al describir los hallazgos de las imágenes, NO menciones los nombres de los archivos. Simplemente describe lo que observas (ej. 'En la vista frontal...').\n"
        "4. **Tu respuesta debe ser únicamente el informe en HTML**, sin texto introductorio como 'Claro, aquí tienes...'"
    )

    user_task = (
        "Analiza las imágenes adjuntas y genera un informe de postura. Sigue estrictamente esta estructura y checklist:\n\n"
        "--- DATOS OBJETIVOS DE POSTURA (HECHOS, NO INTERPRETAR) ---\n"
        f"- Hallazgo en Hombros: {hallazgos_calculados.get('hombros', 'No calculado.')}\n"
        f"- Hallazgo en Pelvis: {hallazgos_calculados.get('pelvis', 'No calculado.')}\n\n"
        "--- DATOS CLÍNICOS ADICIONALES ---\n"
        f"- Notas del Examen Físico: {notas_adicionales or 'No se proporcionaron.'}\n\n"
        "--- INFORME A GENERAR (USA ESTE FORMATO HTML) ---\n"
        "<b>1. Análisis del Plano Frontal:</b><br>"
        "   - <b>Alineación Frontal:</b> (**Basándote en los 'DATOS OBJETIVOS' proporcionados, describe la nivelación de hombros y pelvis.**).<br>"
        "   - <b>Línea de Plomada:</b> (Describe si la línea media se desvía y hacia dónde. Ej: 'Desviación lateral del tronco hacia la derecha').<br>"
        "<br>"
        "<b>2. Análisis del Plano Sagital (Lateral):</b><br>"
        "   - <b>Postura de la Cabeza (CVA):</b> (Describe si hay anteriorización o rectificación. Usa los términos 'Cabeza anteriorizada', 'Cabeza en posición neutra' o 'Rectificación cervical').<br>"
        "   - <b>Curvaturas Dorsal y Lumbar:</b> (Describe si hay 'Hipercifosis dorsal', 'Hipolordosis lumbar', 'Hiperlordosis lumbar' o 'Curvaturas dentro de límites normales').<br>"
        "   - <b>Inclinación Pélvica:</b> (Describe si hay 'Anteroversión pélvica', 'Retroversión pélvica' o 'Pelvis en posición neutra').<br>"
        "<br>"
        "<b>3. Conclusión Biomecánica:</b><br>"
        "(En un párrafo breve, resume 2-3 hallazgos clave y cómo podrían relacionarse con desequilibrios musculares o estrés articular. NO des un diagnóstico médico ni recomiendes tratamiento)."
    )

    # Cargar las imágenes
    prompt_parts = [system_prompt, user_task]
    image_order = ['frontal', 'lateral_izq', 'lateral_der']

    for view in image_order:
        if rutas_imagenes.get(view):
            try:
                # Construir la ruta absoluta completa a la imagen
                full_image_path = os.path.join(current_app.root_path, 'static', rutas_imagenes[view])
                print(f"DEBUG: Cargando imagen para IA desde: {full_image_path}")
                img = Image.open(full_image_path)
                prompt_parts.append(f"\n--- IMAGEN: VISTA {view.upper()} ---")
                prompt_parts.append(img)
            except FileNotFoundError:
                print(f"ADVERTENCIA: No se encontró el archivo de imagen en la ruta: {full_image_path}")
            except Exception as e:
                print(f"ERROR: No se pudo cargar la imagen {full_image_path}: {e}")

    if len(prompt_parts) <= 2: # Si no se cargó ninguna imagen
         return "Error: No se encontraron imágenes válidas para analizar. Asegúrate de que las pruebas se hayan guardado primero."

    # Llamar a la IA
    try:
        print("INFO: Enviando solicitud de análisis de postura a Gemini...")
        response = generative_model.generate_content(prompt_parts)
        return response.text.strip()
    except Exception as e:
        print(f"ERROR: La llamada a la API de Gemini para análisis de postura falló: {e}")
        return f"Error al generar el informe con IA: {e}"

def generar_informe_podal_unificado(rutas_imagenes, notas_adicionales, hallazgos_podales):
    """
    Llama a la IA multimodal (Gemini) con las 3 imágenes de los pies para
    generar un informe podal unificado.
    """
    generative_model = get_generative_model()
    if not generative_model:
        return "Error: El modelo de IA generativa (Gemini) no está configurado."
    

    # Construir el prompt unificado
    system_prompt = (
        "Eres un Podólogo y experto en biomecánica del pie y tobillo. Tu tarea es generar un informe técnico, "
        "objetivo y conciso. Tu respuesta debe ser exclusivamente el informe en HTML, sin texto introductorio."
    )
    user_task = (
        "Analiza las tres imágenes podales adjuntas (plantografía, vista frontal y vista trasera) y genera un informe. "
        "Sigue estrictamente esta estructura y checklist:\n\n"
        "--- DATOS OBJETIVOS DEL RETROPIÉ (HECHOS, NO INTERPRETAR) ---\n"
        f"- Pie Izquierdo: {hallazgos_podales.get('retropie_izq', 'No calculado.')}\n"
        f"- Pie Derecho: {hallazgos_podales.get('retropie_der', 'No calculado.')}\n\n"
        "--- DATOS CLÍNICOS ADICIONALES ---\n"
        f"- Notas Relevantes: {notas_adicionales or 'No se proporcionaron.'}\n\n"
        "--- INFORME A GENERAR (USA ESTE FORMATO HTML) ---\n"
        "<b>1. Análisis de la Huella Plantar (Plantografía):</b><br>"
        "   - <b>Tipo de Arco:</b> (Clasifica cada pie usando los términos: 'Arco normal (neutro)', 'Arco bajo (pie plano)', o 'Arco alto (pie cavo)').<br>"
        "   - <b>Distribución de Carga:</b> (Describe si se observa mayor carga en el retropié, antepié, borde medial o lateral. Ej: 'Hiperapoyo en cabezas metatarsales').<br>"
        "<br>"
        "<b>2. Análisis Estructural (Vistas Frontal y Trasera):</b><br>"
        "   - <b>Alineación del Retropié:</b> (**Usa los 'DATOS OBJETIVOS DEL RETROPIÉ' para describir la alineación del talón.**).<br>"
        "   - <b>Signos en Antepié:</b> (Desde la vista frontal, busca y describe signos como 'Hallux valgus', 'Dedos en garra', etc.).<br>"
        "<br>"
        "<b>3. Correlación y Conclusión Clínica:</b><br>"
        "(En un párrafo breve, explica cómo los hallazgos se conectan. Por ejemplo, cómo un 'Retropié en valgo' se correlaciona con un 'Arco bajo'. Finaliza con la implicación biomecánica general. NO des un diagnóstico médico ni recomiendes plantillas específicas).<br>"
        "<br>"
        "<b>4. Como puede afectar:</b><br>"
        "(En un párrafo breve, explica cómo los hallazgos pueden afectar a la columna vertebral y/o postura del paciente.)."

    )

    # Cargar las imágenes
    prompt_parts = [system_prompt, user_task]
    image_keys = {'frontal': 'pies_frontal', 'trasera': 'pies_trasera', 'plantografia': 'pies'}
    
    imagenes_cargadas = 0
    for view, ruta_key in image_keys.items():
        if rutas_imagenes.get(ruta_key):
            try:
                full_image_path = os.path.join(current_app.root_path, 'static', rutas_imagenes[ruta_key])
                print(f"DEBUG: Cargando imagen podal para IA desde: {full_image_path}")
                img = Image.open(full_image_path)
                prompt_parts.append(f"\n--- IMAGEN: VISTA {view.upper()} ---")
                prompt_parts.append(img)
                imagenes_cargadas += 1
            except FileNotFoundError:
                print(f"ADVERTENCIA: No se encontró el archivo de imagen podal: {full_image_path}")
            except Exception as e:
                print(f"ERROR: No se pudo cargar la imagen podal {full_image_path}: {e}")

    if imagenes_cargadas < 3: # Idealmente, necesitamos las 3
         return f"Error: Se encontraron {imagenes_cargadas} de 3 imágenes de pies necesarias. Asegúrate de que las tres imágenes (frontal, trasera y plantografía) estén guardadas."

    # Llamar a la IA
    try:
        print("INFO: Enviando solicitud de análisis podal unificado a Gemini...")
        response = generative_model.generate_content(prompt_parts)
        return response.text.strip()
    except Exception as e:
        print(f"ERROR: La llamada a la API de Gemini para análisis podal falló: {e}")
        return f"Error al generar el informe podal con IA: {e}"

def analizar_coordenadas_postura(ruta_imagen_frontal):
    """
    Analiza una imagen de postura frontal usando MediaPipe para determinar objetivamente
    la elevación de hombros y pelvis. Devuelve un diccionario con los hallazgos.
    """
    hallazgos = {
        "hombros": "Nivelación de hombros simétrica.",
        "pelvis": "Nivelación pélvica simétrica."
    }
    
    if not ruta_imagen_frontal or not os.path.exists(ruta_imagen_frontal):
        print(f"ADVERTENCIA: No se encontró la imagen frontal en {ruta_imagen_frontal} para el análisis de coordenadas.")
        return hallazgos

    try:
        image = cv2.imread(ruta_imagen_frontal)
        if image is None:
            raise ValueError("OpenCV no pudo leer la imagen.")

        mp_pose = mp.solutions.pose
        with mp_pose.Pose(static_image_mode=True, model_complexity=2) as pose:
            results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

            if results.pose_landmarks:
                landmarks = results.pose_landmarks.landmark
                
                # Coordenadas Y de hombros (11=izq, 12=der) y pelvis (23=izq, 24=der)
                hombro_izq_y = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER.value].y
                hombro_der_y = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER.value].y
                pelvis_izq_y = landmarks[mp_pose.PoseLandmark.LEFT_HIP.value].y
                pelvis_der_y = landmarks[mp_pose.PoseLandmark.RIGHT_HIP.value].y

                # Umbral de sensibilidad para evitar detectar micro-desviaciones
                umbral_hombros = 0.007 # Un 0.7% de la altura de la imagen
                
                # Comparación de Hombros (menor 'y' significa más alto en la imagen)
                if hombro_izq_y < hombro_der_y - umbral_hombros:
                    hallazgos["hombros"] = "Elevación del hombro izquierdo."
                elif hombro_der_y < hombro_izq_y - umbral_hombros:
                    hallazgos["hombros"] = "Elevación del hombro derecho."

                # Comparación de Pelvis
                if pelvis_izq_y < pelvis_der_y - umbral_hombros:
                    hallazgos["pelvis"] = "Elevación de la hemipelvis izquierda."
                elif pelvis_der_y < pelvis_izq_y - umbral_hombros:
                    hallazgos["pelvis"] = "Elevación de la hemipelvis derecha."
        
        return hallazgos

    except Exception as e:
        print(f"ERROR en analizar_coordenadas_postura: {e}")
        return hallazgos # Devuelve los valores por defecto si hay un error

def analizar_coordenadas_podal(ruta_imagen_trasera):
    """
    Intenta analizar la alineación del retropié. Si falla, devuelve hallazgos neutros.
    Esta función ya NO crea una imagen anotada.
    """
    hallazgos = {
        "retropie_izq": "Alineación de retropié izquierdo no determinada.",
        "retropie_der": "Alineación de retropié derecho no determinada."
    }
    
    if not ruta_imagen_trasera or not os.path.exists(ruta_imagen_trasera):
        return hallazgos

    try:
        image = cv2.imread(ruta_imagen_trasera)
        mp_pose = mp.solutions.pose
        with mp_pose.Pose(static_image_mode=True, model_complexity=2, min_detection_confidence=0.1) as pose:
            results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR_RGB))
            
            if results.pose_landmarks:
                # Si la detección tiene éxito, calcula los hallazgos
                landmarks = results.pose_landmarks.landmark
                
                tobillo_izq_x = landmarks[mp_pose.PoseLandmark.LEFT_ANKLE.value].x
                talon_izq_x = landmarks[mp_pose.PoseLandmark.LEFT_HEEL.value].x
                tobillo_der_x = landmarks[mp_pose.PoseLandmark.RIGHT_ANKLE.value].x
                talon_der_x = landmarks[mp_pose.PoseLandmark.RIGHT_HEEL.value].x
                
                umbral_retropie = 0.01

                # Lógica para Pie Izquierdo
                if tobillo_izq_x < talon_izq_x - umbral_retropie:
                    hallazgos["retropie_izq"] = "Retropié izquierdo en valgo."
                elif tobillo_izq_x > talon_izq_x + umbral_retropie:
                    hallazgos["retropie_izq"] = "Retropié izquierdo en varo."
                else:
                    hallazgos["retropie_izq"] = "Alineación de retropié izquierdo neutra."

                # Lógica para Pie Derecho
                if tobillo_der_x > talon_der_x + umbral_retropie:
                    hallazgos["retropie_der"] = "Retropié derecho en valgo."
                elif tobillo_der_x < talon_der_x - umbral_retropie:
                    hallazgos["retropie_der"] = "Retropié derecho en varo."
                else:
                    hallazgos["retropie_der"] = "Alineación de retropié derecho neutra."
        
        return hallazgos

    except Exception as e:
        print(f"ERROR durante el análisis silencioso de coordenadas podal: {e}")
        return hallazgos # Devuelve los hallazgos por defecto en caso de error

def generar_informe_integral_con_ia(datos_paciente, datos_anamnesis, datos_pruebas, hallazgos_calculados):
    generative_model = get_generative_model()
    if not generative_model:
        return "Error: El modelo de IA (Gemini) no está configurado."
    

    system_prompt = (
            "Eres un Quiropráctico y Fisioterapeuta con especialidad en biomecánica, redactando un informe de correlación clínica. "
            "Tu análisis debe ser objetivo, técnico y basado únicamente en la evidencia proporcionada (imágenes y datos). "
            "Tu respuesta debe ser exclusivamente el informe en formato HTML, sin texto introductorio ni conclusiones fuera de la plantilla proporcionada."
    )
        
        # Preparamos un resumen de síntomas más claro para la IA.
    sintomas = (
            f"Motivo principal de consulta: {datos_anamnesis.get('condicion1', 'No especificado')} "
            f"con una severidad de {datos_anamnesis.get('calif1', 'N/A')}/10. "
            f"El paciente reporta que el dolor empeora con: {datos_anamnesis.get('empeora', 'No especificado')}."
    )
        
        # Prompt del Usuario: Ahora es una plantilla HTML con instrucciones detalladas.
    user_task = (
            "Analiza TODAS las imágenes (postura y podales) y los datos clínicos para generar un informe integral. "
            "Completa la siguiente plantilla HTML con tus hallazgos. Sé conciso y enfócate en la conexión entre los hallazgos.\n\n"
            "--- DATOS OBJETIVOS DE POSTURA (HECHOS, NO INTERPRETAR) ---\n"
            f"- Hallazgo en Hombros: {hallazgos_calculados.get('hombros', 'No calculado.')}\n"
            f"- Hallazgo en Pelvis: {hallazgos_calculados.get('pelvis', 'No calculado.')}\n\n"
            "--- DATOS CLÍNICOS DEL PACIENTE ---\n"
            f"- Nombre: {datos_paciente.get('nombre')} {datos_paciente.get('apellidop')}\n"
            f"- Síntomas Clave: {sintomas}\n"
            f"- Notas del Examen Físico: {datos_pruebas.get('notas_pruebas_ortoneuro', 'No se proporcionaron notas.')}\n\n"
            "--- PLANTILLA DE INFORME A COMPLETAR ---\n\
            <b>1. Hallazgos Biomecánicos Principales:</b><br>\
            \
            &nbsp;&nbsp;<b>- Análisis Postural:</b> (**Usa los 'DATOS OBJETIVOS DE POSTURA' de arriba para describir la alineación frontal.** Luego, describe los hallazgos del plano sagital que observes en la imagen lateral).<br>\
            &nbsp;&nbsp;<b>- Análisis Podal:</b> (Describe el hallazgo más relevante de la pisada y estructura del pie. Ej: Arco bajo bilateral con retropié en valgo).<br>\
            <br>\
            <b>2. Correlación Clínica (Cadena Cinética):</b><br>\
            \
            (Párrafo conciso que explique la relación. Ej: La pronación del pie (retropié en valgo) puede generar una rotación interna de la tibia y el fémur, afectando la nivelación pélvica y contribuyendo a la tensión lumbar reportada...).<br>\
            <br>\
            <b>3. Conclusión y Pronóstico Funcional:</b><br>\
            \
            (Párrafo final de 2-3 frases. Ej: Los hallazgos sugieren un patrón de desequilibrio ascendente, donde la inestabilidad de la base podal contribuye a compensaciones posturales superiores. El objetivo del cuidado quiropráctico será restaurar la alineación y mejorar la función neuromuscular para mitigar el estrés sobre las áreas sintomáticas)."
    )
       
    
    prompt_parts = [system_prompt, user_task]
    
    # Cargar las 6 imágenes
    image_keys = ['frente', 'lado', 'postura_extra', 'pies_frontal', 'pies_trasera', 'pies']
    imagenes_cargadas = 0
    for key in image_keys:
        ruta_relativa = datos_pruebas.get(key)
        if ruta_relativa:
            try:
                full_image_path = os.path.join(current_app.root_path, 'static', ruta_relativa)
                img = Image.open(full_image_path)
                prompt_parts.append(f"\n--- IMAGEN: {key.upper()} ---")
                prompt_parts.append(img)
                imagenes_cargadas += 1
            except Exception as e:
                print(f"ADVERTENCIA: No se pudo cargar la imagen para el informe integral: {ruta_relativa} ({e})")

    if imagenes_cargadas == 0:
        return "No se encontraron imágenes de pruebas para analizar."

    try:
        print("INFO: Enviando solicitud de informe integral a Gemini...")
        response = generative_model.generate_content(prompt_parts)
        # **VERIFICACIÓN INTELIGENTE ANTES DE LEER EL TEXTO**
        # Si la respuesta no tiene partes (fue bloqueada), lo manejamos aquí.
        if not response.parts:
            # Intentamos obtener la razón del bloqueo para dar un mensaje más claro.
            try:
                block_reason = response.prompt_feedback.block_reason.name
                error_message = (
                    f"La solicitud a la IA fue bloqueada por el filtro de seguridad: '{block_reason}'. "
                    "Esto puede ser un falso positivo debido a la naturaleza de las imágenes clínicas. "
                    "Intente con imágenes diferentes si el problema persiste."
                )
            except (AttributeError, ValueError):
                error_message = (
                    "La IA no generó una respuesta. La solicitud pudo haber sido bloqueada por los filtros de contenido."
                )
            print(f"ERROR: Respuesta de Gemini bloqueada. Razón: {response.candidates[0].finish_reason}")
            return error_message

        informe_html = response.text.strip()
        # Limpiamos los marcadores de bloque de código de Markdown.
        if informe_html.startswith("```html"):
            informe_html = informe_html[7:] # Elimina "```html" del inicio
        if informe_html.endswith("```"):
            informe_html = informe_html[:-3] # Elimina "```" del final
        # --- FIN DE LA MEJORA ---

        import re
        informe_html = re.sub(r'', '', informe_html, flags=re.DOTALL)
        informe_html = informe_html.replace('*', '')
        
        return informe_html.strip()

    except Exception as e:
        # Capturamos el error real y lo devolvemos como un mensaje HTML formateado.
        print(f"ERROR: Falló la llamada a Gemini para el informe integral: {e}")
        # Devolvemos un mensaje de error más específico para mostrarlo en el PDF
        return f"<b>Error al contactar a la IA:</b><br><pre>{str(e)}</pre>"

def calculate_age(nacimiento_str):
    """Calcula la edad a partir de una fecha de nacimiento en formato dd/mm/yyyy."""
    if not nacimiento_str:
        return "N/A"
    try:
        nacimiento = datetime.strptime(nacimiento_str, '%d/%m/%Y')
        hoy = datetime.now()
        edad = hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))
        return edad
    except ValueError:
        return "N/A"

# --- Fin IA Helper Functions ---



@clinical_bp.route('/antecedentes', methods=['GET', 'POST'])
@login_required
def manage_antecedentes(patient_id): 
    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            flash('Error conectando a la base de datos.', 'danger')
            return redirect(url_for('main')) 

        patient = get_patient_by_id(connection, patient_id)
        if not patient:
            flash('Paciente no encontrado.', 'warning')
            return redirect(url_for('main')) 

        is_admin = session.get('is_admin', False)
        
        # Objeto 'date' para comparaciones lógicas
        today_date_obj = date.today()  
        # String 'dd/mm/YYYY' para la UI y para ENVIAR a la base de datos
        today_str = to_frontend_str(today_date_obj)

        # --- Instanciar el Formulario ---
        form = AntecedentesForm()

        # --- Poblar Opciones (Choices) Dinámicamente ---
        form.cond_gen.choices = [(k, v) for k, v in CONDICIONES_GENERALES_MAP.items()]
        

        if form.validate_on_submit():
            # --- LÓGICA POST (Guardar datos) ---
            print("DEBUG: El formulario VALIDÓ CORRECTAMENTE.") # <--- Print de éxito
            
            id_antecedente_editado_str = request.form.get('id_antecedente')
            id_antecedente_editado = int(id_antecedente_editado_str) if id_antecedente_editado_str else None

            is_editable_post = False
            # Por defecto, la fecha a guardar es HOY en formato 'dd/mm/YYYY'
            fecha_para_guardar_str = today_str 

            if id_antecedente_editado:
                record_original = get_specific_antecedente(connection, id_antecedente_editado)
                if record_original and record_original.get('id_px') == patient_id:
                    
                    # get_specific_antecedente devuelve un objeto 'date' de la BD
                    fecha_original_registro_obj = record_original.get('fecha') 
                    
                    # Comparamos objeto 'date' con objeto 'date'
                    if is_admin or fecha_original_registro_obj == today_date_obj:
                        is_editable_post = True
                    
                    # Si el admin edita y la fecha original existe, la usamos
                    if is_admin and fecha_original_registro_obj:
                         fecha_para_guardar_str = to_frontend_str(fecha_original_registro_obj)
                    # Si no es admin, la fecha se actualizará a 'today_str'
                    
                else:
                    flash("Error: No se encontró el registro original a actualizar.", "danger")
                    return redirect(url_for('clinical.manage_antecedentes', patient_id=patient_id))
            else: 
                # Creando uno nuevo, es editable y la fecha es 'today_str'
                is_editable_post = True
                fecha_para_guardar_str = today_str

            if not is_editable_post:
                flash('No tiene permiso para modificar estos antecedentes en este momento.', 'warning')
                redirect_args = {'patient_id': patient_id}
                if id_antecedente_editado: redirect_args['selected_id'] = id_antecedente_editado
                return redirect(url_for('clinical.manage_antecedentes', **redirect_args))

            # --- Recopilar datos desde form.data ---
            data = {'id_px': patient_id}
            
            # Guardamos la fecha en el formato 'dd/mm/YYYY'
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
            
            # Construir cadena de condiciones generales
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

            # --- Guardar en BBDD ---
            # save_antecedentes ahora usará STR_TO_DATE
            success = save_antecedentes(connection, data)

            if success:
                flash('Antecedentes guardados exitosamente.', 'success')
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))
            else:
                flash('Error al guardar los antecedentes.', 'danger')
                
                fecha_cargada_obj_error = today_date_obj
                val_date = parse_date(fecha_para_guardar_str)
                if val_date:
                    fecha_cargada_obj_error = val_date

                return render_template('antecedentes_form.html',
                                       patient=patient,
                                       all_records_info=get_antecedentes_summary(connection, patient_id),
                                       form=form, 
                                       is_editable=is_editable_post,
                                       loaded_id_antecedente=id_antecedente_editado,
                                       today_str=today_str,
                                       fecha_cargada=fecha_cargada_obj_error
                                       )

        else: 
            # --- LÓGICA GET (Cargar datos para mostrar) ---


            selected_id_str = request.args.get('selected_id')
            selected_id = int(selected_id_str) if selected_id_str else None

            all_records_info = get_antecedentes_summary(connection, patient_id) 

            current_data = None
            id_antecedente_a_cargar = None
            fecha_cargada_obj = today_date_obj # Default a hoy (objeto date)

            if selected_id: 
                current_data = get_specific_antecedente(connection, selected_id)
                if not (current_data and current_data.get('id_px') == patient_id):
                    flash("ID de antecedente seleccionado inválido.", "warning")
                    current_data = None 
                    selected_id = None 
                else:
                    id_antecedente_a_cargar = selected_id
                    if current_data.get('fecha'): # get_specific_... devuelve objeto date
                        fecha_cargada_obj = current_data.get('fecha')

            if current_data is None:
                 # get_specific_antecedente_by_date espera 'dd/mm/YYYY'
                 # ¡ASEGÚRATE DE APLICAR LA CORRECCIÓN 1 A ESTA FUNCIÓN EN DATABASE.PY!
                 current_data_today = get_specific_antecedente_by_date(connection, patient_id, today_str)
                 if current_data_today: 
                     current_data = current_data_today 
                     id_antecedente_a_cargar = current_data.get('id_antecedente')
                     if current_data.get('fecha'): # es un objeto date
                        fecha_cargada_obj = current_data.get('fecha')
                 else: 
                     current_data = {} 
                     id_antecedente_a_cargar = None
                     fecha_cargada_obj = today_date_obj 

            is_editable = is_admin or fecha_cargada_obj == today_date_obj
            
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
            
            form = AntecedentesForm(data=current_data_for_form)
            form.cond_gen.choices = [(k, v) for k, v in CONDICIONES_GENERALES_MAP.items()]
            
            return render_template('antecedentes_form.html',
                                   patient=patient,
                                   all_records_info=all_records_info,
                                   form=form, 
                                   is_editable=is_editable,
                                   loaded_id_antecedente=id_antecedente_a_cargar,
                                   today_str=today_str, # Pasamos 'dd/mm/YYYY'
                                   fecha_cargada=fecha_cargada_obj # Pasamos el objeto date
                                   ) 

    except Exception as e:
        print(f"Error en manage_antecedentes (PID {patient_id}): {e}") 
        flash('Ocurrió un error inesperado al gestionar antecedentes.', 'danger')
        safe_redirect_url = url_for('patient.patient_detail', patient_id=patient_id) 
        return redirect(safe_redirect_url)
    finally:
        if connection and connection.is_connected():
            connection.close()
            
@clinical_bp.route('/anamnesis', methods=['GET', 'POST'])
@login_required
def manage_anamnesis(patient_id): 
    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            flash('Error conectando a la base de datos.', 'danger')
            return redirect(url_for('main')) 

        patient = get_patient_by_id(connection, patient_id)
        if not patient:
            flash('Paciente no encontrado.', 'warning')
            return redirect(url_for('main')) 
        
        is_admin = session.get('is_admin', False)
        today_str = to_frontend_str(date.today())
        today_date_obj = date.today()

        form = AnamnesisForm()
        form.dolor_intenso_chk.choices = [(k, v) for k, v in DOLOR_INTENSO_MAP.items()]
        form.tipo_dolor_chk.choices = [(k, v) for k, v in TIPO_DOLOR_MAP.items()]

        if form.validate_on_submit():
            # --- LÓGICA POST ---
            id_anamnesis_editado_str = request.form.get('id_anamnesis') 
            id_anamnesis_editado = int(id_anamnesis_editado_str) if id_anamnesis_editado_str else None

            is_editable_post = False
            fecha_para_guardar_str = today_str 
            fecha_original_registro_obj = None

            if id_anamnesis_editado:
                # get_specific_anamnesis devuelve 'fecha' como un objeto date
                record_original = get_specific_anamnesis(connection, id_anamnesis_editado)
                if record_original and record_original.get('id_px') == patient_id:
                    
                    # --- CORRECCIÓN DE FECHA ---
                    fecha_original_registro_obj = record_original.get('fecha') # Ya es un objeto 'date'
                    if not isinstance(fecha_original_registro_obj, date):
                         fecha_original_registro_obj = parse_date(str(fecha_original_registro_obj))
                    # --- FIN CORRECCIÓN ---

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
            data['fecha'] = fecha_para_guardar_str # string 'dd/mm/yyyy'
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
            historia_generada = generar_historia_con_ia(data, mapas_para_ia)
            data['historia'] = historia_generada
            
            success = save_anamnesis(connection, data) # save_anamnesis espera un string

            if success == "duplicate":
                flash(f"Error: Ya existe un registro de anamnesis para este paciente en la fecha {data.get('fecha')}.", 'danger')
            elif success:
                flash('Anamnesis guardada exitosamente.', 'success')
                return redirect(url_for('patient.patient_detail', patient_id=patient_id))
            else:
                flash('Error al guardar la anamnesis.', 'danger')
            
            all_records_info = get_anamnesis_summary(connection, patient_id)
            selected_diagrama_puntos = data.get('diagrama', '0,').split(',')
            try:
                fecha_cargada_obj_error = parse_date(fecha_para_guardar_str) or today_date_obj
            except (ValueError, TypeError):
                fecha_cargada_obj_error = today_date_obj
            
            return render_template('anamnesis_form.html',
                                   patient=patient,
                                   all_records_info=all_records_info,
                                   form=form, 
                                   is_editable=is_editable_post,
                                   loaded_id_anamnesis=id_anamnesis_editado,
                                   today_str=today_str,
                                   DIAGRAMA_PUNTOS_COORDENADAS=DIAGRAMA_PUNTOS_COORDENADAS,
                                   selected_diagrama_puntos=selected_diagrama_puntos,
                                   fecha_cargada=fecha_cargada_obj_error,
                                   current_data=data
                                  )
        else: 
            # --- LÓGICA GET (o POST con validación fallida) ---
            
            # Definir defaults aquí para ambos caminos (GET y POST-Fallido)
            all_records_info = get_anamnesis_summary(connection, patient_id)
            selected_diagrama_puntos = ['0']
            fecha_cargada_obj = today_date_obj
            id_anamnesis_a_cargar = None
            is_editable = True
            current_data = None 
            

            if request.method == 'POST':
                # --- POST con validación fallida ---
                print(f"--- 2. Entrando a RAMA POST (Validación fallida) ---")
                print(f"--- 3. Errores del Form: {form.errors} ---")
                
                id_anamnesis_a_cargar_str = request.form.get('id_anamnesis')
                try: id_anamnesis_a_cargar = int(id_anamnesis_a_cargar_str) if id_anamnesis_a_cargar_str else None
                except ValueError: id_anamnesis_a_cargar = None
                
                fecha_cargada_str = request.form.get('fecha_cargada', today_str)
                is_editable = is_admin or (fecha_cargada_str == today_str)
                selected_diagrama_puntos = request.form.get('diagrama_puntos', '0,').split(',')
                
                try:
                    fecha_cargada_obj = parse_date(fecha_cargada_str) or today_date_obj
                except (ValueError, TypeError):
                    fecha_cargada_obj = today_date_obj
                
                # No hacemos nada más. 'form' ya tiene los datos del POST fallido.
                # 'current_data' sigue siendo None, lo cual está bien.
                print(f"--- 4. Variables (rama POST) actualizadas: 'selected_diagrama_puntos', 'is_editable', etc. ---")
                # 'form' ya contiene los datos del POST (no se toca)

            else:
                # --- Lógica GET Pura ---
                selected_id_str = request.args.get('selected_id')
                selected_id = int(selected_id_str) if selected_id_str else None

                # 'current_data' ya es None
                if selected_id:
                    current_data = get_specific_anamnesis(connection, selected_id) # 'fecha' es un objeto date
                    if not (current_data and current_data.get('id_px') == patient_id):
                        flash("ID de anamnesis seleccionado inválido.", "warning")
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
                
                current_data_for_form = current_data.copy()
                current_data_for_form['diagrama_puntos'] = current_data.get('diagrama', '0,')
                di_codes_str = current_data.get('dolor_intenso', '0,')
                current_data_for_form['dolor_intenso_chk'] = [code for code in di_codes_str.split(',') if code != '0']
                td_codes_str = current_data.get('tipo_dolor', '0,')
                current_data_for_form['tipo_dolor_chk'] = [code for code in td_codes_str.split(',') if code != '0']
                
                form.process(data=current_data_for_form) 
                form.dolor_intenso_chk.choices = [(k, v) for k, v in DOLOR_INTENSO_MAP.items()]
                form.tipo_dolor_chk.choices = [(k, v) for k, v in TIPO_DOLOR_MAP.items()]
                
                selected_diagrama_puntos = current_data.get('diagrama', '0,').split(',')
                


            # Este return ahora es seguro para ambas ramas (POST-fallido y GET)
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
    finally:
        if connection and connection.is_connected():
            connection.close()

# --- TODAS las demás rutas clínicas aquí ---

@clinical_bp.route('/pruebas', methods=['GET', 'POST'])
@login_required
def manage_pruebas(patient_id):
    connection = None
    try:
        # 1. Conectar y obtener datos básicos
        connection = connect_to_db()
        if not connection: flash('Error conectando a la base de datos.', 'danger'); return redirect(url_for('main'))
        patient = get_patient_by_id(connection, patient_id)
        if not patient:
             flash('Paciente no encontrado.', 'warning')
             if connection and connection.is_connected(): connection.close()
             return redirect(url_for('main'))

        # 2. Rollback Preventivo (opcional si autocommit=True, pero no hace daño)
        try: connection.rollback()
        except Error as rb_err: print(f"WARN: Error rollback preventivo (pruebas): {rb_err}")

        # 3. Datos comunes
        is_admin = session.get('is_admin', False)
        today_str = to_frontend_str(date.today())
        id_dr_actual = session.get('id_dr')
        if not id_dr_actual:
             flash("Error de sesión.", "danger"); return redirect(url_for('auth.login'))

        # --- Lógica POST (Guardado Granular) ---
        if request.method == 'POST':
            # Recolectar datos del form (ID, fecha, campos, archivos)
            id_postura_editado_str = request.form.get('id_postura')
            id_postura_editado = int(id_postura_editado_str) if id_postura_editado_str else None
            fecha_guardada = request.form.get('fecha_cargada', today_str) # Fecha que se estaba viendo/editando
            rx_files = request.files.getlist('fotos_rx') # Para nuevas Rx

            # Obtener todos los campos de texto/número
            tipo_calzado_form = request.form.get('tipo_calzado', '').strip()
            pie_cm_form = request.form.get('pie_cm')
            zapato_cm_form = request.form.get('zapato_cm')
            fuerza_izq_form = request.form.get('fuerza_izq')
            fuerza_der_form = request.form.get('fuerza_der')
            oxigeno_form = request.form.get('oxigeno')
            notas_plantillas_form = request.form.get('notas_plantillas', '').strip() 
            notas_pruebas_ortoneuro_form = request.form.get('notas_pruebas_ortoneuro', '').strip()

            # Obtener todos los archivos de imagen
            foto_frente_file = request.files.get('foto_frente')
            foto_lado_file = request.files.get('foto_lado')
            foto_postura3_file = request.files.get('foto_postura3') # Corresponde a postura_extra
            foto_termografia_file = request.files.get('foto_termografia')
            foto_pisada_file = request.files.get('foto_pisada') # Corresponde a pies
            foto_pies_frontal_file = request.files.get('foto_pies_frontal') 
            foto_pies_trasera_file = request.files.get('foto_pies_trasera') 


            print(f"INFO: Entering POST for pruebas. ID Editado: {id_postura_editado}, Fecha Guardada/Objetivo: {fecha_guardada}")

            # --- Iniciar Transacción ---
            try:
                print("INFO: Preparado para operaciones DB (Pruebas POST).")
            except Error as tx_err:
                 print(f"ERROR: Falló start_transaction (Pruebas POST): {tx_err}")
                 flash('Error interno al iniciar la operación.', 'danger')
                 return redirect(url_for('patient.patient_detail', patient_id=patient_id))

            # --- Bloque Try/Except para Operaciones ---
            try:
                record_original = get_specific_postura_by_date(connection, patient_id, fecha_guardada)
                existing_data = record_original if record_original else {}
                id_postura_actual_o_existente = existing_data.get('id_postura')

                if id_postura_editado and id_postura_editado != id_postura_actual_o_existente:
                     raise ValueError("Inconsistencia: El ID del formulario no coincide con el registro de la fecha.")

                # Determinar permisos
                es_fecha_de_hoy = (fecha_guardada == today_str)
                puede_editar_todo = is_admin or es_fecha_de_hoy
                record_exists = (id_postura_actual_o_existente is not None)
                # Se puede añadir Rx si es admin o si el registro base ya existe (aunque no se pueda editar)
                puede_anadir_rx = is_admin or record_exists


                # Verificar si la acción general está permitida
                # Permite añadir datos faltantes (incluyendo Rx) si el registro existe, aunque no sea hoy/admin
                accion_permitida = puede_editar_todo or (not puede_editar_todo and record_exists)
                if not accion_permitida:
                     if not is_admin and not es_fecha_de_hoy:
                         raise PermissionError("No tiene permiso para crear registros de pruebas para fechas pasadas.")
                     raise PermissionError("Acción no permitida para esta fecha y usuario.")

                # --- Preparar 'data_to_save' con lógica granular ---
                data_to_save = {'id_px': patient_id}
                if id_postura_actual_o_existente:
                    data_to_save['id_postura'] = id_postura_actual_o_existente
                    data_to_save['fecha'] = fecha_guardada # Mantener fecha si se edita
                else:
                    data_to_save['fecha'] = today_str # Usar fecha de hoy para nuevo registro

                # --- Procesar Campos Texto/Numérico ---
                campos_a_procesar = {
                    'tipo_calzado': (tipo_calzado_form, 'tipo_calzado'),
                    'pie_cm': (pie_cm_form, 'pie_cm'),
                    'zapato_cm': (zapato_cm_form, 'zapato_cm'),
                    'fuerza_izq': (fuerza_izq_form, 'fuerza_izq'),
                    'fuerza_der': (fuerza_der_form, 'fuerza_der'),
                    'oxigeno': (oxigeno_form, 'oxigeno'),
                    'notas_plantillas': (notas_plantillas_form, 'notas_plantillas'),
                    'notas_pruebas_ortoneuro': (notas_pruebas_ortoneuro_form, 'notas_pruebas_ortoneuro')
                
                }

                for form_value, db_key in campos_a_procesar.values():
                    original_value = existing_data.get(db_key)
                    if db_key in ['pie_cm', 'zapato_cm', 'fuerza_izq', 'fuerza_der', 'oxigeno']:
                        original_has_data = (original_value is not None)
                    else: # Texto (tipo_calzado, notas_plantillas)
                        original_has_data = bool(original_value) 

                    # Determinar si el valor del formulario es significativo (no vacío)
                    form_has_data = bool(form_value)

                    # Decidir si guardar el valor del formulario
                    should_save_form_value = False
                    if puede_editar_todo: # Si admin o es hoy, siempre guardar el valor del form (incluso si está vacío)
                        should_save_form_value = True
                    elif not original_has_data and form_has_data: # Si no puede editar todo, solo guardar si original estaba vacío Y el form tiene datos
                        should_save_form_value = True

                    if should_save_form_value:
                        # Asignar valor del formulario (CORREGIDO)
                        if db_key in ['pie_cm', 'zapato_cm', 'fuerza_izq', 'fuerza_der']:
                            try:
                                # Si el valor NO está vacío, conviértelo. Si ESTÁ vacío, guarda None (NULL).
                                data_to_save[db_key] = float(form_value) if form_value else None
                            except (ValueError, TypeError):
                                data_to_save[db_key] = None # Guardar NULL si la conversión falla
                        elif db_key == 'oxigeno':
                            try:
                                # Misma lógica para int
                                data_to_save[db_key] = int(form_value) if form_value else None
                            except (ValueError, TypeError):
                                data_to_save[db_key] = None # Guardar NULL si la conversión falla
                        else: # Texto
                            # Simplificado para guardar NULL si está vacío
                            data_to_save[db_key] = form_value.strip() if form_value else None
                    
                # --- Procesar Imágenes Fijas (con análisis de pose) ---
                image_inputs_map = {
                    'foto_frente': ('frente', 'frontal'),
                    'foto_lado': ('lado', 'lateral_izq'), # Asumimos que foto_lado es la izquierda
                    'foto_postura3': ('postura_extra', 'lateral_der'), # Asumimos que postura3 es la derecha
                    'foto_termografia': ('termografia', None), 
                    'foto_pisada': ('pies', None), 
                    'foto_pies_frontal': ('pies_frontal', None), 
                    'foto_pies_trasera': ('pies_trasera', None) 
                }

                for input_name, (db_column, view_type) in image_inputs_map.items():
                    file = request.files.get(input_name)
                    original_path = existing_data.get(db_column)
                    new_file_uploaded = file and file.filename != '' and allowed_file(file.filename)
                    file_path_to_save = original_path

                    should_save_new_file = False
                    if new_file_uploaded and (puede_editar_todo or not original_path):
                        should_save_new_file = True

                    if should_save_new_file:
                        base_filename = secure_filename(f"{patient_id}_{data_to_save['fecha'].replace('/', '-')}_{db_column}")
                        
                        # Si view_type no es None, procesamos la imagen. Si es None, solo la guardamos.
                        new_relative_path, error = procesar_y_guardar_imagen_postura(
                            file_storage=file,
                            save_folder=current_app.config['UPLOAD_FOLDER'],
                            base_filename=base_filename,
                            view_type=view_type
                        )
                        
                        if error:
                            flash(f"Advertencia al procesar '{input_name}': {error}", "warning")
                        
                        file_path_to_save = new_relative_path

                    elif file and file.filename != '' and not allowed_file(file.filename):
                         flash(f"Tipo de archivo no permitido para {input_name}.", "warning")
                    
                    data_to_save[db_column] = file_path_to_save

                # --- Guardar/Actualizar registro 'postura' ---
                # save_postura ahora debería esperar 'pies_frontal', 'pies_trasera', 'notas_plantillas'
                id_postura_resultante = save_postura(connection, data_to_save) 
                if not id_postura_resultante:
                     # Lanzar excepción específica para forzar rollback si save_postura falla
                     raise Exception("Fallo crítico al guardar/actualizar el registro base de postura.")


                # --- Procesar NUEVAS Radiografías ---
                rx_insert_count = 0
                if puede_anadir_rx and rx_files:
                    rx_upload_folder_path = current_app.config.get('RX_UPLOAD_FOLDER', os.path.join(current_app.config['UPLOAD_FOLDER'], 'rx'))
                    os.makedirs(rx_upload_folder_path, exist_ok=True) 
                    for i, file in enumerate(rx_files):
                        if file and file.filename != '' and allowed_file(file.filename):
                            filename_base = secure_filename(f"{patient_id}_{data_to_save['fecha'].replace('/', '-')}_rx_{i+1}")
                            extension = file.filename.rsplit('.', 1)[1].lower()
                            unique_id = uuid.uuid4().hex[:6]
                            filename = f"{filename_base}_{unique_id}.{extension}"
                            save_path = os.path.join(rx_upload_folder_path, filename)
                            try:
                                file.save(save_path)
                                file_path_to_save = os.path.join('uploads', 'patient_images', 'rx', filename).replace("\\", "/")
                                insert_radiografia(connection, id_postura_resultante, file_path_to_save) 
                                rx_insert_count += 1
                            except Exception as rx_save_err:
                                 print(f"ERROR guardando Rx {filename}: {rx_save_err}")
                                 flash(f"Error al guardar Rx '{file.filename}'.", "warning")
                        elif file and file.filename != '':
                             flash(f"Tipo de archivo no permitido para Rx: {file.filename}", "warning")
                    print(f"INFO: {rx_insert_count} nuevas Rx procesadas para id_postura {id_postura_resultante}.")

                print(f"INFO: Operaciones DB (Pruebas POST) completadas. ID Postura: {id_postura_resultante}")
                flash('Datos de pruebas guardados exitosamente.', 'success')
                # Redirigir a la misma fecha/ID que se guardó/actualizó
                return redirect(url_for('clinical.manage_pruebas', patient_id=patient_id, fecha=data_to_save['fecha']))

            except (PermissionError, ValueError, Exception) as e:
                print(f"ERROR: Iniciando rollback (Pruebas): {type(e).__name__} - {e}")
                print("INFO: Rollback ejecutado (o no necesario por autocommit) (Pruebas).")
                print(f"Error POST manage_pruebas (PID {patient_id}): {e}")

                if isinstance(e, PermissionError): flash(str(e), 'warning')
                elif isinstance(e, ValueError): flash(f"Error en datos o inconsistencia: {e}", 'danger')
                else: flash(f'Error interno al guardar: {e}', 'danger')

                # --- Re-renderizar formulario ---
                # Re-obtener datos para el estado antes del fallo
                available_dates_rerender = get_postura_summary(connection, patient_id)
                # Usar fecha_guardada que era el objetivo del POST
                current_data_rerender = get_specific_postura_by_date(connection, patient_id, fecha_guardada) or {}
                current_rx_list_rerender = []
                reloaded_id_postura = current_data_rerender.get('id_postura')
                if reloaded_id_postura:
                     current_rx_list_rerender = get_radiografias_for_postura(connection, reloaded_id_postura)

                # Re-calcular permisos para el estado que se mostrará
                _record_exists_rerender = (reloaded_id_postura is not None)
                _is_fully_editable_rerender = is_admin or (fecha_guardada == today_str)
                _can_add_rx_rerender = is_admin or _record_exists_rerender

                # Re-poblar 'current_data' con los datos del FORMULARIO que fallaron
                # Es importante NO sobrescribir las rutas de imagen existentes si no se intentó subir una nueva
                current_data_for_reload = { k: request.form.get(k) for k in request.form } 
                current_data_for_reload['id_px'] = patient_id # Asegurar id_px
                # Mantener rutas originales si no se subió archivo para ese campo
                if 'frente' not in request.files or not request.files['frente'].filename: current_data_for_reload['frente'] = existing_data.get('frente')
                if 'lado' not in request.files or not request.files['lado'].filename: current_data_for_reload['lado'] = existing_data.get('lado')
                if 'postura_extra' not in request.files or not request.files['postura_extra'].filename: current_data_for_reload['postura_extra'] = existing_data.get('postura_extra')
                if 'termografia' not in request.files or not request.files['termografia'].filename: current_data_for_reload['termografia'] = existing_data.get('termografia')
                if 'pies' not in request.files or not request.files['pies'].filename: current_data_for_reload['pies'] = existing_data.get('pies')
                if 'pies_frontal' not in request.files or not request.files['pies_frontal'].filename: current_data_for_reload['pies_frontal'] = existing_data.get('pies_frontal')
                if 'pies_trasera' not in request.files or not request.files['pies_trasera'].filename: current_data_for_reload['pies_trasera'] = existing_data.get('pies_trasera')
                # Asegurar que el ID de postura (si se estaba editando) se mantenga
                if id_postura_editado: current_data_for_reload['id_postura'] = id_postura_editado


                return render_template('pruebas_form.html',
                                       patient=patient,
                                       available_dates=available_dates_rerender,
                                       current_data=current_data_for_reload, 
                                       current_rx_list=current_rx_list_rerender, 
                                       is_fully_editable=_is_fully_editable_rerender,
                                       can_add_rx=_can_add_rx_rerender,
                                       is_admin=is_admin,
                                       loaded_date=fecha_guardada,
                                       today_str=today_str)
        # --- FIN MÉTODO POST ---

        # --- MÉTODO GET (Mostrar Formulario) ---
        else:
            selected_fecha_param = request.args.get('fecha')
            available_dates = get_postura_summary(connection, patient_id)
            target_date_to_load = None
            current_data = {}
            id_postura_actual = None
            record_exists_for_target_date = False
            

            # Lógica para determinar qué fecha cargar 
            if selected_fecha_param == 'hoy':
                target_date_to_load = today_str
            elif selected_fecha_param and selected_fecha_param in available_dates:
                target_date_to_load = selected_fecha_param
            elif available_dates:
                 target_date_to_load = available_dates[0] # Cargar el MÁS RECIENTE por defecto
            else:
                 target_date_to_load = today_str # Preparar para HOY (primer registro)

            # Obtener datos de postura para la fecha objetivo
            if target_date_to_load:
                loaded_postura_data = get_specific_postura_by_date(connection, patient_id, target_date_to_load)
                if loaded_postura_data:
                    current_data = loaded_postura_data
                    id_postura_actual = current_data.get('id_postura')
                    record_exists_for_target_date = True
                else: # Si no se encontraron datos para la fecha (ej. 'hoy' pero no hay registro)
                     current_data = {} # Formulario vacío
                     id_postura_actual = None
                     record_exists_for_target_date = False
            else: # Caso improbable, pero por seguridad
                current_data = {}
                id_postura_actual = None
                record_exists_for_target_date = False


            # Obtener lista de Rx asociadas al ID de postura cargado (si existe)
            fecha_cargada = target_date_to_load # La fecha que se mostrará en la UI
            current_rx_list = []
            if id_postura_actual:
                current_rx_list = get_radiografias_for_postura(connection, id_postura_actual)

            # Determinar permisos de edición para la plantilla
            is_fully_editable = is_admin or (fecha_cargada == today_str)
            can_add_rx = is_admin or record_exists_for_target_date # Puede añadir Rx si admin o si ya hay un registro de postura

            # Renderizar plantilla
            return render_template('pruebas_form.html',
                                   patient=patient,
                                   available_dates=available_dates,
                                   current_data=current_data,
                                   current_rx_list=current_rx_list,
                                   is_fully_editable=is_fully_editable,
                                   can_add_rx=can_add_rx,
                                   is_admin=is_admin,
                                   loaded_date=fecha_cargada,
                                   today_str=today_str)

    # --- Bloque except y finally exterior ---
    except Exception as e:
        print(f"Error general en manage_pruebas (PID {patient_id}): {e}")
        flash('Ocurrió un error inesperado al gestionar las pruebas.', 'danger')
        if connection and connection.is_connected():
             pass 
        safe_redirect_url = url_for('patient.patient_detail', patient_id=patient_id) if 'patient_id' in locals() else url_for('main')
        return redirect(safe_redirect_url)
    finally:
        if connection and connection.is_connected():
            connection.close()
            print("INFO: Conexión a BD cerrada en finally de manage_pruebas.")

@clinical_bp.route('/seguimiento', methods=['GET', 'POST'])
@login_required
def manage_seguimiento(patient_id):
    connection = None
    record_original = None 
    id_dr_para_guardar = session.get('id_dr') 

    try:
        connection = connect_to_db()
        if not connection: 
            flash('Error conectando a la base de datos.', 'danger')
            return redirect(url_for('main'))
        
        patient = get_patient_by_id(connection, patient_id)
        if not patient:
             flash('Paciente no encontrado.', 'warning')
             if connection and connection.is_connected(): connection.close()
             return redirect(url_for('main'))

        is_admin = session.get('is_admin', False)
        today_str = datetime.now().strftime('%d/%m/%Y')
        id_dr_actual_sesion = session.get('id_dr') 
        nombre_dr_actual_sesion = session.get('nombre_dr', 'Doctor Desconocido') 

        if not id_dr_actual_sesion:
             flash("Error de sesión. No se pudo identificar al doctor.", "danger")
             return redirect(url_for('auth.login'))

        active_plans_list = get_active_plans_for_patient(connection, patient_id)

        if request.method == 'POST':
            id_seguimiento_editado_str = request.form.get('id_seguimiento')
            id_seguimiento_editado = int(id_seguimiento_editado_str) if id_seguimiento_editado_str else None
            fecha_guardada = request.form.get('fecha_cargada', today_str)
            
            id_dr_para_guardar = id_dr_actual_sesion 

            # --- INICIO: LÓGICA DE TRANSACCIÓN ---
            try:
                connection.autocommit = False 

                if id_seguimiento_editado:
                    record_original = get_specific_seguimiento(connection, id_seguimiento_editado)
                    
                    # Validación simplificada: Solo verificamos que el ID pertenezca al paciente
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
                
                existing_data = record_original if record_original else {}

                data_to_save = {
                    'id_px': patient_id,
                    'id_dr': id_dr_para_guardar,
                    'fecha': fecha_guardada if (is_admin and record_original) else today_str
                }
                if id_seguimiento_editado:
                    data_to_save['id_seguimiento'] = id_seguimiento_editado
                
                id_plan_asociado_str = request.form.get('id_plan_cuidado_asociado')
                data_to_save['id_plan_cuidado_asociado'] = int(id_plan_asociado_str) if id_plan_asociado_str and id_plan_asociado_str.isdigit() else None
                
                # --- CORRECCIÓN 1: SEGMENTOS ---
                # Guardamos DIRECTAMENTE lo que viene del formulario
                segmentos = [
                    'occipital', 'atlas', 'axis', 'c3', 'c4', 'c5', 'c6', 'c7',
                    't1', 't2', 't3', 't4', 't5', 't6', 't7', 't8', 't9', 't10', 't11', 't12',
                    'l1', 'l2', 'l3', 'l4', 'l5', 'sacro', 'coxis', 'iliaco_d', 'iliaco_i', 'pubis'
                ]
                for seg in segmentos:
                    # Usamos el valor del form. Si no viene nada, cadena vacía.
                    data_to_save[seg] = request.form.get(seg, '').strip()

                # --- CORRECCIÓN 2: NOTAS ---
                # Forzamos guardar lo que el usuario escribió en el formulario
                data_to_save['notas'] = request.form.get('notas', '').strip()

                # --- CORRECCIÓN 3: TERAPIAS ---
                selected_therapy_ids = request.form.getlist('terapia_chk')
                valid_therapy_ids = [tid for tid in selected_therapy_ids if tid.isdigit()]
                terapia_string_form = '0,' + ','.join(sorted(valid_therapy_ids))
                if terapia_string_form == '0,': terapia_string_form = '0,'
                
                data_to_save['terapia'] = terapia_string_form

                # 1. Guardar el seguimiento
                saved_id_seguimiento = save_seguimiento(connection, data_to_save) 
                if not saved_id_seguimiento:
                    raise Exception("Error al guardar el seguimiento principal.")

                # 2. Guardar las Notas Ortopédicas (si aplica)
                notas_orto_form = request.form.get('notas_pruebas_ortoneuro')
                id_postura_para_actualizar_str = request.form.get('id_postura_hoy')
                id_postura_para_actualizar = int(id_postura_para_actualizar_str) if id_postura_para_actualizar_str and id_postura_para_actualizar_str.isdigit() else None

                # Quitamos la restricción estricta aquí también para permitir actualizar la nota
                if notas_orto_form is not None and id_postura_para_actualizar:
                    success_notas = update_postura_ortho_notes(connection, id_postura_para_actualizar, notas_orto_form.strip())
                    if not success_notas:
                        raise Exception("Error al guardar las notas ortopédicas.")

                # 3. Si todo salió bien, hacer commit
                connection.commit()
                
                flash('Seguimiento guardado exitosamente.', 'success')

                # --- Lógica Dinámica ---
                from db.auth import get_doctor_profile # Asegúrate de importar esto arriba
                
                perfil_dr = get_doctor_profile(connection, id_dr_actual_sesion)
                preferencia = perfil_dr.get('config_redireccion_seguimiento', 0) if perfil_dr else 0

                if preferencia == 1:
                    return redirect(url_for('main'))
                elif preferencia == 2:
                    return redirect(url_for('patient.patient_detail', patient_id=patient_id))
                else:
                    return redirect(url_for('clinical.manage_seguimiento', patient_id=patient_id, selected_id=saved_id_seguimiento))
            
            except (PermissionError, ValueError, Exception) as e:
                 print(f"Error POST manage_seguimiento (PID {patient_id}): {e}")
                 connection.rollback()
                 if isinstance(e, PermissionError): flash(str(e), 'warning')
                 elif isinstance(e, ValueError): flash(f"Error en datos: {e}", 'danger')
                 else: flash(f'Error interno al guardar: {e}', 'danger')

                 all_records_info_rerender = get_seguimiento_summary(connection, patient_id)
                 available_therapies_rerender = get_terapias_fisicas(connection)

                 current_data_for_reload = { k: request.form.get(k) for k in request.form }
                 current_data_for_reload['id_px'] = patient_id
                 current_data_for_reload['id_dr'] = id_dr_para_guardar 

                 current_data_for_reload['terapia'] = '0,' + ','.join(request.form.getlist('terapia_chk'))
                 if current_data_for_reload['terapia'] == '0,': 
                     current_data_for_reload['terapia'] = '0,'
                 current_selected_ids_rerender = current_data_for_reload['terapia'].split(',')
                 
                 if id_seguimiento_editado:
                    current_data_for_reload['id_seguimiento'] = id_seguimiento_editado
                 
                 if record_original:
                     current_data_for_reload['nombre_doctor_seguimiento'] = record_original.get('nombre_doctor_seguimiento', nombre_dr_actual_sesion)
                     for key_orig, val_orig in record_original.items():
                         if key_orig not in current_data_for_reload:
                             current_data_for_reload[key_orig] = val_orig
                 else:
                     current_data_for_reload['nombre_doctor_seguimiento'] = nombre_dr_actual_sesion

                 latest_anamnesis_rerender = get_latest_anamnesis(connection, patient_id) or {}
                 latest_postura_rerender = get_latest_postura_overall(connection, patient_id) or {}
                 latest_rx_list_rerender = get_latest_radiografias_overall(connection, patient_id, limit=4)
                 _is_editable_post_rerender = True # Forzamos editable al rerenderizar si falló
                 linked_plan_id_rerender_str = request.form.get('id_plan_cuidado_asociado')
                 linked_plan_id_rerender = int(linked_plan_id_rerender_str) if linked_plan_id_rerender_str and linked_plan_id_rerender_str.isdigit() else None

                 postura_data_hoy_rerender = get_specific_postura_by_date(connection, patient_id, today_str)
                 show_ortho_rerender = False
                 notes_ortho_rerender = request.form.get('notas_pruebas_ortoneuro', '') 
                 id_postura_rerender = request.form.get('id_postura_hoy')

                 if postura_data_hoy_rerender or id_postura_rerender: 
                    show_ortho_rerender = True
                    if not id_postura_rerender: 
                        id_postura_rerender = postura_data_hoy_rerender.get('id_postura') if postura_data_hoy_rerender else None
                    if not notes_ortho_rerender and postura_data_hoy_rerender:
                        notes_ortho_rerender = postura_data_hoy_rerender.get('notas_pruebas_ortoneuro', '')

                 return render_template('seguimiento_form.html',
                                         patient=patient,
                                         all_records_info=all_records_info_rerender,
                                         current_data=current_data_for_reload, 
                                         is_editable=_is_editable_post_rerender, 
                                         loaded_id_seguimiento=id_seguimiento_editado,
                                         today_str=today_str,
                                         available_therapies=available_therapies_rerender,
                                         current_selected_ids=current_selected_ids_rerender,
                                         historia_narrativa=latest_anamnesis_rerender.get('historia', ''),
                                         latest_postura_data=latest_postura_rerender,
                                         latest_rx_list=latest_rx_list_rerender,
                                         active_plans_list=active_plans_list,
                                         id_plan_asociado_seleccionado=linked_plan_id_rerender,
                                         nombre_doctor_sesion = current_data_for_reload.get('nombre_doctor_seguimiento', nombre_dr_actual_sesion),
                                         show_ortho_notes_field=show_ortho_rerender,
                                         ortho_notes_today=notes_ortho_rerender, 
                                         id_postura_hoy_para_form=id_postura_rerender
                                         )
            finally:
                if connection:
                    connection.autocommit = True
                
        else: # Método GET
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

            # --- CÁLCULO DE VISITAS (LÓGICA EN PYTHON) ---
            # 1. Extraemos valores seguros (usamos {} por si active_plan_status es None)
            safe_plan = active_plan_status if active_plan_status else {}
            
            qp_total = safe_plan.get('visitas_qp', 0)
            qp_restantes = safe_plan.get('qp_restantes', 0) 
            tf_total = safe_plan.get('visitas_tf', 0)
            tf_restantes = safe_plan.get('tf_restantes', 0)

            # 2. Calculamos cuántas se han consumido realmente (Matemática base)
            visita_qp_actual = qp_total - qp_restantes
            visita_tf_actual = tf_total - tf_restantes

            # 3. REGLA DE NEGOCIO:
            # Si id_seguimiento_a_cargar es None, estamos CREANDO un registro nuevo.
            # Por lo tanto, la visita actual será la siguiente a consumir (+1).
            if id_seguimiento_a_cargar is None:
                visita_qp_actual += 1
                visita_tf_actual += 1
            
            # Si id_seguimiento_a_cargar EXISTE, estamos VIENDO un registro pasado.
            # En ese caso, la BD ya descontó la visita, así que el cálculo base es correcto.
            # ---------------------------------------------

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
                                   
                                   # PASAMOS LAS VARIABLES YA CALCULADAS
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
    finally:
        if connection and connection.is_connected():
            connection.close()


@clinical_bp.route('/revaloracion', methods=['GET', 'POST'])
@login_required
def manage_revaloracion(patient_id):
    connection = None
    try:
        connection = connect_to_db()
        if not connection: flash('Error conectando.', 'danger'); return redirect(url_for('main'))
        patient = get_patient_by_id(connection, patient_id)
        if not patient: flash('Paciente no encontrado.', 'warning'); return redirect(url_for('main'))
        is_admin = session.get('is_admin', False)
        today_str = datetime.now().strftime('%d/%m/%Y')
        id_dr_actual = session.get('id_dr')
        if not id_dr_actual: flash("Error de sesión.", "danger"); return redirect(url_for('auth.login'))

        if request.method == 'POST':
            id_revaloracion_editado_str = request.form.get('id_revaloracion')
            id_revaloracion_editado = int(id_revaloracion_editado_str) if id_revaloracion_editado_str else None
            fecha_guardada = request.form.get('fecha_cargada', today_str)


            try:
                connection.autocommit = False
                print("INFO (Reval POST): Autocommit deshabilitado. Iniciando transacción.")
                
                is_editable_post = False
                record_original = None
                fecha_original_db_str = None # <--- 1. Variable para el string de fecha
                
                if id_revaloracion_editado:
                    record_original = get_specific_revaloracion(connection, id_revaloracion_editado)
                    
                    # --- !! INICIO DE LA CORRECCIÓN !! ---
                    
                    # 2. Convertir el objeto date de la BD a string
                    fecha_original_db_obj = record_original.get('fecha') if record_original else None
                    if isinstance(fecha_original_db_obj, date):
                        fecha_original_db_str = fecha_original_db_obj.strftime('%d/%m/%Y')

                    # 3. Comparar string vs string
                    if not (record_original and record_original.get('id_px') == patient_id and fecha_original_db_str == fecha_guardada):
                         raise ValueError("Revaloración a editar inválida.")
                    
                    # 4. Usar el string para la comprobación de 'is_editable'
                    if is_admin or (fecha_original_db_str == today_str): 
                         is_editable_post = True
                    # --- !! FIN DE LA CORRECCIÓN !! ---
                else: 
                     if fecha_guardada == today_str: is_editable_post = True
                     else: is_editable_post = is_admin
                if not is_editable_post: raise PermissionError('Permiso denegado.')


                # --- Preparar 'data_to_save'  ---
                data_to_save = { 'id_px': patient_id, 'id_dr': id_dr_actual, 'id_revaloracion': id_revaloracion_editado, 'fecha': fecha_guardada if (is_admin and record_original) else today_str, 'id_anamnesis_inicial': request.form.get('id_anamnesis_inicial') or None, 'diagrama_actual': request.form.get('diagrama_puntos', '0,') }
                
                if not data_to_save['diagrama_actual']: data_to_save['diagrama_actual'] = '0,'
                try: 
                    data_to_save['calif1_actual'] = int(request.form.get('calif1_actual') or 0)
                    data_to_save['calif2_actual'] = int(request.form.get('calif2_actual') or 0)
                    data_to_save['calif3_actual'] = int(request.form.get('calif3_actual') or 0)
                    data_to_save['mejora_subjetiva_pct'] = int(request.form.get('mejora_subjetiva_pct') or 0)
                    data_to_save['notas_adicionales_reval'] = request.form.get('notas_adicionales_reval', '').strip()
                    # -----------
                except ValueError: raise ValueError("Calificaciones/Porcentaje deben ser números.")

                # --- AÑADIR LÓGICA DE VINCULACIÓN DE POSTURA ---
                print(f"INFO (Reval POST): Buscando registro de postura para fecha {data_to_save['fecha']}...")
                postura_record_asociado = get_specific_postura_by_date(connection, patient_id, data_to_save['fecha'])
                id_postura_a_vincular = None
                if postura_record_asociado:
                    id_postura_a_vincular = postura_record_asociado.get('id_postura')
                    print(f"INFO (Reval POST): Encontrado id_postura: {id_postura_a_vincular}")
                else:
                    print(f"WARN (Reval POST): No se encontró registro de postura para la fecha {data_to_save['fecha']}. No se vincularán imágenes.")
                    flash(f"Advertencia: No se encontraron 'Pruebas' para la fecha {data_to_save['fecha']}. Guardando revaloración sin imágenes.", "info")
                
                data_to_save['id_postura_asociado'] = id_postura_a_vincular
                # --- FIN DE LÓGICA DE VINCULACIÓN ---

                # --- Guardar/Actualizar registro 'revaloraciones' ---
                saved_id = save_revaloracion(connection, data_to_save) # NO hace commit
                if not saved_id:
                    raise Exception("Error al guardar la revaloración.")

                # --- Commit y Redirección ---
                connection.commit()
                print(f"INFO: Transacción completada (commit) Revaloración. ID: {saved_id}")
                flash('Revaloración guardada exitosamente.', 'success')
                return redirect(url_for('clinical.manage_revaloracion', patient_id=patient_id, selected_id=saved_id))

            # ... (Bloque except para operaciones DB) ...
            except (PermissionError, ValueError, Exception) as e:
                 print(f"ERROR: Rollback Revaloración: {type(e).__name__} - {e}")
                 try:
                     connection.rollback()
                     print("INFO (Reval POST): Rollback ejecutado.")
                 except Error as rb_err:
                     print(f"ERROR: Falló el rollback de Revaloración: {rb_err}")

                 print(f"Error POST manage_revaloracion (PID {patient_id}): {e}")
                 
                 if isinstance(e, PermissionError): flash(str(e), 'warning')
                 elif isinstance(e, ValueError): flash(f"Error en datos: {e}", 'danger')
                 else: flash(f'Error interno al guardar: {e}', 'danger')

                 # --- Recargar datos para re-renderizar el formulario ---

                 # 1. Datos que el usuario intentó guardar (del formulario)
                 current_data_for_reload = { k: request.form.get(k) for k in request.form }
                 current_data_for_reload['id_px'] = patient_id
                 current_data_for_reload['diagrama_actual'] = request.form.get('diagrama_puntos', '0,')
                 
                 # (Ya no necesitamos repoblar las imágenes, se eliminó ese bloque)

                 # 2. Listas para los Dropdowns
                 all_records_info_rerender = get_revaloraciones_summary(connection, patient_id)
                 anamnesis_summary_list_rerender = get_anamnesis_summary(connection, patient_id)

                 # 3. Determinar qué anamnesis mostrar (la que se intentó vincular)
                 linked_anamnesis_id_rerender = request.form.get('id_anamnesis_inicial')
                 try: 
                     linked_anamnesis_id_rerender = int(linked_anamnesis_id_rerender) if linked_anamnesis_id_rerender else None
                 except ValueError: 
                     linked_anamnesis_id_rerender = None
                 
                 initial_anamnesis_data_rerender = None
                 if linked_anamnesis_id_rerender:
                     initial_anamnesis_data_rerender = get_specific_anamnesis(connection, linked_anamnesis_id_rerender)
                 if not initial_anamnesis_data_rerender:
                     initial_anamnesis_data_rerender = get_latest_anamnesis(connection, patient_id) or {}

                 # 4. Permisos
                 _is_editable_post_rerender = is_admin or (fecha_guardada == today_str)

                 # 5. Cargar los datos de Postura y RX para la fecha (para mostrar las imágenes)
                 postura_data_rerender = get_specific_postura_by_date(connection, patient_id, fecha_guardada) or {}
                 rx_list_rerender = []
                 if postura_data_rerender.get('id_postura'):
                     rx_list_rerender = get_radiografias_for_postura(connection, postura_data_rerender['id_postura'])
                 else:
                     rx_list_rerender = get_latest_radiografias_overall(connection, patient_id, limit=4)


                 # 6. Re-renderizar la plantilla
                 return render_template('revaloracion_form.html',
                                        patient=patient, 
                                        all_records_info=all_records_info_rerender,
                                        current_data=current_data_for_reload, 
                                        is_editable=_is_editable_post_rerender,
                                        loaded_id_revaloracion=id_revaloracion_editado,
                                        today_str=today_str,
                                        anamnesis_summary_list=anamnesis_summary_list_rerender,
                                        linked_anamnesis_id=linked_anamnesis_id_rerender,
                                        initial_anamnesis_data=initial_anamnesis_data_rerender,
                                        postura_data_for_date=postura_data_rerender, 
                                        latest_rx_list=rx_list_rerender, 
                                        DIAGRAMA_PUNTOS_COORDENADAS=DIAGRAMA_PUNTOS_COORDENADAS,
                                        loaded_date=fecha_guardada
                                        )
            finally: 
                if connection:
                    connection.autocommit = True
                    print("INFO (Reval POST): Autocommit restaurado a True.")

        # --- MÉTODO GET ---
        else:
            # 1. Obtener la revaloración seleccionada (o la de hoy)
            selected_id_str = request.args.get('selected_id')
            selected_id = int(selected_id_str) if selected_id_str else None
            all_records_info = get_revaloraciones_summary(connection, patient_id)
            
            current_data = None
            id_revaloracion_a_cargar = None
            fecha_cargada = None
            linked_anamnesis_id = None

            if selected_id:
                current_data = get_specific_revaloracion(connection, selected_id) 
                if not (current_data and current_data.get('id_px') == patient_id): 
                    flash("ID reval inválido.", "warning")
                    current_data = None
                    selected_id = None
                else: 
                    id_revaloracion_a_cargar = selected_id
                    fecha_cargada = current_data.get('fecha')
                    linked_anamnesis_id = current_data.get('id_anamnesis_inicial')
            
            if current_data is None:
                 current_data = get_specific_revaloracion_by_date(connection, patient_id, today_str) 
                 if current_data: 
                     id_revaloracion_a_cargar = current_data.get('id_revaloracion')
                     fecha_cargada = today_str
                     linked_anamnesis_id = current_data.get('id_anamnesis_inicial')
                 else: 
                     # Es un nuevo registro
                     current_data = {}
                     id_revaloracion_a_cargar = None
                     fecha_cargada = today_str # La fecha a cargar/guardar es hoy

            is_editable = is_admin or (fecha_cargada == today_str)

            # 2. Cargar la anamnesis vinculada (o la más reciente como fallback)
            anamnesis_summary_list = get_anamnesis_summary(connection, patient_id)
            if linked_anamnesis_id is None and anamnesis_summary_list: 
                linked_anamnesis_id = anamnesis_summary_list[0]['id_anamnesis']
            
            initial_anamnesis_data_for_labels = None
            if linked_anamnesis_id:
                initial_anamnesis_data_for_labels = get_specific_anamnesis(connection, linked_anamnesis_id)
            if not initial_anamnesis_data_for_labels:
                initial_anamnesis_data_for_labels = get_latest_anamnesis(connection, patient_id) or {}

            # 3. Cargar las Pruebas/Postura y RX asociadas a esta FECHA
            print(f"INFO (Reval GET): Cargando datos de postura para la fecha: {fecha_cargada}")
            postura_data_for_date = get_specific_postura_by_date(connection, patient_id, fecha_cargada) or {}
            rx_list_for_date = []
            
            # Verificar si el registro de postura tiene un ID
            id_postura_asociado = postura_data_for_date.get('id_postura')
            
            if id_postura_asociado:
                # Si hay un registro de postura, buscar sus RX
                print(f"INFO (Reval GET): Postura encontrada (ID: {id_postura_asociado}), buscando RX asociadas.")
                rx_list_for_date = get_radiografias_for_postura(connection, id_postura_asociado)
            else:
                # Si no hay registro de postura para esta fecha, las listas estarán vacías
                print(f"INFO (Reval GET): No se encontró registro de postura para {fecha_cargada}.")
                pass 

            # 4. Renderizar
            return render_template('revaloracion_form.html',
                                   patient=patient, 
                                   all_records_info=all_records_info, 
                                   current_data=current_data,
                                   is_editable=is_editable, 
                                   loaded_id_revaloracion=id_revaloracion_a_cargar,
                                   today_str=today_str, 
                                   anamnesis_summary_list=anamnesis_summary_list,
                                   linked_anamnesis_id=linked_anamnesis_id, 
                                   initial_anamnesis_data=initial_anamnesis_data_for_labels,
                                   postura_data_for_date=postura_data_for_date,
                                   latest_rx_list=rx_list_for_date,
                                   DIAGRAMA_PUNTOS_COORDENADAS=DIAGRAMA_PUNTOS_COORDENADAS, 
                                   loaded_date=fecha_cargada
                                  )

    except Exception as e:
        print(f"Error general en manage_revaloracion (PID {patient_id}): {e}")
        flash('Ocurrió un error inesperado al gestionar la revaloración.', 'danger')
        if connection and connection.is_connected():
             try: 
                 if not connection.autocommit: 
                     connection.rollback()
             except Error as rb_error: print(f"WARN: Error rollback externo (reval): {rb_error}")
        safe_redirect_url = url_for('patient.patient_detail', patient_id=patient_id) if 'patient_id' in locals() else url_for('main')
        return redirect(safe_redirect_url)
    finally:
        if connection and connection.is_connected():
            if not connection.autocommit: 
                 connection.autocommit = True
            connection.close()

@clinical_bp.route('/plan_cuidado', methods=['GET', 'POST'])
@login_required
def manage_plan_cuidado(patient_id):
    connection = None
    try:
        # 1. Conectar
        connection = connect_to_db()
        if not connection: 
            flash('Error conectando a la base de datos.', 'danger'); 
            return redirect(url_for('main'))
        
        patient = get_patient_by_id(connection, patient_id)
        if not patient:
             flash('Paciente no encontrado.', 'warning')
             if connection and connection.is_connected(): connection.close()
             return redirect(url_for('main'))

        # 3. Datos comunes
        is_admin = session.get('is_admin', False)
        today_str = datetime.now().strftime('%d/%m/%Y')
        id_dr_actual_sesion = session.get('id_dr')
        id_centro_dr_logueado = session.get('id_centro_dr') 

        if not id_dr_actual_sesion: 
            flash("Error de sesión.", "danger"); 
            return redirect(url_for('auth.login'))
        
        # --- Lógica para obtener doctores ---
        centro_para_filtrar_doctores = None
        if not is_admin: 
            centro_para_filtrar_doctores = id_centro_dr_logueado

        doctors_list = get_all_doctors(connection, 
                                       include_inactive=False, 
                                       filter_by_centro_id=centro_para_filtrar_doctores)

        adicionales_list = get_productos_servicios_by_type(connection, tipo_adicional=1)
        costo_qp_db = 0.0
        costo_tf_db = 0.0
        productos_base = get_productos_servicios_by_type(connection, tipo_adicional=0)

        for prod in productos_base:
            if prod.get('nombre', '').lower() == 'ajuste quiropractico': 
                costo_qp_db = float(prod.get('costo', 0.0))
            elif prod.get('nombre', '').lower() == 'terapia fisica': 
                costo_tf_db = float(prod.get('costo', 0.0))
        
        anamnesis_summary_list = get_anamnesis_summary(connection, patient_id) 

        # --- Lógica POST (Guardar Plan) ---
        if request.method == 'POST':
            id_plan_editado_str = request.form.get('id_plan')
            id_plan_editado = int(id_plan_editado_str) if id_plan_editado_str else None
            fecha_guardada = request.form.get('fecha_cargada', today_str)
            form_data = { k: request.form.get(k) for k in request.form }
            form_adicionales_ids = request.form.getlist('adicionales_chk')

            try:
                is_editable_post = False
                record_original = None
                fecha_original_db_str = None 

                if id_plan_editado:
                    record_original = get_specific_plan_cuidado(connection, id_plan_editado)
                    fecha_original_db_obj = record_original.get('fecha') if record_original else None
                    
                    if fecha_original_db_obj and hasattr(fecha_original_db_obj, 'strftime'):
                        fecha_original_db_str = fecha_original_db_obj.strftime('%d/%m/%Y')
                    
                    if not (record_original and record_original.get('id_px') == patient_id and fecha_original_db_str == fecha_guardada):
                         raise ValueError("Plan de cuidado a editar inválido.")
                    
                    if is_admin or (fecha_original_db_str == today_str):
                         is_editable_post = True
                else: 
                     if fecha_guardada == today_str: is_editable_post = True
                     else: is_editable_post = is_admin

                if not is_editable_post:
                    raise PermissionError('No tiene permiso para modificar/crear planes para esta fecha.')

                # Preparar datos
                data_to_save = {
                    'id_px': patient_id,
                    'id_plan': id_plan_editado,
                    'fecha': fecha_guardada if (is_admin and record_original) else today_str,
                    'id_dr': int(form_data.get('id_dr') or id_dr_actual_sesion),
                    'pb_diagnostico': form_data.get('pb_diagnostico', '').strip(),
                    'etapa': form_data.get('etapa', '').strip(),
                    'notas_plan': form_data.get('notas_plan', '').strip(),
                    'visitas_qp': 0, 'visitas_tf': 0, 'promocion_pct': 0,
                    'inversion_total': 0.0, 'ahorro_calculado': 0.0
                }
                
                # Cálculos
                inversion_total_neta = 0.0; ahorro_calculado = 0.0
                try:
                    visitas_qp = int(form_data.get('visitas_qp') or 0)
                    visitas_tf = int(form_data.get('visitas_tf') or 0)
                    promocion_pct = int(form_data.get('promocion_pct') or 0)
                    data_to_save['visitas_qp'] = visitas_qp
                    data_to_save['visitas_tf'] = visitas_tf
                    data_to_save['promocion_pct'] = promocion_pct
                    inversion_bruta = (visitas_qp * costo_qp_db) + (visitas_tf * costo_tf_db)
                    ahorro_calculado = (inversion_bruta * promocion_pct) / 100.0
                    inversion_total_neta = inversion_bruta - ahorro_calculado
                except ValueError:
                    raise ValueError("Visitas y promoción deben ser números enteros.")

                data_to_save['inversion_total'] = round(inversion_total_neta, 2)
                data_to_save['ahorro_calculado'] = round(ahorro_calculado, 2)

                valid_adicionales_ids = [aid for aid in form_adicionales_ids if aid.isdigit()]
                adicionales_string = '0,' + ','.join(sorted(valid_adicionales_ids))
                if adicionales_string == '0,': adicionales_string = '0,'
                data_to_save['adicionales_ids'] = adicionales_string

                saved_id = save_plan_cuidado(connection, data_to_save)
                if not saved_id: raise Exception("Error al guardar en BD.")

                flash('Plan de Cuidado guardado exitosamente.', 'success')
                return redirect(url_for('clinical.manage_plan_cuidado', patient_id=patient_id, selected_id=saved_id))

            except (PermissionError, ValueError, Exception) as e:
                 print(f"ERROR POST manage_plan_cuidado: {e}")
                 if isinstance(e, PermissionError): flash(str(e), 'warning')
                 elif isinstance(e, ValueError): flash(f"Error en datos: {e}", 'danger')
                 else: flash(f'Error interno: {e}', 'danger')
                 return redirect(url_for('clinical.manage_plan_cuidado', patient_id=patient_id))

        # --- Lógica GET ---
        else:
            today_date_obj = datetime.now().date()
            
            selected_id_str = request.args.get('selected_id')
            selected_id = int(selected_id_str) if selected_id_str else None
            all_records_info = get_plan_cuidado_summary(connection, patient_id)
            
            current_data = None
            id_plan_a_cargar = None
            fecha_cargada_obj = None
            linked_doctor_id = None
            qp_completadas = 0; tf_completadas = 0
            seguimientos_del_plan = []; adicionales_status = []

            if selected_id:
                 current_data = get_specific_plan_cuidado(connection, selected_id)
                 if current_data and current_data.get('id_px') == patient_id:
                     id_plan_a_cargar = selected_id
                     fecha_cargada_obj = current_data.get('fecha') 
                     linked_doctor_id = current_data.get('id_dr')
                 else:
                     current_data = None 

            if current_data is None:
                  current_data_today = get_specific_plan_cuidado_by_date(connection, patient_id, today_str)
                  if current_data_today:
                      current_data = current_data_today
                      id_plan_a_cargar = current_data.get('id_plan')
                      fecha_cargada_obj = current_data.get('fecha') 
                      linked_doctor_id = current_data.get('id_dr')
                  else: 
                      current_data = {}
                      id_plan_a_cargar = None
                      fecha_cargada_obj = today_date_obj 
                      linked_doctor_id = id_dr_actual_sesion 

            if id_plan_a_cargar:
                seguimientos_del_plan = get_seguimientos_for_plan(connection, id_plan_a_cargar) or []
                qp_completadas = len(seguimientos_del_plan)
                for seg in seguimientos_del_plan:
                    t_ids = seg.get('terapia', '0,').strip(',').split(',')
                    if any(tid != '0' and tid for tid in t_ids): tf_completadas += 1
                adicionales_status = analizar_adicionales_plan(connection, id_plan_a_cargar)
            
            is_editable = False
            if is_admin:
                is_editable = True
            elif fecha_cargada_obj == today_date_obj:
                is_editable = True

            adicionales_string = current_data.get('adicionales_ids', '0,') if current_data else '0,'
            current_selected_adicionales = adicionales_string.split(',')

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
                                   adicionales_status=adicionales_status
                                   )

    except Exception as e:
        print(f"Error general en manage_plan_cuidado: {e}")
        flash('Ocurrió un error inesperado.', 'danger')
        safe_redirect_url = url_for('patient.patient_detail', patient_id=patient_id) if 'patient_id' in locals() else url_for('main')
        return redirect(safe_redirect_url)
    finally:
        if connection and connection.is_connected():
            connection.close()


@clinical_bp.route('/recibo', methods=['GET', 'POST'])
@clinical_bp.route('/recibo/<int:recibo_id>', methods=['GET'])
@login_required
def manage_recibos(patient_id, recibo_id=None):
    connection = None
    
    patient_context = None
    productos_context = [] 
    recibos_anteriores_context = []
    current_recibo_data_context = None 
    current_recibo_detalles_context = []
    is_new_recibo_context = not bool(recibo_id)
    id_dr_actual_context = session.get('id_dr')
    today_str_context = datetime.now().strftime('%d/%m/%Y')
    recibo_id_cargado_context = recibo_id
    historial_compras_context = []

    if request.method == 'POST':
        connection_post = None
        try:
            connection_post = connect_to_db()
            if not connection_post: raise Exception("Error DB POST")
            connection_post.start_transaction()
            
            form_datos_recibo = {
                'id_px': patient_id,
                'id_dr': session.get('id_dr'), 
                'fecha': request.form.get('fecha_recibo', today_str_context), 
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
                connection_post.commit()
                flash('Recibo guardado.', 'success')
                return jsonify({ 
                    'success': True, 
                    'message': f'Recibo #{id_nuevo} guardado exitosamente.',
                    'new_receipt_id': id_nuevo,
                    'view_receipt_url': url_for('clinical.manage_recibos', patient_id=patient_id, recibo_id=id_nuevo),
                    'pdf_url': url_for('clinical.generate_recibo_pdf', patient_id=patient_id, id_recibo=id_nuevo) 
                }), 200
            else:
                # Si save_recibo devuelve None pero no lanza excepción
                if connection_post and connection_post.in_transaction: connection_post.rollback()
                print("Fallo al guardar recibo (save_recibo devolvió None).")
                return jsonify({'success': False, 'message': 'Error interno al intentar guardar el recibo (Lógica).'}), 500
        
        except (ValueError, TypeError, json.JSONDecodeError) as ve:
            if connection_post and connection_post.in_transaction: connection_post.rollback()
            print(f"Error de datos/JSON al procesar recibo: {ve}")
            return jsonify({'success': False, 'message': f"Error en los datos del recibo: {str(ve)}. Verifique."}), 400
        except Error as db_err:
            if connection_post and connection_post.in_transaction: connection_post.rollback()
            print(f"Error de BD al guardar recibo: {db_err}")
            return jsonify({'success': False, 'message': f"Error de base de datos al procesar el recibo."}), 500
        except Exception as e:
            if connection_post and connection_post.in_transaction: connection_post.rollback()
            print(f"Error general al guardar recibo: {e}")
            return jsonify({'success': False, 'message': f'Error inesperado al guardar el recibo.'}), 500
        finally:
            if connection_post and connection_post.is_connected(): connection_post.close()
        # --- FIN LÓGICA POST SIMPLIFICADA ---

    # --- LÓGICA GET ---
    try:
        connection = connect_to_db()
        if not connection:
            flash('Error conectando a la base de datos.', 'danger')
            return render_template('recibo_form.html', 
                                   patient=patient_context, 
                                   # ... (el resto de tus defaults) ...
                                  )


        patient_context = get_patient_by_id(connection, patient_id)
        if not patient_context:
            flash('Paciente no encontrado.', 'warning')
            return redirect(url_for('main'))

        productos_context = get_productos_servicios_venta(connection)
        recibos_anteriores_context = get_recibos_by_patient(connection, patient_id)
        historial_compras_context = []
        try:
            historial_compras_context = get_historial_compras_paciente(connection, patient_id)
        except Error as e_hist:
            print(f"Error al llamar a get_historial_compras_paciente: {e_hist}")

        # Definimos los defaults ANTES de la lógica
        is_new_recibo_context = True # Default es "Nuevo"
        current_recibo_data_context = None 
        id_dr_actual_context = session.get('id_dr')
        recibo_id_cargado_context = None

        if recibo_id: # Si la URL SÍ trae un ID (ej. /recibo/146)
            is_new_recibo_context = False # Intentamos cargar uno existente
            current_recibo_data_context = get_recibo_by_id(connection, recibo_id)
            

            if current_recibo_data_context and current_recibo_data_context.get('id_px') == patient_id:
                
                current_recibo_detalles_context = get_recibo_detalles_by_id(connection, recibo_id)
                id_dr_actual_context = current_recibo_data_context.get('id_dr', session.get('id_dr'))
                recibo_id_cargado_context = recibo_id # Confirmamos el ID cargado
                
                # Filtramos el historial
                if historial_compras_context:
                    try:
                        id_a_filtrar = int(recibo_id_cargado_context)
                        historial_compras_context = [
                            item for item in historial_compras_context 
                            if int(item.get('id_recibo', 0)) != id_a_filtrar
                        ]
                    except (ValueError, TypeError):
                        pass
            else:
                
                flash("Recibo no encontrado o no pertenece a este paciente. Mostrando formulario nuevo.", "warning")
                is_new_recibo_context = True # Falló, volvemos a modo "Nuevo"
                recibo_id_cargado_context = None
                current_recibo_data_context = None
                id_dr_actual_context = session.get('id_dr')
        
        else: # Si la URL NO trae un ID
            print(f"--- 2. No se solicitó ID. Preparando recibo nuevo. ---")
            is_new_recibo_context = True
            current_recibo_data_context = None 
            id_dr_actual_context = session.get('id_dr')
            
        print(f"--- 4. ESTADO FINAL: Paciente ID: {patient_id}, Recibo ID Cargado: {recibo_id_cargado_context}, Es Nuevo: {is_new_recibo_context} ---")
        
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
        print(f"Error general en GET manage_recibos: {e}")
        flash(f"Ocurrió un error al cargar la página de recibos: {str(e)}", "danger")
        return redirect(url_for('patient.patient_detail', patient_id=patient_id) if patient_id else url_for('main'))
    finally:
        if connection and connection.is_connected():
            connection.close()





@clinical_bp.route('/reporte')
@login_required
def generate_patient_report(patient_id):
    connection = None
    try:
        connection = connect_to_db()
        patient = get_patient_by_id(connection, patient_id) 
        today_str = datetime.now().strftime('%d/%m/%Y')

        anamnesis_episodes_list = get_anamnesis_summary(connection, patient_id)
        if not anamnesis_episodes_list:
            # 1. Muestra un mensaje al usuario
            flash("Este paciente aún no tiene registros de Anamnesis para generar un reporte de episodio.", "warning")

            # 2. Prepara un diccionario 'report_data' vacío o con valores mínimos
            #    Esto es para evitar errores en la plantilla si intenta acceder a datos que no existen.
            report_data = {
                'patient': patient, 
                'antecedente': {},
                'anamnesis': {},
                'postura': {},
                'rx_list': [],
                'comparison_initial_anamnesis': {},
                'comparison_linked_revals': [],
                 # Incluir los mapeos vacíos que la plantilla podría esperar
                'cond_gen_text': [], 'cond_diag_text': [], 'dolor_intenso_text': [],
                'tipo_dolor_text': [], 'como_comenzo_text': '', 'diagrama_puntos': []
            }

            # 3. Renderiza la plantilla del reporte, pero pasándole datos vacíos
            return render_template('reporte_paciente.html',
                                   data=report_data,
                                   anamnesis_episodes_list=[], 
                                   loaded_episode_id=None,    
                                   today_str=today_str,
                                   CONDICIONES_GENERALES_MAP=CONDICIONES_GENERALES_MAP, 
                                   DIAGRAMA_PUNTOS_COORDENADAS=DIAGRAMA_PUNTOS_COORDENADAS
                                  )
        selected_episode_id_str= request.args.get('selected_episode_id')
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

        # Obtener datos del episodio seleccionado
        episode_initial_anamnesis = get_specific_anamnesis(connection, selected_episode_id) or {}

        episode_start_date = episode_initial_anamnesis.get('fecha')

        antecedente_data = {}
        postura_data = {}
        rx_list = []
        postura_images = {} 
        centro_info = {}
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
        centro_info_db = get_centro_by_id(connection, id_centro_sesion) if id_centro_sesion else None
        if centro_info_db:
            centro_info = centro_info_db
        else: # Fallback por si no se encuentra
            centro_info = {'nombre': 'Chiropractic Care Center', 'direccion': 'N/A', 'cel': 'N/A', 'tel': 'N/A'}


        comparison_linked_revals = get_revaloraciones_linked_to_anamnesis(connection, selected_episode_id) if selected_episode_id else []
        # --- INICIO: Procesamiento de Datos para el Reporte ---

        # 1. Procesar Diagrama Corporal de Anamnesis Inicial
        diagrama_anam_inicial_str = episode_initial_anamnesis.get('diagrama', '0,')
        diagrama_puntos_inicial = [p for p in diagrama_anam_inicial_str.split(',') if p and p != '0']

        # 2. Procesar Condiciones Diagnosticadas (de Antecedentes)
        cond_diag_str = antecedente_data.get('condicion_diagnosticada', '0,')
        cond_diag_ids = [cd_id for cd_id in cond_diag_str.split(',') if cd_id and cd_id != '0']
        cond_diag_text_list = [CONDICION_DIAGNOSTICADA_MAP.get(cd_id, f"ID Desconocido: {cd_id}") for cd_id in cond_diag_ids]

        # 3. Procesar Síntomas Generales (de Antecedentes)
        cond_gen_str = antecedente_data.get('condiciones_generales', '0,')
        cond_gen_ids = [cg_id for cg_id in cond_gen_str.split(',') if cg_id and cg_id != '0']
        cond_gen_text_list = [CONDICIONES_GENERALES_MAP.get(cg_id, f"ID Desconocido: {cg_id}") for cg_id in cond_gen_ids]

        # 4. Procesar textos de "Cómo Comenzó", "Dolor Intenso", "Tipo Dolor" (de Anamnesis)
        como_comenzo_id = episode_initial_anamnesis.get('como_comenzo')
        como_comenzo_text = COMO_COMENZO_MAP.get(como_comenzo_id, 'N/A')

        dolor_intenso_str = episode_initial_anamnesis.get('dolor_intenso', '0,')
        dolor_intenso_ids = [di_id for di_id in dolor_intenso_str.split(',') if di_id and di_id != '0']
        dolor_intenso_text_list = [DOLOR_INTENSO_MAP.get(di_id, '') for di_id in dolor_intenso_ids]

        tipo_dolor_str = episode_initial_anamnesis.get('tipo_dolor', '0,')
        tipo_dolor_ids = [td_id for td_id in tipo_dolor_str.split(',') if td_id and td_id != '0']
        tipo_dolor_text_list = [TIPO_DOLOR_MAP.get(td_id, '') for td_id in tipo_dolor_ids]

        # --- FIN: Procesamiento de Datos ---

        # Preparar Datos para el Template
        report_data = {
            'patient': patient,
            'antecedente': antecedente_data,
            'anamnesis': episode_initial_anamnesis,
            'postura': postura_data,
            'rx_list': rx_list,
            'postura_images': postura_images, 
            'centro_info': centro_info,       
            'comparison_initial_anamnesis': episode_initial_anamnesis,
            'comparison_linked_revals': comparison_linked_revals, 
            'diagrama_puntos': diagrama_puntos_inicial, 
            'cond_diag_text': cond_diag_text_list,     
            'cond_gen_text': cond_gen_text_list,       
            'como_comenzo_text': como_comenzo_text,    
            'dolor_intenso_text': dolor_intenso_text_list, 
            'tipo_dolor_text': tipo_dolor_text_list      
        }

        # Renderizar la plantilla
        return render_template('reporte_paciente.html',
                               data=report_data,
                               anamnesis_episodes_list=anamnesis_episodes_list,
                               loaded_episode_id=selected_episode_id,
                               today_str=today_str,
                               CONDICIONES_GENERALES_MAP=CONDICIONES_GENERALES_MAP,
                               CONDICION_DIAGNOSTICADA_MAP=CONDICION_DIAGNOSTICADA_MAP, 
                               DIAGRAMA_PUNTOS_COORDENADAS=DIAGRAMA_PUNTOS_COORDENADAS
                              )

    # --- Bloque except y finally exterior ---
    except Exception as e:
         print(f"Error generando reporte para patient_id {patient_id}: {e}")
         flash('Ocurrió un error inesperado al generar el reporte.', 'danger')
         if connection and connection.is_connected():
             try: connection.rollback()
             except Error: pass
         safe_redirect_url = url_for('patient.patient_detail', patient_id=patient_id) if 'patient_id' in locals() else url_for('main')
         return redirect(safe_redirect_url)
    finally:
        if connection and connection.is_connected():
            connection.close()


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

    connection = None
    try:
        connection = connect_to_db()
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
    finally:
        if connection and connection.is_connected():
            connection.close()

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

    # 1. Obtener la ruta absoluta de la imagen frontal para analizarla
    ruta_frontal_relativa = rutas_imagenes.get('frontal')
    ruta_frontal_absoluta = os.path.join(current_app.root_path, 'static', ruta_frontal_relativa) if ruta_frontal_relativa else None

    # 2. Llamar a nuestra función para obtener los datos objetivos
    hallazgos_calculados = analizar_coordenadas_postura(ruta_frontal_absoluta)

     # 3. Generar el informe, pasando los hallazgos calculados
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
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Solicitud inválida.'}), 400

    rutas_imagenes = {
        'pies_frontal': data.get('ruta_pies_frontal'),
        'pies_trasera': data.get('ruta_pies_trasera'),
        'pies': data.get('ruta_pisada') # 'pies' es la clave para la plantografía
    }
    notas_adicionales = data.get('notas_plantillas', '')

    ruta_trasera_relativa = rutas_imagenes.get('pies_trasera')
    ruta_trasera_absoluta = os.path.join(current_app.root_path, 'static', ruta_trasera_relativa) if ruta_trasera_relativa else None
    hallazgos_podales, ruta_imagen_anotada = analizar_coordenadas_podal(ruta_trasera_absoluta)

    informe_texto = generar_informe_podal_unificado(rutas_imagenes, notas_adicionales, hallazgos_podales )

    if ruta_imagen_anotada:
        url_imagen_anotada = url_for('static', filename=ruta_imagen_anotada)
        return jsonify({'informe': informe_texto, 'annotated_image_url': url_imagen_anotada})
    else:
        return jsonify({'informe': informe_texto, 'annotated_image_url': None}) 

@clinical_bp.route('/plan_cuidado/<int:id_plan>/pdf') 
@login_required
def generate_plan_pdf(patient_id, id_plan):
    connection = None
    logo_base64_uri = None
    centro_info_for_pdf = None 
    try:
        # --- Cargar y codificar el logo ---
        logo_path = os.path.join(current_app.static_folder, 'img', 'logo.png')
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                logo_base64_uri = f"data:image/png;base64,{encoded_string}"
        
        connection = connect_to_db()
        if not connection:
            flash('Error de conexión.', 'danger')
            return redirect(url_for('clinical.manage_plan_cuidado', patient_id=patient_id, selected_id=id_plan))

        # --- Obtener información del centro ---
        id_centro_actual_dr = session.get('id_centro_dr')
        if id_centro_actual_dr and id_centro_actual_dr != 0:
            centro_info_for_pdf = get_centro_by_id(connection, id_centro_actual_dr)
        elif session.get('is_admin'):
            centro_info_for_pdf = get_centro_by_id(connection, 1) 
            if not centro_info_for_pdf:
                centro_info_for_pdf = {'nombre': 'Chiropractic Care Center (Admin)', 'direccion': 'N/A', 'cel': 'N/A', 'tel': 'N/A'}
        else:
            centro_info_for_pdf = {'nombre': 'Chiropractic Care Center', 'direccion': 'N/A', 'cel': 'N/A', 'tel': 'N/A'}

        # --- Obtener datos principales ---
        patient_obj = get_patient_by_id(connection, patient_id) 
        plan_obj = get_specific_plan_cuidado(connection, id_plan) 

        if not patient_obj or not plan_obj or plan_obj.get('id_px') != patient_id:
            flash('Datos no encontrados para generar PDF del plan.', 'warning')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        doctor_name = "No especificado"
        if plan_obj.get('id_dr'): 
            doctors = get_all_doctors(connection) 
            found_doctor = next((doc for doc in doctors if doc['id_dr'] == plan_obj['id_dr']), None)
            if found_doctor: doctor_name = found_doctor.get('nombre', doctor_name)

        adicionales_seleccionados_obj = [] 
        adicional_ids_str = plan_obj.get('adicionales_ids', '0,')
        adicional_ids_list = [id_str for id_str in adicional_ids_str.split(',') if id_str.isdigit() and int(id_str) > 0]
        if adicional_ids_list: 
            adicionales_seleccionados_obj = get_productos_by_ids(connection, adicional_ids_list)

        costo_qp = 0.0; costo_tf = 0.0
        productos_base = get_productos_servicios_by_type(connection, tipo_adicional=0)
        for prod in productos_base:
            if 'ajuste quiropractico' in prod.get('nombre', '').lower(): costo_qp = float(prod.get('costo', 0.0))
            elif 'terapia fisica' in prod.get('nombre', '').lower(): costo_tf = float(prod.get('costo', 0.0))

        # ---> CREAR UN ÚNICO DICCIONARIO 'data_for_pdf' <---
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
        # ----------------------------------------------------


        # Renderizar la plantilla HTML pasando el diccionario 'data_for_pdf' como 'data'
        html_content = render_template('plan_cuidado_pdf.html', data=data_for_pdf) 

        # Convertir HTML a PDF
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(
            html_content.encode('utf-8'),
            dest=pdf_buffer,
            encoding='utf-8'
        )

        if pisa_status.err:
            print(f"Error al generar PDF de Plan de Cuidado #{id_plan} con pisa: {pisa_status.err}")
            flash('Ocurrió un error al generar el archivo PDF del plan.', 'danger')
            return redirect(url_for('clinical.manage_plan_cuidado', patient_id=patient_id, selected_id=id_plan))

        pdf_buffer.seek(0)
        response = Response(pdf_buffer, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'inline; filename=plan_cuidado_px{patient_id}_plan{id_plan}.pdf'
        return response

    except Exception as e:
        print(f"Error en generate_plan_pdf (PID {patient_id}, PlanID {id_plan}): {e}")
        flash('Error inesperado al generar el PDF del plan.', 'danger')
        if connection and connection.is_connected() and not getattr(connection, 'autocommit', True): 
            try: connection.rollback()
            except Error: pass
        # Redirigir a una página segura, por ejemplo, el detalle del plan de cuidado o del paciente
        safe_redirect_url = url_for('clinical.manage_plan_cuidado', patient_id=patient_id, selected_id=id_plan) if id_plan else url_for('patient.patient_detail', patient_id=patient_id)
        return redirect(safe_redirect_url)
    finally:
        if connection and connection.is_connected(): 
            connection.close()
            print("INFO generate_plan_pdf: Conexión a BD cerrada en finally.")

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
        # get_postura_summary devuelve una lista de strings de fecha ya ordenadas (DESC por defecto)
        available_postura_dates = get_postura_summary(connection, patient_id)

        if not available_postura_dates:
            return jsonify({
                'exists': False,
                'message': 'No se encontraron datos de pruebas/postura para este paciente.',
                'redirect_url': url_for('patient.patient_detail', patient_id=patient_id)
            })
        
        
        return jsonify({
            'exists': True,
            'available_dates': available_postura_dates, # Lista de fechas disponibles (ej. ['06/05/2025', '01/04/2025'])
            'pdf_url_base': url_for('clinical.generate_plantillas_pdf', patient_id=patient_id) # URL base para generar el PDF
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
    """Genera el PDF para un recibo específico."""
    connection = None
    logo_base64_uri = None
    try:
        logo_path = os.path.join(current_app.static_folder, 'img', 'logo.png')
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                logo_base64_uri = f"data:image/png;base64,{encoded_string}"
                print("INFO generate_recibo_pdf: Logo cargado y codificado.")
        else:
            print("WARN generate_recibo_pdf: Archivo de logo no encontrado en", logo_path)

        connection = connect_to_db()
        if not connection:
            flash('Error conectando a la base de datos.', 'danger')
            # Redirigir a la vista de lista/nuevo recibo si falla la conexión
            return redirect(url_for('clinical.manage_recibos', patient_id=patient_id))

        # Obtener datos del paciente
        patient = get_patient_by_id(connection, patient_id)
        if not patient:
            flash('Paciente no encontrado.', 'warning')
            if connection and connection.is_connected(): connection.close()
            return redirect(url_for('main'))

        receipt_data = get_specific_recibo(connection, id_recibo)

        # Verificar que el recibo exista y pertenezca al paciente correcto
        if not receipt_data or receipt_data.get('id_px') != patient_id:
            flash(f'Recibo #{id_recibo} no encontrado o no pertenece a este paciente.', 'warning')
            if connection and connection.is_connected(): connection.close()
            return redirect(url_for('clinical.manage_recibos', patient_id=patient_id))

        # ---> OBTENER INFORMACIÓN DEL CENTRO DEL DOCTOR LOGUEADO <---
        id_centro_actual_dr = session.get('id_centro_dr')
        if id_centro_actual_dr and id_centro_actual_dr != 0: # Si es un ID de centro válido (no admin)
            centro_info_for_pdf = get_centro_by_id(connection, id_centro_actual_dr)
        elif session.get('is_admin'): # Si es admin (centro 0)
            # El admin podría generar el PDF con datos de un centro por defecto (ej. ID 1)
            # o con datos genéricos si no hay un "centro principal"
            # Por ahora, intentamos cargar el centro con ID 1 como default para admin
            centro_info_for_pdf = get_centro_by_id(connection, 1) 
            if not centro_info_for_pdf: # Si el centro 1 no existe, usar datos genéricos
                centro_info_for_pdf = {'nombre': 'Chiropractic Care Center (Admin)', 'direccion': 'N/A', 'cel': 'N/A', 'tel': 'N/A'}
        else: # No se pudo determinar el centro
            centro_info_for_pdf = {'nombre': 'Chiropractic Care Center', 'direccion': 'N/A', 'cel': 'N/A', 'tel': 'N/A'}
        # ---------------------------------------------------------
        
        # Añadir los datos que necesita la plantilla PDF directamente al diccionario 'receipt_data'
        # que se pasará como 'data' a la plantilla.
        receipt_data['patient_nombre_completo'] = f"{patient.get('nombre', '')} {patient.get('apellidop', '')} {patient.get('apellidom', '')}".strip()
        receipt_data['logo_base64_uri'] = logo_base64_uri
        receipt_data['current_year_for_pdf'] = datetime.now().year
        receipt_data['centro_info'] = centro_info_for_pdf 


        # Renderizar la plantilla HTML específica para el PDF del recibo
        html_content = render_template('recibo_pdf_template.html', data=receipt_data)

        # Convertir HTML a PDF
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(
            html_content.encode('utf-8'), # Fuente HTML
            dest=pdf_buffer,                # Salida al buffer
            encoding='utf-8'                # Codificación
        )

        if pisa_status.err:
            print(f"Error al generar PDF de recibo #{id_recibo} con pisa: {pisa_status.err}")
            flash('Ocurrió un error al generar el PDF del recibo.', 'danger')
            if connection and connection.is_connected(): connection.close()
            return redirect(url_for('clinical.manage_recibos', patient_id=patient_id, selected_id=id_recibo)) # Volver al form del recibo

        pdf_buffer.seek(0)
        response = Response(pdf_buffer, mimetype='application/pdf')
        # 'inline' intenta mostrarlo en el navegador, 'attachment' fuerza la descarga
        response.headers['Content-Disposition'] = f'inline; filename=recibo_px{patient_id}_rec{id_recibo}.pdf'
        return response

    except Exception as e:
        print(f"Error en generate_recibo_pdf (PID {patient_id}, ReciboID {id_recibo}): {e}")
        flash('Error inesperado al generar PDF del recibo.', 'danger')
        # Si la conexión está abierta y ocurre un error no manejado antes, cerrarla.
        if connection and connection.is_connected():
            connection.close()
        # Redirigir a una página segura
        safe_redirect_url = url_for('patient.patient_detail', patient_id=patient_id) if 'patient_id' in locals() and patient_id is not None else url_for('main')
        return redirect(safe_redirect_url)

    finally:
        # Asegurar que la conexión se cierre si se abrió en el try principal
        if connection and connection.is_connected() and not connection.is_closed():
            connection.close()
            print("INFO generate_recibo_pdf: Conexión a BD cerrada en finally.")

@clinical_bp.route('/reporte_integral_pdf')
@login_required
def generar_reporte_integral_pdf(patient_id):
    connection = None
    try:
        logo_base64_uri = None
        logo_path = os.path.join(current_app.static_folder, 'img', 'logo.png')
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                logo_base64_uri = f"data:image/png;base64,{encoded_string}"

        connection = connect_to_db()
        if not connection:
            flash("Error de conexión.", "danger")
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        # 1. Recopilar todos los datos de la base de datos
        patient_data = get_patient_by_id(connection, patient_id)
        anamnesis_data = get_latest_anamnesis(connection, patient_id)
        pruebas_data = get_latest_postura_overall(connection, patient_id)

        if not patient_data or not anamnesis_data or not pruebas_data:
            flash("Faltan datos esenciales (anamnesis o pruebas) para generar el informe.", "warning")
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        # 1.1 Obtener la ruta completa de la imagen frontal
        ruta_frontal_relativa = pruebas_data.get('frente')
        ruta_frontal_absoluta = os.path.join(current_app.root_path, 'static', ruta_frontal_relativa) if ruta_frontal_relativa else None

        # 2.1 Llamar a nuestra nueva función para obtener los datos objetivos
        hallazgos_calculados = analizar_coordenadas_postura(ruta_frontal_absoluta)

        # 2. Generar el informe de texto con la IA
        informe_ia_texto = generar_informe_integral_con_ia(patient_data, anamnesis_data, pruebas_data, hallazgos_calculados )

        # 3. Preparar todos los datos para la plantilla PDF
        edad_paciente = calculate_age(patient_data.get('nacimiento'))
        
        id_dr_sesion = session.get('id_dr')
        nombre_doctor = session.get('nombre_dr', 'No especificado') 
        
        id_centro_sesion = session.get('id_centro_dr')
        centro_info = get_centro_by_id(connection, id_centro_sesion) if id_centro_sesion else None

        print("\n--- DIAGNÓSTICO DEL PIE DE PÁGINA ---")
        print(f"ID del Centro en Sesión: {id_centro_sesion}")
        print(f"Información de la Clínica Obtenida de la BD: {centro_info}")
        print("-------------------------------------\n")

        if not centro_info: # Si no se encuentra info del centro, usar un default
            centro_info = {'nombre': 'Chiropractic Care Center'}

         # 4. Preparar todos los datos para la plantilla PDF 
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
            
            'edad_paciente': edad_paciente,
            'doctor_name': nombre_doctor,
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
        
        # 5. Renderizar el HTML y generar el PDF
        html_content = render_template('reporte_integral_pdf.html', data=data_for_pdf)
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_content.encode('utf-8'), dest=pdf_buffer, encoding='utf-8')

        if pisa_status.err:
            flash('Ocurrió un error al generar el archivo PDF.', 'danger')
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))
        
        pdf_buffer.seek(0)
        response = Response(pdf_buffer, mimetype='application/pdf')
        response.headers['Content-Disposition'] = f'inline; filename=informe_integral_px{patient_id}.pdf'
        return response

    except Exception as e:
        print(f"Error generando informe integral para PID {patient_id}: {e}")
        flash('Error inesperado al generar el informe integral.', 'danger')
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))
    finally:
        if connection and connection.is_connected():
            connection.close()



@clinical_bp.route('/comparador')
@login_required
def comparador_postura(patient_id):
    """
    Muestra la página del comparador de posturas con las fechas disponibles.
    """
    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            flash("Error de conexión a la base de datos.", "danger")
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        patient = get_patient_by_id(connection, patient_id)
        if not patient:
            flash("Paciente no encontrado.", "warning")
            return redirect(url_for('main'))

        # Usamos la función que ya existe para obtener todas las fechas
        # donde se guardaron pruebas de postura.
        available_dates = get_postura_summary(connection, patient_id)
        
        if not available_dates or len(available_dates) < 2:
            flash("Se necesitan al menos dos registros de pruebas de postura para comparar.", "info")
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        # Renderizamos la nueva plantilla que vamos a crear
        return render_template('comparador_postura.html', 
                               patient=patient, 
                               available_dates=available_dates)

    except Exception as e:
        print(f"Error en comparador_postura (PID {patient_id}): {e}")
        flash("Ocurrió un error al cargar el comparador de posturas.", "danger")
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))
    finally:
        if connection and connection.is_connected():
            connection.close()

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



@clinical_bp.route('/reporte_visual_fechado')
@login_required
def reporte_visual_fechado(patient_id):
    """
    Muestra la página del reporte visual con selector de fecha.
    """
    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            flash("Error de conexión.", "danger")
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        patient = get_patient_by_id(connection, patient_id)
        if not patient:
            flash("Paciente no encontrado.", "warning")
            return redirect(url_for('main'))

        # Obtenemos las fechas donde hay registros de postura
        available_dates = get_postura_summary(connection, patient_id)

        if not available_dates:
            flash("No hay registros de pruebas de postura disponibles para este paciente.", "info")
            return redirect(url_for('patient.patient_detail', patient_id=patient_id))

        # Renderizamos la nueva plantilla
        return render_template('reporte_visual_fechado.html',
                               patient=patient,
                               available_dates=available_dates)

    except Exception as e:
        print(f"Error en reporte_visual_fechado (PID {patient_id}): {e}")
        flash("Ocurrió un error al cargar el reporte visual.", "danger")
        return redirect(url_for('patient.patient_detail', patient_id=patient_id))
    finally:
        if connection and connection.is_connected():
            connection.close()




@clinical_bp.route('/api/mark_notes_seen', methods=['POST'])
@login_required
def api_mark_notes_seen(patient_id):
    """
    API endpoint para marcar una lista de notas como vistas.
    """
    data = request.get_json()
    note_ids = data.get('note_ids') # Esperamos una lista de IDs [1, 2, 3]
    
    if not note_ids or not isinstance(note_ids, list):
        return jsonify({'success': False, 'message': 'IDs de nota no proporcionados.'}), 400

    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            return jsonify({'success': False, 'message': 'Error de conexión DB.'}), 500
        
        connection.start_transaction()
        rows_affected = mark_notes_as_seen(connection, note_ids)
        connection.commit()
        
        return jsonify({'success': True, 'message': f'{rows_affected} notas marcadas como vistas.'})

    except Error as e:
        if connection: connection.rollback()
        print(f"Error en API mark_notes_seen: {e}")
        return jsonify({'success': False, 'message': 'Error de base de datos.'}), 500
    except Exception as ex:
        if connection: connection.rollback()
        print(f"Error inesperado en API mark_notes_seen: {ex}")
        return jsonify({'success': False, 'message': 'Error del servidor.'}), 500
    finally:
        if connection: 
            connection.close()

@clinical_bp.route('/api/add_note', methods=['POST'])
@login_required
def api_add_general_note(patient_id):
    """
    API endpoint para añadir una nueva nota general.
    """
    data = request.get_json()
    note_text = data.get('note_text')
    
    if not note_text or not note_text.strip():
        return jsonify({'success': False, 'message': 'El texto de la nota no puede estar vacío.'}), 400

    connection = None
    try:
        connection = connect_to_db()
        if not connection:
            return jsonify({'success': False, 'message': 'Error de conexión DB.'}), 500
        
        connection.start_transaction()
        new_note_id = add_general_note(connection, patient_id, note_text.strip())
        connection.commit()
        
        return jsonify({'success': True, 'message': f'Nota #{new_note_id} guardada.'})

    except Error as e:
        if connection: connection.rollback()
        print(f"Error en API add_general_note: {e}")
        return jsonify({'success': False, 'message': 'Error de base de datos al guardar la nota.'}), 500
    except Exception as ex:
        if connection: connection.rollback()
        print(f"Error inesperado en API add_general_note: {ex}")
        return jsonify({'success': False, 'message': 'Error del servidor al guardar la nota.'}), 500
    finally:
        if connection: 
            connection.close()

def get_first_postura_on_or_after_date(connection, patient_id, target_date_str):
    cursor = None
    try:
        target_date_sql = parse_date(target_date_str)
        cursor = connection.cursor(dictionary=True, buffered=True)
        # Buscar el primero en o después
        query = "SELECT * FROM postura WHERE id_px = %s AND fecha >= %s ORDER BY fecha ASC, id_postura ASC LIMIT 1"
        cursor.execute(query, (patient_id, target_date_sql))
        result = cursor.fetchone()
        
        if not result:
            # Fallback: buscar el más reciente antes
            query_fallback = "SELECT * FROM postura WHERE id_px = %s AND fecha < %s ORDER BY fecha DESC, id_postura DESC LIMIT 1"
            cursor.execute(query_fallback, (patient_id, target_date_sql))
            result = cursor.fetchone()
            
        return result
    except Error: return None
    finally: 
        if cursor: cursor.close()

def update_postura_ortho_notes(connection, id_postura, notas):
    cursor = None
    try:
        cursor = connection.cursor()
        query = "UPDATE postura SET notas_pruebas_ortoneuro = %s WHERE id_postura = %s"
        cursor.execute(query, (notas, id_postura))
        return True
    except Error as e:
        print(f"Error update_postura_ortho_notes: {e}")
        return False
    finally: 
        if cursor: cursor.close()

def get_latest_postura_on_or_before_date(connection, patient_id, target_date_str):
    cursor = None
    try:
        target_date_sql = parse_date(target_date_str)
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = "SELECT * FROM postura WHERE id_px = %s AND fecha <= %s ORDER BY fecha DESC, id_postura DESC LIMIT 1"
        cursor.execute(query, (patient_id, target_date_sql))
        data = cursor.fetchone()
        if data:
            for k in ['pie_cm', 'zapato_cm', 'fuerza_izq', 'fuerza_der']:
                if data.get(k): data[k] = float(data[k])
        return data
    except Error: return None
    finally: 
        if cursor: cursor.close()

def get_latest_antecedente_on_or_before_date(connection, patient_id, target_date_str):
    cursor = None
    try:
        target_date_obj = datetime.strptime(target_date_str, '%d/%m/%Y')
        cursor = connection.cursor(dictionary=True, buffered=True)
        query = "SELECT * FROM antecedentes WHERE id_px = %s AND fecha <= %s ORDER BY fecha DESC, id_antecedente DESC LIMIT 1"
        cursor.execute(query, (patient_id, target_date_obj.strftime('%Y-%m-%d')))
        data = cursor.fetchone()
        if data and data.get('calzado'): data['calzado'] = float(data['calzado'])
        return data
    except (ValueError, Error): return None
    finally: 
        if cursor: cursor.close()
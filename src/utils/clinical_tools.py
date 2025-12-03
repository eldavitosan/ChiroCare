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
from datetime import datetime, timedelta, date
import uuid
import base64
import json
from PIL import Image
from flask import (
    jsonify, url_for,  current_app
)
from io import BytesIO
from xhtml2pdf import pisa
import cv2
import mediapipe as mp
from werkzeug.utils import secure_filename
import traceback


from utils.date_manager import to_frontend_str, to_db_str, calculate_age, parse_date

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


# --- Fin IA Helper Functions ---
            


from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, SubmitField, BooleanField, DateField, EmailField, IntegerField,
                     SelectField, RadioField, TextAreaField, HiddenField, SelectMultipleField)
from wtforms.fields import DecimalField, DateField
from wtforms.validators import DataRequired, Length, Email, EqualTo, Optional, NumberRange
from datetime import datetime

class LoginForm(FlaskForm):
    usuario = StringField('Usuario', 
                          validators=[DataRequired(message="El usuario es obligatorio."), 
                                      Length(min=3, max=50, message="El usuario debe tener entre 3 y 50 caracteres.")])
    contraseña = PasswordField('Contraseña', 
                               validators=[DataRequired(message="La contraseña es obligatoria.")])
    submit = SubmitField('Entrar')

class RegisterForm(FlaskForm):
    nombre = StringField('Nombre Completo:', 
                         validators=[DataRequired(message="El nombre es obligatorio.")])
    usuario = StringField('Nombre de Usuario (para login):', 
                          validators=[DataRequired(message="El usuario es obligatorio."),
                                      Length(min=3, max=50)])
    contraseña = PasswordField('Contraseña:', 
                               validators=[DataRequired(message="La contraseña es obligatoria."), 
                                           Length(min=6, message="La contraseña debe tener al menos 6 caracteres.")])
    confirm_password = PasswordField('Confirmar Contraseña:', 
                                     validators=[DataRequired(message="Confirme la contraseña."), 
                                                 EqualTo('contraseña', message='Las contraseñas no coinciden.')])
    centro = SelectField('Asignar a Clínica:', coerce=int, validators=[Optional()])
    es_admin_nuevo_dr = BooleanField('¿Asignar Rol de Administrador?')
    submit = SubmitField('Registrar Doctor')

class PatientForm(FlaskForm):
    # Campos de Información General
    comoentero = StringField('¿Cómo se enteró?', validators=[Optional()])
    nombre = StringField('Nombre(s):', validators=[DataRequired(message="El nombre es obligatorio.")])
    apellidop = StringField('Apellido Paterno:', validators=[DataRequired(message="El apellido paterno es obligatorio.")])
    apellidom = StringField('Apellido Materno:', validators=[Optional()])
    
    # Usamos DateField para un mejor control de la fecha
    nacimiento = DateField('Fecha nacimiento:', validators=[Optional()])
    
    # Campos de Contacto y Personales
    direccion = StringField('Dirección:', validators=[Optional()])
    estadocivil = StringField('Estado civil:', validators=[Optional()])
    ocupacion = StringField('Ocupación:', validators=[Optional()])
    hijos = StringField('Hijos (Cantidad y Edades):', validators=[Optional()])
    
    # TelField es semántico, pero StringField también funciona. 
    # Usamos StringField con DataRequired para 'cel' como en tu lógica.
    telcasa = StringField('Tel. Casa:', validators=[Optional()])
    cel = StringField('Tel. Celular:', validators=[DataRequired(message="El celular es obligatorio.")])
    correo = EmailField('Correo electrónico:', validators=[Optional(), Email(message="Correo inválido.")])
    
    # Campos de Contacto de Emergencia
    contacto = StringField('Nombre Contacto:', validators=[Optional()])
    parentesco = StringField('Parentesco:', validators=[Optional()])
    emergencia = StringField('Tel. Emergencia:', validators=[Optional()])
    
    submit = SubmitField('Guardar Paciente')

class EditDoctorForm(FlaskForm):
    nombre = StringField('Nombre Completo:', 
                         validators=[DataRequired(message="El nombre es obligatorio.")])
    usuario = StringField('Nombre de Usuario (para login):', 
                          validators=[DataRequired(message="El usuario es obligatorio."),
                                      Length(min=3, max=50)])
    
    # Campo para asignar la clínica
    centro = SelectField('Asignar a Clínica:', coerce=int, validators=[Optional()])

    # Checkbox para rol de admin
    es_admin_nuevo_dr = BooleanField('¿Asignar Rol de Administrador?')
    
    submit = SubmitField('Actualizar Doctor')

class ChangePasswordForm(FlaskForm):
    nueva_contraseña = PasswordField('Nueva Contraseña:', 
                                     validators=[DataRequired(message="La contraseña es obligatoria."), 
                                                 Length(min=6, message="La contraseña debe tener al menos 6 caracteres.")])
    confirmar_contraseña = PasswordField('Confirmar Contraseña:', 
                                         validators=[DataRequired(message="Confirme la contraseña."), 
                                                     # Este validador comprueba que el valor sea igual
                                                     # al del campo 'nueva_contraseña'
                                                     EqualTo('nueva_contraseña', message='Las contraseñas no coinciden.')])
    submit = SubmitField('Cambiar Contraseña')

class ClinicaForm(FlaskForm):
    nombre = StringField('Nombre de la Clínica:', 
                         validators=[DataRequired(message="El nombre es obligatorio."),
                                     Length(min=3, max=100)])
    direccion = StringField('Dirección:', 
                            validators=[Optional(), Length(max=255)])
    tel = StringField('Teléfono:', 
                           validators=[Optional(), Length(max=20)])
    cel = StringField('Celular:', 
                           validators=[Optional(), Length(max=20)])
    submit = SubmitField('Guardar Clínica')

class ProductoServicioForm(FlaskForm):
    nombre = StringField('Nombre:', 
                         validators=[DataRequired(message="El nombre es obligatorio."),
                                     Length(min=3, max=255)])
    
    # DecimalField es el campo correcto para dinero/precios
    costo = DecimalField('Costo (Opcional):',
                          validators=[Optional(), # El costo puede ser 0 o Nulo
                                      NumberRange(min=0, message="El costo no puede ser negativo.")],
                          places=2,
                          default=0.00) 
    
    venta = DecimalField('Precio de Venta:',
                          validators=[DataRequired(message="El precio de venta es obligatorio."),
                                      NumberRange(min=0, message="El precio no puede ser negativo.")],
                          places=2)
    
    adicional = SelectField('Tipo de Servicio/Producto:',
                            coerce=int, # Convierte el valor del form a entero
                            choices=[
                                (0, 'Consulta / Seguimiento (Principal)'),
                                (1, 'Producto (Inventario)'),
                                (2, 'Terapia Física')
                            ],
                            validators=[DataRequired(message="Debe seleccionar un tipo.")])

    submit = SubmitField('Guardar')

# --- FORMULARIOS BASE PARA REPORTES ---
class ReporteFechasForm(FlaskForm):
    """Un formulario base que solo pide un rango de fechas."""
    # Usamos DateField, que valida el formato YYYY-MM-DD automáticamente
    fecha_inicio = DateField('Fecha Inicio', validators=[DataRequired(message="Fecha de inicio requerida.")])
    fecha_fin = DateField('Fecha Fin', validators=[DataRequired(message="Fecha de fin requerida.")])

class ReporteFechasDoctorForm(ReporteFechasForm):
    """Un formulario base que pide fechas Y un doctor."""
    # El 'coerce=int' convierte el valor del select a número
    # El 'default=0' es para la opción "Todos los Doctores"
    doctor_id = SelectField('Doctor:', coerce=int, default=0, validators=[Optional()])

# --- FORMULARIOS ESPECÍFICOS PARA EL DASHBOARD ---

# 1. y 2. Para "Ingresos por periodo" E "Ingreso por doctor"
class FormIngresos(ReporteFechasDoctorForm):
    submit_ingresos = SubmitField('Generar Reporte')

# 3. y 4. Para "Utilidad por periodo" Y "Utilidad por doctor"
class FormUtilidad(ReporteFechasDoctorForm):
    submit_utilidad = SubmitField('Generar Reporte')

# 5. Para "Pacientes nuevos por periodo" (total o por doctor)
class FormNuevosPacientes(ReporteFechasDoctorForm):
    submit_nuevos_pac = SubmitField('Generar Reporte')

# 6. Para "Pacientes mas frecuentes (top N)"
class FormPacientesFrecuentes(ReporteFechasForm):
    top_n = IntegerField('Top N:', 
                         default=10, 
                         validators=[DataRequired(), NumberRange(min=1, max=100)])
    submit_pac_frec = SubmitField('Generar Reporte')
    
# 7. Para "Consultas (seguimientos) por doctor"
class FormSeguimientos(ReporteFechasDoctorForm):
    submit_seguimientos = SubmitField('Generar Reporte')

# 8. Para "Uso de planes de cuidado"
class FormUsoPlanes(ReporteFechasForm):
    submit_uso_planes = SubmitField('Generar Reporte')

class AntecedentesForm(FlaskForm):
    # Campos de texto y numéricos
    peso = IntegerField('Peso:', validators=[Optional(), NumberRange(min=0)])
    altura = StringField('Altura:', validators=[Optional()])
    calzado = DecimalField('#Calzado:', validators=[Optional(), NumberRange(min=0)], places=1)
    presion_alta = StringField('Presión Alta:', validators=[Optional()])
    trigliceridos = StringField('Triglicéridos/ Colesterol:', validators=[Optional()])
    diabetes = StringField('Diabetes:', validators=[Optional()])
    agua = StringField('Consumo de Agua:', validators=[Optional()])
    notas = TextAreaField('Notas Adicionales:', validators=[Optional()])

    # --- Campos de Opciones Múltiples ---
    # NOTA: Las 'choices' (opciones) de estos campos
    # se asignarán dinámicamente en la ruta (blueprint)
    
    # Este campo (`cond_gen`) se mapeará a `condiciones_generales`
    # Usamos coerce=str para que guarde los IDs '1', '2', etc.
    cond_gen = SelectMultipleField('Condiciones Generales:', 
                                   coerce=str, validators=[Optional()])

    # --- Campos de Radio (Condición Diagnosticada) ---
    # Estos se mapean a los campos 'diag_...'
    diag_dislocacion = RadioField('Dislocación:', 
                                  choices=[('1', 'Pasado'), ('2', 'Actual')], 
                                  validators=[Optional()])
    diag_fractura = RadioField('Fractura:', 
                               choices=[('3', 'Pasado'), ('4', 'Actual')], 
                               validators=[Optional()])
    diag_tumor = RadioField('Tumor:', 
                            choices=[('5', 'Pasado'), ('6', 'Actual')], 
                            validators=[Optional()])
    diag_cancer = RadioField('Cáncer:', 
                             choices=[('7', 'Pasado'), ('8', 'Actual')], 
                             validators=[Optional()])
    diag_embarazo = RadioField('Embarazo:', 
                               choices=[('9', 'Pasado'), ('10', 'Actual')], 
                               validators=[Optional()])
    diag_osteo = RadioField('Osteoartritis:', 
                            choices=[('11', 'Pasado'), ('12', 'Actual')], 
                            validators=[Optional()])
    diag_implante = RadioField('Implante Metálico:', 
                               choices=[('13', 'Pasado'), ('14', 'Actual')], 
                               validators=[Optional()])
    diag_ataque = RadioField('Ataque Cardiaco:', 
                             choices=[('15', 'Pasado'), ('16', 'Actual')], 
                             validators=[Optional()])
    diag_epilepsia = RadioField('Epilepsia:', 
                                choices=[('17', 'Pasado'), ('18', 'Actual')], 
                                validators=[Optional()])

    submit = SubmitField('Guardar Antecedentes')

class AnamnesisForm(FlaskForm):
    condicion1 = StringField('Condición Principal #1', validators=[Optional()])
    calif1 = IntegerField('Severidad #1', validators=[Optional(), NumberRange(min=0, max=10)])
    
    condicion2 = StringField('Condición Principal #2', validators=[Optional()])
    calif2 = IntegerField('Severidad #2', validators=[Optional(), NumberRange(min=0, max=10)])

    condicion3 = StringField('Condición Principal #3', validators=[Optional()])
    calif3 = IntegerField('Severidad #3', validators=[Optional(), NumberRange(min=0, max=10)])

    como_comenzo = RadioField('¿Cómo comenzó?', 
                            choices=[
                                (1, 'Gradual'),
                                (2, 'Súbito'),
                                (3, 'Desconocido')
                            ], 
                            coerce=int,
                            validators=[Optional()])
    
    primera_vez = StringField('¿Cuándo fue la primera vez?', validators=[Optional()])
    alivia = StringField('¿Qué alivia sus síntomas?', validators=[Optional()])
    empeora = StringField('¿Qué empeora sus síntomas?', validators=[Optional()])
    como_ocurrio = StringField('¿Cómo ocurrió su lesión?', validators=[Optional()])
    actividades_afectadas = StringField('¿Actividades afectadas?', validators=[Optional()])

    # Para los checkboxes, usamos SelectMultipleField.
    # Las 'choices' se deben poblar desde tu MAPA en la ruta.
    dolor_intenso_chk = SelectMultipleField('¿Cuándo es más intenso el dolor?', 
                                            coerce=str, 
                                            validators=[Optional()])
    
    tipo_dolor_chk = SelectMultipleField('Tipo de Dolor:', 
                                         coerce=str, 
                                         validators=[Optional()])

    # Campo oculto para almacenar los puntos del diagrama
    diagrama_puntos = HiddenField('Diagrama Puntos', default='0,')
    
    # La historia es solo de lectura en el form, la generas en el backend.
    historia = TextAreaField('Historia (Autogenerada)', 
                             render_kw={'readonly': True, 
                                        'style': 'background-color: #f8f9fa; font-style: italic;'})

    submit = SubmitField('Guardar Anamnesis')

class SeguimientoForm(FlaskForm):
    # Asociar a plan de cuidado
    id_plan_cuidado_asociado = SelectField('Asociar a Plan de Cuidado', 
                                         coerce=int, 
                                         validators=[Optional()])
    
    # Campo de notas ortopédicas (que actualiza 'postura')
    notas_pruebas_ortoneuro = TextAreaField('Notas de Pruebas Ortopédicas (de hoy)',
                                            validators=[Optional()])

    # Segmentos Vertebrales
    occipital = StringField('Occ', validators=[Optional()])
    atlas = StringField('C1', validators=[Optional()])
    axis = StringField('C2', validators=[Optional()])
    c3 = StringField('C3', validators=[Optional()])
    c4 = StringField('C4', validators=[Optional()])
    c5 = StringField('C5', validators=[Optional()])
    c6 = StringField('C6', validators=[Optional()])
    c7 = StringField('C7', validators=[Optional()])
    t1 = StringField('T1', validators=[Optional()])
    t2 = StringField('T2', validators=[Optional()])
    t3 = StringField('T3', validators=[Optional()])
    t4 = StringField('T4', validators=[Optional()])
    t5 = StringField('T5', validators=[Optional()])
    t6 = StringField('T6', validators=[Optional()])
    t7 = StringField('T7', validators=[Optional()])
    t8 = StringField('T8', validators=[Optional()])
    t9 = StringField('T9', validators=[Optional()])
    t10 = StringField('T10', validators=[Optional()])
    t11 = StringField('T11', validators=[Optional()])
    t12 = StringField('T12', validators=[Optional()])
    l1 = StringField('L1', validators=[Optional()])
    l2 = StringField('L2', validators=[Optional()])
    l3 = StringField('L3', validators=[Optional()])
    l4 = StringField('L4', validators=[Optional()])
    l5 = StringField('L5', validators=[Optional()])
    sacro = StringField('Sacro', validators=[Optional()])
    coxis = StringField('Coxis', validators=[Optional()])
    iliaco_d = StringField('Iliaco D', validators=[Optional()])
    iliaco_i = StringField('Iliaco I', validators=[Optional()])
    pubis = StringField('Pubis', validators=[Optional()])

    # Terapias (Checkboxes)
    # Las 'choices' se deben poblar desde la base de datos en la ruta.
    terapia_chk = SelectMultipleField('Terapia Física Aplicada', 
                                      coerce=str, 
                                      validators=[Optional()])
    
    # Notas de la visita
    notas = TextAreaField('Notas de la Visita', validators=[Optional()])
    
    submit = SubmitField('Guardar Seguimiento')

# --- Nuevos Forms para Cobranza y Caja ---

class FormCuentasPorCobrar(FlaskForm):
    """Filtra deudas por doctor (opcional)."""
    doctor_id = SelectField('Filtrar por Doctor:', coerce=int, default=0, validators=[Optional()])
    submit_cxc = SubmitField('Generar Reporte de Deudores')

class FormCorteCaja(ReporteFechasDoctorForm):
    """Hereda fecha_inicio, fecha_fin y doctor_id."""
    submit_caja = SubmitField('Generar Corte de Caja')
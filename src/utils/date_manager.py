from datetime import datetime, date

def to_frontend_str(date_obj):
    """
    Convierte un objeto date/datetime o string YYYY-MM-DD a formato DD/MM/YYYY.
    Si es None o vacío, devuelve cadena vacía.
    """
    if not date_obj:
        return ""
    
    if isinstance(date_obj, str):
        # Intentar parsear si viene como string YYYY-MM-DD
        try:
            date_obj = datetime.strptime(date_obj, '%Y-%m-%d').date()
        except ValueError:
            # Si ya está en DD/MM/YYYY o es otro formato, devolver tal cual o intentar parsear
            # Asumimos que si falla YYYY-MM-DD, podría ser que ya sea el formato deseado o inválido.
            # Para seguridad, intentamos parsear DD/MM/YYYY para validar, si no, devolvemos original.
            try:
                datetime.strptime(date_obj, '%d/%m/%Y')
                return date_obj
            except ValueError:
                return date_obj # Devolver como está si no se reconoce

    if isinstance(date_obj, (date, datetime)):
        return date_obj.strftime('%d/%m/%Y')
    
    return str(date_obj)

def to_db_str(date_str):
    """
    Convierte un string DD/MM/YYYY (o objeto date) a formato YYYY-MM-DD para la BD.
    Si es None o vacío, devuelve None (para que la BD maneje NULL si aplica, o error).
    """
    if not date_str:
        return None
    
    if isinstance(date_str, (date, datetime)):
        return date_str.strftime('%Y-%m-%d')

    if isinstance(date_str, str):
        date_str = date_str.strip()
        if not date_str:
            return None
            
        # Intentar parsear DD/MM/YYYY
        try:
            dt = datetime.strptime(date_str, '%d/%m/%Y')
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            # Si falla, quizás ya viene en YYYY-MM-DD (ej. input type="date" a veces)
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                return date_str
            except ValueError:
                raise ValueError(f"Formato de fecha inválido: {date_str}. Se espera DD/MM/YYYY.")
                
    return str(date_str)

def calculate_age(birth_date):
    """
    Calcula la edad basada en la fecha de nacimiento (date, datetime o string).
    Devuelve int o None si hay error.
    """
    if not birth_date:
        return None
        
    if isinstance(birth_date, str):
        # Intentar detectar formato
        try:
            birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
        except ValueError:
            try:
                birth_date = datetime.strptime(birth_date, '%d/%m/%Y').date()
            except ValueError:
                return None

    if isinstance(birth_date, datetime):
        birth_date = birth_date.date()
        
    today = date.today()
    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    return age

def parse_date(date_input):
    """
    Convierte un string (YYYY-MM-DD o DD/MM/YYYY) o datetime a un objeto date.
    Devuelve None si no se puede convertir.
    """
    if not date_input:
        return None
    
    if isinstance(date_input, date):
        return date_input
    
    if isinstance(date_input, datetime):
        return date_input.date()
        
    if isinstance(date_input, str):
        date_input = date_input.strip()
        # Intentar YYYY-MM-DD
        try:
            return datetime.strptime(date_input, '%Y-%m-%d').date()
        except ValueError:
            pass
            
        # Intentar DD/MM/YYYY
        try:
            return datetime.strptime(date_input, '%d/%m/%Y').date()
        except ValueError:
            pass
            
    return None

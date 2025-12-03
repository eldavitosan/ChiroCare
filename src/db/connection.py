import mysql.connector
from mysql.connector import pooling, Error
import os
from dotenv import load_dotenv
from contextlib import contextmanager

load_dotenv()

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER'),
    'password': os.environ.get('DB_PASSWORD'),
    'database': os.environ.get('DB_NAME'),
    'port': int(os.environ.get('DB_PORT', 3306))
}

if not DB_CONFIG['user'] or not DB_CONFIG['database']:
    raise ValueError("Faltan variables de configuración de la base de datos en .env")

# --- CREAR EL POOL DE CONEXIONES (Variable Global) ---
# Se crea una sola vez cuando se importa este archivo
connection_pool = None

try:
    connection_pool = mysql.connector.pooling.MySQLConnectionPool(
        pool_name="chiro_pool",
        pool_size=10,  # Mantiene hasta 10 conexiones abiertas listas para usar
        pool_reset_session=True,
        **DB_CONFIG
    )
    print("INFO: Pool de conexiones MySQL inicializado correctamente.")
except Error as e:
    print(f"ERROR CRÍTICO: No se pudo crear el pool de conexiones: {e}")

def connect_to_db():
    """
    Obtiene una conexión disponible del pool.
    Si el pool está lleno o agotado, esta función manejará la espera o el error.
    """
    global connection_pool
    if not connection_pool:
        print("ERROR: Intento de conectar pero el pool no está inicializado.")
        return None

    try:
        # Obtiene una conexión del pool en lugar de crear una nueva
        connection = connection_pool.get_connection()
        
        if connection.is_connected():
            return connection
            
    except Error as e:
        print(f"Error al obtener conexión del pool MySQL: {e}")
        return None
    
    return None

@contextmanager
def get_db_cursor(commit=False):
    """
    Maneja automáticamente la apertura y cierre de conexiones del pool.
    Uso:
    with get_db_cursor() as (conn, cursor):
        cursor.execute("SELECT ...")
    """
    connection = connect_to_db()
    cursor = None
    try:
        if connection:
            cursor = connection.cursor(dictionary=True)
            yield connection, cursor
            if commit:
                connection.commit()
        else:
            # Si falla la conexión, entregamos None para manejarlo en la ruta
            yield None, None
    except Exception as e:
        if connection and commit:
            connection.rollback()
        raise e
    finally:
        # ESTO ES LO IMPORTANTE: Cierra todo automáticamente
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close() # Devuelve la conexión al pool
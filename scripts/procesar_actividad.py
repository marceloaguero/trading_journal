
import pandas as pd
import yaml
import os
import uuid
from datetime import datetime, timedelta
from collections import defaultdict
from utils import parse_symbol_improved, calcular_dte_pata  # Importar las funciones de utils

def parse_symbol(symbol):
    """
    Parsea el symbol de Tastytrade para extraer detalles, incluyendo opciones sobre futuros.

    Args:
        symbol (str): El símbolo de la opción.

    Returns:
        dict: Un diccionario con el subyacente, vencimiento, tipo y strike.
              Devuelve None si no se puede parsear el símbolo.
    """
    try:
        parts = symbol.split()
        if len(parts) > 1:  # Verificar si hay al menos dos partes
            subyacente = parts[0].split('/')[1] if '/' in parts[0] else parts[0]
            vencimiento_str = parts[1][:6] if len(parts[1]) >= 6 else ""  # Verificar longitud antes de acceder
            vencimiento = datetime.strptime(vencimiento_str, '%y%m%d').strftime('%Y-%m-%d') if vencimiento_str else None
            tipo = "PUT" if "P" in symbol else "CALL"
            # Extraer el strike de la cadena parts[1]
            strike_part = parts[1][1:]
            if 'P' in strike_part:
                strike_str = strike_part.split('P')[1]
            elif 'C' in strike_part:
                strike_str = strike_part.split('C')[1]
            else:
                strike_str = strike_part
            strike = float(strike_str)
            return {'subyacente': subyacente.strip(), 'vencimiento': vencimiento, 'tipo': tipo, 'strike': strike}
        else:
            return None  # No se pudo parsear el símbolo
    except (ValueError, IndexError) as e:
        print(f"Error al parsear el símbolo '{symbol}': {e}")
        return None

def calcular_dte(vencimiento_str):
    """Calcula los días hasta el vencimiento."""
    vencimiento = datetime.strptime(vencimiento_str, '%Y-%m-%d')
    hoy = datetime.now().date()  # Obtener solo la fecha actual
    return (vencimiento.date() - hoy).days

def procesar_archivo_actividad(archivo_csv, carpeta_posiciones="data/yaml/posiciones_activas"):
    """
    Procesa un archivo CSV de actividad de Tastytrade y crea archivos YAML de posiciones.

    Args:
        archivo_csv (str): La ruta al archivo CSV de actividad.
        carpeta_posiciones (str, optional): La carpeta donde se guardarán los archivos YAML.
                                          Defaults to "data/yaml/posiciones_activas".
    """

    try:
        df = pd.read_csv(archivo_csv)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{archivo_csv}'")
        return

    for index, row in df.iterrows():
        if row['Sub Type'] == 'Sell to Open' or row['Sub Type'] == 'Buy to Open':
            crear_archivo_yaml_posicion(df, index, carpeta_posiciones)  # Pasa el DataFrame y el índice

def crear_archivo_yaml_posicion(df, index, carpeta_posiciones):
    """
    Crea un archivo YAML para una nueva posición basada en una fila del DataFrame.

    Args:
        df (pd.DataFrame): El DataFrame que contiene los datos de actividad.
        index (int): El índice de la fila que representa la transacción de apertura.
        carpeta_posiciones (str): La carpeta donde se guardará el archivo YAML.
    """

    row = df.iloc[index]

    # 1. Extraer la información relevante de la fila
    fecha_inicio_str = row['Date'].split('T')[0]
    fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').strftime('%Y%m%d')
    subyacente = row['Root Symbol']
    estrategia = "NakedPut" if "PUT" in row['Description'] and "CALL" not in row['Description'] else "Unknown"  # Simple lógica
    symbol = row['Symbol']
    opcion_details = parse_symbol(symbol)

    if opcion_details is None:
        print(f"Advertencia: No se pudo procesar el símbolo '{symbol}', omitiendo la fila.")
        return

    # 2. Crear el nombre del archivo YAML
    nombre_archivo = f"{subyacente}_{fecha_inicio}_{estrategia}.yaml"
    ruta_archivo = os.path.join(carpeta_posiciones, nombre_archivo)

    # 3. Recopilar datos de todas las patas de la estrategia (si hay más de una)
    patas = []
    total_credito_debito = 0.0

    # Función para encontrar patas relacionadas (esto es un placeholder y debe mejorarse)
    patas_indices = buscar_patas_relacionadas(df, index)
    for pata_index in patas_indices:
        pata_row = df.iloc[pata_index]
        pata_symbol = pata_row['Symbol']
        pata_opcion_details = parse_symbol(pata_symbol)
        if pata_opcion_details:
            patas.append({
                'tipo': pata_opcion_details['tipo'],
                'strike': pata_opcion_details['strike'],
                'vencimiento': pata_opcion_details['vencimiento'],
                'cantidad': pata_row['Quantity'],
                'precio_apertura': pata_row['Average Price'],
                'precio_actual': pata_row['Average Price'],
                'fecha_cierre': None,
                'precio_cierre': None,
            })
            total_credito_debito += pata_row['Total']

    # 4. Crear el diccionario con los datos de la posición
    posicion_data = {
        'id': str(uuid.uuid4()),
        'fecha_inicio': fecha_inicio,
        'subyacente': subyacente,
        'estrategia': estrategia,
        'cantidad_rolls': 0,
        'credito_debito_inicial': total_credito_debito,
        'credito_debito_actual': total_credito_debito,
        'patas': patas,
        'beta_delta_inicial': None,  # Necesitamos el archivo de posiciones para esto
        'delta_inicial': None,
        'theta_inicial': None,
        'vega_inicial': None,
        'ivr_inicial': None,
        'pop_inicial': None,
        'log_diario': {
            fecha_inicio: {
                'credito_debito': total_credito_debito,
                'mark_precio_spread': None,  # Mejorar: calcular el precio del spread
                'dte_cercano': calcular_dte(min(pata['vencimiento'] for pata in patas)),  # DTE del vencimiento más cercano
                'beta_delta': None,
                'delta': None,
                'theta': None,
                'ivr_promedio': None,
                'pop_estimado': None,
            }
        },
        'fecha_cierre': None,
        'precio_cierre': None,
        'ganancia_perdida_neta': None,
        'duracion_dias': None,
    }

    # 5. Guardar los datos en un archivo YAML
    with open(ruta_archivo, 'w') as archivo_yaml:
        yaml.dump(posicion_data, archivo_yaml, default_flow_style=False)

    print(f"Archivo YAML creado: {ruta_archivo}")

def buscar_patas_relacionadas(df, index, umbral_tiempo_segundos=5):
    """
    Encuentra las filas del DataFrame que pertenecen al mismo trade,
    priorizando la cercanía en el tiempo y el símbolo raíz.
    Permite la intervención manual en caso de ambigüedad.

    Args:
        df (pd.DataFrame): El DataFrame que contiene los datos de actividad.
        index (int): El índice de la fila que representa la transacción de apertura.
        umbral_tiempo_segundos (int, optional): El umbral de tiempo en segundos para considerar
                                              transacciones como parte del mismo trade.
                                              Defaults to 5.

    Returns:
        list: Una lista de los índices de las filas que pertenecen al mismo trade.
    """

    row = df.iloc[index]
    fecha_hora_str = row['Date']
    fecha_hora_dt = datetime.fromisoformat(fecha_hora_str)
    root_symbol = row['Root Symbol']
    patas_indices = [index]
    posibles_patas = []

    for i in range(len(df)):
        if i != index:
            otra_row = df.iloc[i]
            otra_root_symbol = otra_row['Root Symbol']
            otra_fecha_hora_str = otra_row['Date']
            otra_fecha_hora_dt = datetime.fromisoformat(otra_fecha_hora_str)
            diferencia_tiempo = abs((fecha_hora_dt - otra_fecha_hora_dt).total_seconds())

            if otra_root_symbol == root_symbol and diferencia_tiempo <= umbral_tiempo_segundos:
                posibles_patas.append(i)

    # Si no hay patas posibles, devolver solo la fila actual
    if not posibles_patas:
        return [index]

    # Preguntar al usuario si hay ambigüedad
    if len(posibles_patas) > 0:
        print(f"\nPosibles patas relacionadas para '{root_symbol}' el {fecha_hora_str}:")
        for i in patas_indices:
            print(f"- {df.iloc[i]['Date']} - {df.iloc[i]['Description']}")
        for i in posibles_patas:
            print(f"- {df.iloc[i]['Date']} - {df.iloc[i]['Description']}")

        confirmacion = input("¿Son estas transacciones parte del mismo trade? (s/n): ")
        if confirmacion.lower() != 's':
            return [index]
        else:
            return patas_indices + posibles_patas

    return patas_indices

# Esta función ya está definida en utils.py (no es necesario duplicarla)
# def parse_symbol(symbol):
#     """
#     Parsea el symbol de Tastytrade para extraer detalles, incluyendo opciones sobre futuros.
#
#     Args:
#         symbol (str): El símbolo de la opción.
#
#     Returns:
#         dict: Un diccionario con el subyacente, vencimiento, tipo y strike.
#               Devuelve None si no se puede parsear el símbolo.
#     """
#     try:
#         parts = symbol.split()
#         subyacente = parts[0].split('/')[1] if '/' in parts[0] else parts[0]  # Extraer subyacente de futuros
#         vencimiento_str = parts[1][:6]  # Asume que los primeros 6 caracteres después del símbolo son la fecha
#         vencimiento = datetime.strptime(vencimiento_str, '%y%m%d').strftime('%Y-%m-%d')
#         tipo = "PUT" if "P" in symbol else "CALL"
#         strike_str = parts[1][1:]  # Asume que el strike está después de la fecha
#         strike = float(strike_str.split('P')[1].split('C')[1]) if 'P' in strike_str or 'C' in strike_str else float(strike_str)
#         return {'subyacente': subyacente.strip(), 'vencimiento': vencimiento, 'tipo': tipo, 'strike': strike}
#     except (ValueError, IndexError) as e:
#         print(f"Error al parsear el símbolo '{symbol}': {e}")
#         return None

# Esta función ya está definida en utils.py (no es necesario duplicarla)
# def calcular_dte(vencimiento_str):
#     """Calcula los días hasta el vencimiento."""
#     vencimiento = datetime.strptime(vencimiento_str, '%Y-%m-%d')
#     hoy = datetime.now().date()  # Obtener solo la fecha actual
#     return (vencimiento.date() - hoy).days

if __name__ == "__main__":
    archivo_csv = "data/csv/actividad/tastytrade_transactions_history_x5WW34822_241120_to_241120.csv"  # Reemplaza con tu archivo
    procesar_archivo_actividad(archivo_csv)

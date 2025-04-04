import pandas as pd
import yaml
import os
import uuid
from datetime import datetime, timedelta
from collections import defaultdict
import re  # Importar la biblioteca de expresiones regulares

from utils import parse_symbol_improved, calcular_dte_pata  # Asegúrate de importar correctamente


def procesar_archivo_actividad(archivo_csv, carpeta_posiciones="data/yaml/posiciones_activas"):
    """
    Procesa un archivo CSV de actividad de Tastytrade y crea archivos YAML de posiciones.
    """
    try:
        df = pd.read_csv(archivo_csv)
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo '{archivo_csv}'")
        return

    trades_agrupados = agrupar_trades(df)

    for subyacente_base, trade_data in trades_agrupados.items():
        crear_archivo_yaml_posicion(df, subyacente_base, trade_data, carpeta_posiciones)  # Pasar df


def agrupar_trades(df, umbral_tiempo_minutos=3):
    """
    Agrupa las filas del DataFrame en trades basado en la cercanía en la fecha/hora de ejecución y el subyacente "base".

    Args:
        df (pd.DataFrame): El DataFrame que contiene los datos de actividad.
        umbral_tiempo_minutos (int, optional): El umbral de tiempo en minutos para considerar
                                              transacciones como parte del mismo trade.
                                              Defaults to 3.

    Returns:
        dict: Un diccionario donde las claves son los subyacentes "base" y los valores son listas de filas del DataFrame.
    """
    trades = defaultdict(list)

    for index, row in df.iterrows():
        fecha_hora_str = row['Date']
        fecha_hora_dt = datetime.fromisoformat(fecha_hora_str)
        underlying_symbol = row['Underlying Symbol'] if row['Instrument Type'] == 'Future Option' else row['Root Symbol']
        # Extraer el "símbolo base" del futuro
        if row['Instrument Type'] == 'Future Option' and underlying_symbol:
            underlying_symbol_base = underlying_symbol[:-2]  # Eliminar los últimos 2 caracteres
        else:
            underlying_symbol_base = underlying_symbol

        trade_id = underlying_symbol_base  # Usar el subyacente base como ID inicial

        if trade_id not in trades:
            trades[trade_id] = []

        trades[trade_id].append(row.to_dict())

    # Verificar y agrupar manualmente los Calendar 1-1-2s (opcional)
    trades = agrupar_calendars(df, trades)

    return trades


def agrupar_calendars(df, trades):
    """
    Intenta agrupar los Calendar 1-1-2s. Requiere intervención manual.
    """
    calendar_trades = defaultdict(list)
    otros_trades = defaultdict(list)

    for trade_id, trade in trades.items():
        if len(trade) == 3 and all(parse_symbol_improved(t['Symbol'])['tipo'] == 'PUT' for t in trade if
                                  parse_symbol_improved(t['Symbol'])) and sum(t['Quantity'] for t in trade) == 2 and len(
                set(parse_symbol_improved(t['Symbol'])['vencimiento'] for t in trade if
                    parse_symbol_improved(t['Symbol']))) == 2:
            print(f"\nPosible Calendar 1-1-2: Trade ID(s): {[t['Order #'] for t in trade]}")
            for t in trade:
                print(f"- {t['Date']} - {t['Description']}")
            confirmacion = input("¿Es este un Calendar 1-1-2? (s/n): ")
            if confirmacion.lower() == 's':
                calendar_trades[trade_id] = trade  # Mantener el trade_id
            else:
                otros_trades[trade_id] = trade
        else:
            otros_trades[trade_id] = trade

    trades.clear()
    trades.update(otros_trades)
    trades.update(calendar_trades)

    return trades


def crear_archivo_yaml_posicion(df, subyacente_base, trade_data, carpeta_posiciones):  # Añadir df como primer argumento
    """
    Crea un archivo YAML para una posición agrupada, utilizando el subyacente base en el nombre del archivo.
    Reemplaza caracteres problemáticos en el nombre del archivo.
    """

    if not trade_data:
        return  # No hacer nada si no hay datos de trade

    fecha_inicio_str = trade_data[0]['Date'].split('T')[0]
    fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').strftime('%Y%m%d')
    estrategia = "Unknown"

    patas = []
    total_credito_debito = 0.0

    for pata_data in trade_data:
        pata_symbol = pata_data['Symbol']
        pata_opcion_details = parse_symbol_improved(pata_symbol)
        if pata_opcion_details:
            vencimiento_str = pata_opcion_details['vencimiento']
            vencimiento_date = datetime.strptime(vencimiento_str, '%Y-%m-%d').date() if vencimiento_str else None
            patas.append({
                'tipo': pata_opcion_details['tipo'],
                'strike': pata_data['Strike Price'],  # Obtener el strike de la columna 'Strike Price'
                'vencimiento': vencimiento_date,
                'cantidad': pata_data['Quantity'] if 'Quantity' in pata_data else 0,
                'precio_apertura': pata_data['Average Price'],
                'precio_actual': pata_data['Average Price'],
                'fecha_cierre': None,
                'precio_cierre': None,
            })
            total_credito_debito += pata_data['Total']

    # Determinar la estrategia DESPUÉS de agrupar las patas
    if len(patas) == 1 and patas[0]['tipo'] == 'PUT' and patas[0]['cantidad'] < 0:
        estrategia = "NakedPut"
    elif len(patas) == 3 and all(pata['tipo'] == 'PUT' for pata in patas):
        vencimientos = [pata['vencimiento'] for pata in patas if pata['vencimiento']]
        if len(vencimientos) == 3 and len(set(vencimientos)) == 2 and patas[0]['strike'] < patas[2]['strike']:
            estrategia = "Calendar1-1-2"

    # Reemplazar caracteres problemáticos en el nombre del archivo
    subyacente_base_seguro = re.sub(r'[\\/*?:"<>|]', '_', subyacente_base)
    nombre_archivo = f"{subyacente_base_seguro}_{fecha_inicio}_{estrategia}.yaml"
    ruta_archivo = os.path.join(carpeta_posiciones, nombre_archivo)

    posicion_data = {
        'id': str(uuid.uuid4()),
        'fecha_inicio': fecha_inicio,
        'subyacente': subyacente_base,
        'estrategia': estrategia,
        'cantidad_rolls': 0,
        'credito_debito_inicial': total_credito_debito,
        'credito_debito_actual': total_credito_debito,
        'patas': patas,
        'beta_delta_inicial': None,
        'delta_inicial': None,
        'theta_inicial': None,
        'vega_inicial': None,
        'ivr_inicial': None,
        'pop_inicial': None,
        'log_diario': {
            fecha_inicio: {
                'credito_debito': total_credito_debito,
                'mark_precio_spread': None,
                'dte_cercano': calcular_dte_pata(min(pata['vencimiento'] for pata in patas) if patas else None),
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

    with open(ruta_archivo, 'w') as archivo_yaml:
        yaml.dump(posicion_data, archivo_yaml, default_flow_style=False)

    print(f"Archivo YAML creado: {ruta_archivo}")


if __name__ == "__main__":
    archivo_csv = "data/csv/actividad/tastytrade_transactions_history_x5WW34822_241120_to_241120.csv"  # Reemplaza con tu archivo
    procesar_archivo_actividad(archivo_csv)

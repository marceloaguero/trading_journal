import pandas as pd
import yaml
import os
import uuid
from datetime import datetime, timedelta
from collections import defaultdict
import re  # Importar la biblioteca de expresiones regulares
import glob  # Para buscar archivos
import shutil  # Para mover archivos

from utils import parse_symbol_improved, calcular_dte_pata, es_1_1_2, es_calendar_1_1_2, es_iron_condor, es_strangle, identificar_spread, es_butterfly, es_broken_wing_butterfly, es_broken_wing_condor, es_ratio_spread  # Asegúrate de importar todas las funciones de utils


def procesar_archivos_actividad(carpeta_csv="data/csv/actividad/", carpeta_procesados="data/csv/actividad/procesados/",
                             carpeta_posiciones="data/yaml/posiciones_activas/", archivo_procesados="data/procesados.txt"):
    """
    Procesa todos los archivos CSV de actividad en una carpeta, evitando reprocesar los ya procesados.
    Mueve los archivos procesados a la carpeta 'procesados'.
    """
    try:
        with open(archivo_procesados, 'r') as f:
            archivos_procesados = f.read().splitlines()
    except FileNotFoundError:
        archivos_procesados = []

    archivos_csv = glob.glob(os.path.join(carpeta_csv, "*.csv"))

    for archivo_csv_ruta in archivos_csv:
        nombre_archivo = os.path.basename(archivo_csv_ruta)
        if nombre_archivo not in archivos_procesados:
            df = pd.read_csv(archivo_csv_ruta)
            procesar_archivo_actividad(df, nombre_archivo, carpeta_posiciones)
            archivos_procesados.append(nombre_archivo)
            with open(archivo_procesados, 'a') as f:
                f.write(nombre_archivo + '\n')
            # Mover el archivo a la carpeta 'procesados'
            shutil.move(archivo_csv_ruta, os.path.join(carpeta_csv, "procesados", nombre_archivo))


def procesar_archivo_actividad(df, nombre_archivo, carpeta_posiciones="data/yaml/posiciones_activas/"):
    """
    Procesa un único DataFrame (ya leído desde el CSV) y crea archivos YAML de posiciones.
    """

    trades_agrupados = agrupar_trades(df)

    for subyacente_base, trade_data in trades_agrupados.items():
        crear_archivo_yaml_posicion(df, subyacente_base, trade_data, carpeta_posiciones)


def agrupar_trades(df, umbral_tiempo_minutos=3):
    """
    Agrupa las filas del DataFrame en trades basado en la cercanía en la fecha/hora de ejecución y el subyacente "base".
    """
    trades = defaultdict(list)

    for index, row in df.iterrows():
        fecha_hora_str = row['Date']
        fecha_hora_dt = datetime.fromisoformat(fecha_hora_str)
        underlying_symbol = row['Underlying Symbol'] if row['Instrument Type'] == 'Future Option' else row['Root Symbol']
        # Extraer el "símbolo base" del futuro
        if row['Instrument Type'] == 'Future Option' and underlying_symbol:
            underlying_symbol_base = underlying_symbol[:-2]
        else:
            underlying_symbol_base = underlying_symbol

        trade_id = underlying_symbol_base

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


def crear_archivo_yaml_posicion(df, subyacente_base, trade_data, carpeta_posiciones):
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
            # vencimiento_str = pata_opcion_details['vencimiento']
            vencimiento_date = datetime.strptime(pata_data['Expiration Date'], '%m/%d/%y').date() if 'Expiration Date' in pata_data else None  # Usar Expiration Date
            cantidad = -pata_data['Quantity'] if 'SELL' in str(pata_data['Action']).upper() else pata_data['Quantity']
            patas.append({
                'tipo': pata_opcion_details['tipo'],
                'strike': pata_data['Strike Price'],
                'vencimiento': vencimiento_date,
                'cantidad': cantidad,
                'precio_apertura': pata_data['Average Price'],
                'precio_actual': pata_data['Average Price'],
                'fecha_cierre': None,
                'precio_cierre': None,
                'accion': str(pata_data['Action']).upper()  # Guardar la acción en mayúsculas
            })
            total_credito_debito += pata_data['Total']

    # Determinar la estrategia DESPUÉS de agrupar las patas
    if len(patas) == 1 and patas[0]['tipo'] == 'PUT' and patas[0]['cantidad'] < 0:
        estrategia = "NakedPut"
    elif es_1_1_2(patas):
        estrategia = "1-1-2"
        print("DEBUG: ¡Identificado como 1-1-2!")
    elif es_calendar_1_1_2(patas):
        estrategia = "Calendar1-1-2"
        print("DEBUG: ¡Identificado como Calendar 1-1-2!")
    elif es_iron_condor(patas):
        estrategia = "IronCondor"
        print("DEBUG: ¡Identificado como Iron Condor!")
    elif es_strangle(patas):
        estrategia = "Strangle"
        print("DEBUG: ¡Identificado como Strangle!")
    elif es_butterfly(patas):
        estrategia = "Butterfly"
        print("DEBUG: ¡Identificado como Butterfly!")
    elif es_broken_wing_butterfly(patas):
        estrategia = "BrokenWingButterfly"
        print("DEBUG: ¡Identificado como Broken Wing Butterfly!")
    elif es_broken_wing_condor(patas):
        estrategia = "BrokenWingCondor"
        print("DEBUG: ¡Identificado como Broken Wing Condor!")
    elif es_ratio_spread(patas):
        estrategia = "RatioSpread"
        print("DEBUG: ¡Identificado como Ratio Spread!")
    else:
        spread_type = identificar_spread(patas, total_credito_debito)
        if spread_type:
            estrategia = spread_type
            print(f"DEBUG: ¡Identificado como {estrategia}!")
        else:
            estrategia = "Unknown"
            print("DEBUG: No se pudo identificar la estrategia")

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
    procesar_archivos_actividad()

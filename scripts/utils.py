from datetime import datetime

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
        subyacente = parts[0].split('/')[1] if '/' in parts[0] else parts[0]  # Extraer subyacente de futuros
        vencimiento_str = parts[1][:6]  # Asume que los primeros 6 caracteres después del símbolo son la fecha
        vencimiento = datetime.strptime(vencimiento_str, '%y%m%d').strftime('%Y-%m-%d')
        tipo = "PUT" if "P" in symbol else "CALL"
        strike_str = parts[1][1:]  # Asume que el strike está después de la fecha
        strike = float(strike_str.split('P')[1].split('C')[1]) if 'P' in strike_str or 'C' in strike_str else float(strike_str)
        return {'subyacente': subyacente.strip(), 'vencimiento': vencimiento, 'tipo': tipo, 'strike': strike}
    except (ValueError, IndexError) as e:
        print(f"Error al parsear el símbolo '{symbol}': {e}")
        return None

def calcular_dte(vencimiento_str):
    """Calcula los días hasta el vencimiento."""
    vencimiento = datetime.strptime(vencimiento_str, '%Y-%m-%d')
    hoy = datetime.now().date()  # Obtener solo la fecha actual
    return (vencimiento.date() - hoy).days

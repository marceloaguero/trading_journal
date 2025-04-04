from datetime import datetime

def parse_symbol_improved(symbol):
    """
    Parsea el symbol de Tastytrade para extraer detalles, incluyendo opciones sobre futuros.
    Devuelve None si no se puede parsear.
    """
    try:
        parts = symbol.split()
        if len(parts) > 1:
            subyacente = parts[0].split('/')[1] if '/' in parts[0] else parts[0]
            vencimiento_str = parts[1][:6] if len(parts[1]) >= 6 else None
            vencimiento = datetime.strptime(vencimiento_str, '%y%m%d').strftime('%Y-%m-%d') if vencimiento_str else None
            tipo = "PUT" if "P" in symbol else "CALL" if "C" in symbol else None
            strike_str = ''.join(filter(str.isdigit, parts[-1])) if parts else None
            strike = float(strike_str) / 100.0 if strike_str else None
            return {'subyacente': subyacente.strip(), 'vencimiento': vencimiento, 'tipo': tipo, 'strike': strike}
        else:
            return None
    except (ValueError, IndexError, TypeError) as e:
        print(f"Error al parsear el símbolo '{symbol}': {e}")
        return None

def es_put(pata):
    return pata['tipo'] == 'PUT'

def es_call(pata):
    return pata['tipo'] == 'CALL'

def es_compra(cantidad):
    return cantidad > 0

def es_venta(cantidad):
    return cantidad < 0

def calcular_dte_pata(vencimiento):
    hoy = datetime.now().date()
    return (vencimiento.date() - hoy).days if vencimiento else None

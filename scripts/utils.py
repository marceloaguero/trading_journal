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

def calcular_dte_pata(vencimiento):
    hoy = datetime.now().date()
    return (vencimiento - hoy).days if vencimiento else None

def es_1_1_2(patas):
    """
    Identifica la estrategia 1-1-2.

    Args:
        patas (list): Una lista de diccionarios, donde cada diccionario representa una pata de la operación.

    Returns:
        bool: True si las patas corresponden a una estrategia 1-1-2, False en caso contrario.
    """
    print("DEBUG: es_1_1_2 - Inicio")
    if len(patas) != 3 or not all(pata['tipo'] == 'PUT' for pata in patas):
        print("DEBUG: No es 1-1-2 (Número de patas o tipos incorrectos)")
        return False

    cantidades = [pata['cantidad'] for pata in patas]
    print(f"DEBUG: Cantidades: {cantidades}")
    if sum(cantidades) != -2:
        print("DEBUG: No es 1-1-2 (Cantidades incorrectas)")
        return False

    vencimientos = [pata['vencimiento'] for pata in patas]
    print(f"DEBUG: Vencimientos: {vencimientos}")
    if len(set(vencimientos)) != 1:  # Corrección: Verificar que haya solo 1 vencimiento
        print("DEBUG: No es 1-1-2 (Vencimientos incorrectos)")
        return False

    strikes = [pata['strike'] for pata in patas]
    print(f"DEBUG: Strikes: {strikes}")
    if len(set(strikes)) != 3:  # Corrección: Verificar que haya 3 strikes diferentes
        print("DEBUG: No es 1-1-2 (Número de strikes incorrecto)")
        return False

    # Ordenar las patas por strike
    patas_ordenadas = sorted(patas, key=lambda pata: pata['strike'])
    print(f"DEBUG: Patas Ordenadas: {patas_ordenadas}")

    if patas_ordenadas[0]['strike'] < patas_ordenadas[1]['strike'] and patas_ordenadas[1]['strike'] < patas_ordenadas[2]['strike']:  # Corrección: Verificar la secuencia creciente de strikes
        print("DEBUG: Es 1-1-2")
        return True
    else:
        print("DEBUG: No es 1-1-2 (Condición final incorrecta)")
        return False

    return False

def es_calendar_1_1_2(patas):
    """
    Identifica la estrategia Calendar 1-1-2.

    Args:
        patas (list): Una lista de diccionarios, donde cada diccionario representa una pata de la operación.

    Returns:
        bool: True si las patas corresponden a una estrategia Calendar 1-1-2, False en caso contrario.
    """
    print("DEBUG: es_calendar_1_1_2 - Inicio")
    if len(patas) != 3 or not all(pata['tipo'] == 'PUT' for pata in patas):
        print("DEBUG: No es Calendar 1-1-2 (Número de patas o tipos incorrectos)")
        return False

    cantidades = [pata['cantidad'] for pata in patas]
    print(f"DEBUG: Cantidades: {cantidades}")
    if sum(cantidades) != -2:  # Corrección: Verificar que la suma sea -2
        print("DEBUG: No es Calendar 1-1-2 (Cantidades incorrectas)")
        return False

    vencimientos = [pata['vencimiento'] for pata in patas]
    print(f"DEBUG: Vencimientos: {vencimientos}")
    if len(vencimientos) != 3 or len(set(vencimientos)) != 2:
        print("DEBUG: No es Calendar 1-1-2 (Vencimientos incorrectos)")
        return False

    # Ordenar las patas por fecha de vencimiento
    patas_ordenadas = sorted(patas, key=lambda pata: pata['vencimiento'])
    print(f"DEBUG: Patas Ordenadas: {patas_ordenadas}")

    # Verificar que haya 2 ventas y 1 compra
    if cantidades.count(-2) != 0 and cantidades.count(-1) != 2 and cantidades.count(1) != 1:
        print("DEBUG: No es Calendar 1-1-2 (Cantidad de ventas o compras incorrecta)")
        return False

    if patas_ordenadas[0]['strike'] < patas_ordenadas[2]['strike']:
        print("DEBUG: Es Calendar 1-1-2")
        return True
    else:
        print("DEBUG: No es Calendar 1-1-2 (Strikes incorrectos)")
        return False

def es_iron_condor(patas):
    """
    Identifica la estrategia Iron Condor.

    Args:
        patas (list): Una lista de diccionarios, donde cada diccionario representa una pata de la operación.

    Returns:
        bool: True si las patas corresponden a una estrategia Iron Condor, False en caso contrario.
    """
    if len(patas) != 4:
        return False

    vencimientos = [pata['vencimiento'] for pata in patas]
    if len(set(vencimientos)) != 1:
        return False

    tipos = [pata['tipo'] for pata in patas]
    if tipos.count('PUT') != 2 or tipos.count('CALL') != 2:
        return False

    cantidades = [pata['cantidad'] for pata in patas]
    if cantidades.count(1) != 2 or cantidades.count(-1) != 2:
        return False

    # Ordenar las patas por strike
    patas_ordenadas = sorted(patas, key=lambda pata: pata['strike'])
    strikes = [pata['strike'] for pata in patas_ordenadas]

    if strikes[0] < strikes[1] < strikes[2] < strikes[3] and \
       patas_ordenadas[0]['tipo'] == 'PUT' and patas_ordenadas[1]['tipo'] == 'PUT' and \
       patas_ordenadas[2]['tipo'] == 'CALL' and patas_ordenadas[3]['tipo'] == 'CALL' and \
       patas_ordenadas[0]['cantidad'] > 0 and patas_ordenadas[1]['cantidad'] < 0 and \
       patas_ordenadas[2]['cantidad'] < 0 and patas_ordenadas[3]['cantidad'] > 0:
        return True

    return False

def es_strangle(patas):
    """
    Identifica la estrategia Strangle.

    Args:
        patas (list): Una lista de diccionarios, donde cada diccionario representa una pata de la operación.

    Returns:
        bool: True si las patas corresponden a una estrategia Strangle, False en caso contrario.
    """
    if len(patas) != 2:
        return False

    vencimientos = [pata['vencimiento'] for pata in patas]
    if len(set(vencimientos)) != 1:
        return False

    tipos = [pata['tipo'] for pata in patas]
    if 'CALL' not in tipos or 'PUT' not in tipos:
        return False

    cantidades = [pata['cantidad'] for pata in patas]
    if cantidades[0] > 0 or cantidades[1] > 0:  # Corrección: Verificar que ambas sean ventas
        return False

    strikes = [pata['strike'] for pata in patas]
    if strikes[0] == strikes[1]:
        return False

    return True

def identificar_spread(patas, total):
    """
    Identifica si las patas corresponden a una estrategia Spread (Vertical).

    Args:
        patas (list): Una lista de diccionarios, donde cada diccionario representa una pata de la operación.
        total (float): El Total (crédito o débito) de la operación.

    Returns:
        str: El tipo de spread ("Credit Put Spread", "Credit Call Spread", "Debit Put Spread", "Debit Call Spread"),
             o None si no es un spread.
    """
    if len(patas) != 2:
        return None

    tipos = [pata['tipo'] for pata in patas]
    if tipos[0] != tipos[1]:
        return None

    acciones = [pata['accion'] for pata in patas]
    if 'SELL_TO_OPEN' not in acciones or 'BUY_TO_OPEN' not in acciones:
        return None

    if tipos[0] == 'PUT':
        tipo_opcion = "Put"
    elif tipos[0] == 'CALL':
        tipo_opcion = "Call"
    else:
        return None  # Por si acaso

    if total > 0:
        return f"Credit {tipo_opcion} Spread"
    elif total < 0:
        return f"Debit {tipo_opcion} Spread"
    else:
        return None  # Imposible, pero por si acaso

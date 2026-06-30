import re

def get_led_specs(color: str):
    """
    Analyzes a color string to determine typical LED specifications.
    Returns a dict with 'voltage' and 'current' or None if no match is found.
    """
    if not color:
        return None

    c_lower = color.lower().strip()
    
    if c_lower in ['vermelho', 'amarelo', 'laranja']:
        return {"voltage": "2.0V", "current": "20mA"}
    
    elif c_lower == 'verde':
        return {"voltage": "2.2V", "current": "20mA"}
    
    elif c_lower in ['azul', 'branco', 'ultravioleta', 'uv']:
        return {"voltage": "3.2V", "current": "20mA"}
        
    return None

def get_semiconductor_specs(part_number: str):
    if not part_number:
        return None

    pn_lower = part_number.lower().strip()
    
    specs = {
        '1n4007': {'Tipo': 'Retificador', 'Tensão Máx (V)': '1000', 'Corrente Máx (A)': '1', 'Encapsulamento': 'DO-41 (PTH)'},
        'm7': {'Tipo': 'Retificador', 'Tensão Máx (V)': '1000', 'Corrente Máx (A)': '1', 'Encapsulamento': 'SMA (SMD)'},
        '1n4148': {'Tipo': 'Sinal', 'Tensão Máx (V)': '100', 'Corrente Máx (A)': '0.3', 'Encapsulamento': 'DO-35 (PTH)'},
        'ss34': {'Tipo': 'Schottky', 'Tensão Máx (V)': '40', 'Corrente Máx (A)': '3', 'Encapsulamento': 'SMC (SMD)'},
        'mb10s': {'Tipo': 'Ponte Retificadora', 'Tensão Máx (V)': '1000', 'Corrente Máx (A)': '1', 'Encapsulamento': 'MBS (SMD)'}
    }
    
    for key, spec in specs.items():
        if key in pn_lower:
            return spec
            
    if 'zener' in pn_lower:
        return {'Tipo': 'Zener'}
        
    return None

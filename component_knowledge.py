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
        '1n4007': {'Tipo': 'Retificador', 'Tensão Máx': '1000V', 'Corrente Máx': '1A', 'Encapsulamento': 'DO-41 (PTH)'},
        'm7': {'Tipo': 'Retificador', 'Tensão Máx': '1000V', 'Corrente Máx': '1A', 'Encapsulamento': 'SMA (SMD)'},
        '1n4148': {'Tipo': 'Sinal Rápido', 'Tensão Máx': '100V', 'Corrente Máx': '300mA', 'Encapsulamento': 'DO-35 (PTH)'},
        '1n4148w': {'Tipo': 'Sinal Rápido', 'Tensão Máx': '100V', 'Corrente Máx': '150mA', 'Encapsulamento': 'SOD-123 (SMD)'},
        '1n5819': {'Tipo': 'Schottky', 'Tensão Máx': '40V', 'Corrente Máx': '1A', 'Encapsulamento': 'DO-41 (PTH)'},
        'ss34': {'Tipo': 'Schottky', 'Tensão Máx': '40V', 'Corrente Máx': '3A', 'Encapsulamento': 'SMC (SMD)'},
        'mb10s': {'Tipo': 'Ponte Retificadora', 'Tensão Máx': '1000V', 'Corrente Máx': '1A', 'Encapsulamento': 'SOIC-4 (SMD)'},
        'kbpc3510': {'Tipo': 'Ponte Retificadora', 'Tensão Máx': '1000V', 'Corrente Máx': '35A', 'Encapsulamento': 'Metal Quadrado'},
        'kbp206': {'Tipo': 'Ponte Retificadora', 'Tensão Máx': '600V', 'Corrente Máx': '2A', 'Encapsulamento': 'SIP-4 (PTH)'}
    }
    
    for key, spec in specs.items():
        if key in pn_lower:
            return spec
            
    if 'zener' in pn_lower:
        return {'Tipo': 'Zener'}
        
    return None

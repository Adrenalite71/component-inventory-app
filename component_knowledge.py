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
        'mb10s': {'Fases': 'Monofásica', 'Tensão Máx (V)': '1000', 'Corrente Máx (A)': '1', 'Encapsulamento': 'MBS (SMD)'},
        'kbpc3510': {'Fases': 'Monofásica', 'Tensão Máx (V)': '1000', 'Corrente Máx (A)': '35', 'Encapsulamento': 'KBPC (Metal Quadrado)'},
        'kbp206': {'Fases': 'Monofásica', 'Tensão Máx (V)': '600', 'Corrente Máx (A)': '2', 'Encapsulamento': 'KBP (PTH)'}
    }
    
    for key, spec in specs.items():
        if key in pn_lower:
            return spec
            
    if 'zener' in pn_lower:
        return {'Tipo': 'Zener'}
        
    return None

def get_relay_specs(part_number: str):
    if not part_number:
        return None

    pn_lower = part_number.lower().strip()
    
    specs = {
        'srd-05vdc': {'Tipo': 'Eletromecânico', 'Tipo de Contato': 'SPDT (1 Reversível)', 'Tensão da Bobina (V)': '5', 'Corrente Máx dos Contatos (A)': '10'},
        'srd-12vdc': {'Tipo': 'Eletromecânico', 'Tipo de Contato': 'SPDT (1 Reversível)', 'Tensão da Bobina (V)': '12', 'Corrente Máx dos Contatos (A)': '10'},
        'srd-24vdc': {'Tipo': 'Eletromecânico', 'Tipo de Contato': 'SPDT (1 Reversível)', 'Tensão da Bobina (V)': '24', 'Corrente Máx dos Contatos (A)': '10'},
        'fotek ssr-40da': {'Tipo': 'Estado Sólido (SSR)', 'Tipo de Contato': 'SPST-NO (1 NA)', 'Tensão da Bobina (V)': '3-32 (DC)', 'Corrente Máx dos Contatos (A)': '40'}
    }
    
    for key, spec in specs.items():
        if key in pn_lower:
            return spec
            
    return None

def get_transistor_specs(part_number: str):
    if not part_number:
        return None

    pn_lower = part_number.lower().strip()
    
    specs = {
        'bc548': {'Tipo': 'BJT', 'Polaridade': 'NPN', 'Encapsulamento': 'TO-92', 'Tensão Máx (VCEO/VDS)': '30', 'Corrente Máx (IC/ID)': '0.1'},
        'bc558': {'Tipo': 'BJT', 'Polaridade': 'PNP', 'Encapsulamento': 'TO-92', 'Tensão Máx (VCEO/VDS)': '30', 'Corrente Máx (IC/ID)': '0.1'},
        '2n2222': {'Tipo': 'BJT', 'Polaridade': 'NPN', 'Encapsulamento': 'TO-92', 'Tensão Máx (VCEO/VDS)': '40', 'Corrente Máx (IC/ID)': '0.8'},
        'tip122': {'Tipo': 'Darlington', 'Polaridade': 'NPN', 'Encapsulamento': 'TO-220', 'Tensão Máx (VCEO/VDS)': '100', 'Corrente Máx (IC/ID)': '5'},
        'irf540n': {'Tipo': 'MOSFET', 'Polaridade': 'N-Channel', 'Encapsulamento': 'TO-220', 'Tensão Máx (VCEO/VDS)': '100', 'Corrente Máx (IC/ID)': '33'}
    }
    
    for key, spec in specs.items():
        if key in pn_lower:
            return spec
            
    return None

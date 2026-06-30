import re

def get_led_specs(component_name: str):
    """
    Analyzes a component name to determine typical LED specifications based on color.
    Returns a dict with 'voltage' and 'current' or None if no color is detected.
    """
    name_lower = component_name.lower()
    
    # Check for colors in the name
    if re.search(r'\b(vermelho|amarelo|laranja|red|yellow|orange)\b', name_lower):
        return {"voltage": "2.0V", "current": "20mA"}
    
    elif re.search(r'\b(verde|green)\b', name_lower):
        return {"voltage": "2.2V", "current": "20mA"}
    
    elif re.search(r'\b(azul|branco|ultravioleta|uv|blue|white)\b', name_lower):
        return {"voltage": "3.2V", "current": "20mA"}
        
    return None

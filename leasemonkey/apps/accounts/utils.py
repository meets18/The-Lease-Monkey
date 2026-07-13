import re
from decimal import Decimal
from datetime import date

def validate_password_strength(password):
    """
    Validates password strength:
    - At least 12 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special symbol
    Returns list of error messages, or empty list if valid.
    """
    errors = []
    if len(password) < 12:
        errors.append("Password must be at least 12 characters long.")
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r'[0-9]', password):
        errors.append("Password must contain at least one digit.")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special symbol.")
    return errors

def calculate_age(dob):
    """Calculates age based on Date of Birth date object."""
    if not dob:
        return 0
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def parse_indian_number(val_str):
    """
    Parses number strings supporting Indian notation (e.g. 15,00,000, 15L, 1.5 Cr).
    Returns Decimal or None if invalid.
    """
    if not val_str:
        return Decimal('0')
    # Normalize string: remove commas, whitespace, convert to lowercase
    s = re.sub(r'[\s,]', '', str(val_str)).lower()
    
    # Check for Lakhs / L / lakhs
    if s.endswith('lakhs') or s.endswith('lakh') or s.endswith('l'):
        num_part = re.sub(r'[a-z]', '', s)
        try:
            return Decimal(num_part) * Decimal('100000')
        except (ValueError, TypeError):
            pass
            
    # Check for Crores / Cr / crores
    if s.endswith('crores') or s.endswith('crore') or s.endswith('cr'):
        num_part = re.sub(r'[a-z]', '', s)
        try:
            return Decimal(num_part) * Decimal('10000000')
        except (ValueError, TypeError):
            pass
            
    # Standard raw number parse
    try:
        return Decimal(s)
    except (ValueError, TypeError):
        return None

def format_indian_numeral(value):
    """
    Formats a numeric value with commas according to the Indian numbering system:
    e.g. 1500000 -> 15,00,000
    """
    if value is None:
        return ""
    try:
        dec = Decimal(str(value))
        # Handle negative sign
        is_negative = dec < 0
        if is_negative:
            dec = abs(dec)
            
        s = f"{dec:.2f}"
        parts = s.split('.')
        int_part = parts[0]
        frac_part = parts[1]
        
        if len(int_part) <= 3:
            int_str = int_part
        else:
            last_three = int_part[-3:]
            remaining = int_part[:-3]
            groups = []
            while len(remaining) > 0:
                if len(remaining) >= 2:
                    groups.insert(0, remaining[-2:])
                    remaining = remaining[:-2]
                else:
                    groups.insert(0, remaining)
                    remaining = ""
            int_str = ",".join(groups) + "," + last_three
            
        # Add sign back
        res = f"-{int_str}" if is_negative else int_str
        
        # If float value has .00, omit the decimal points for clean integer display
        if dec == dec.to_integral_value():
            return res
        return f"{res}.{frac_part}"
    except (ValueError, TypeError):
        return str(value)

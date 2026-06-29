import sqlite3

# pyrefly: ignore [missing-import]
import customtkinter as ctk
from tkinter import ttk, messagebox
import pandas as pd
import traceback
import re

DB_FILE = "inventory.db"

CATEGORIES = [
    "Capacitor PTH",
    "Capacitor SMD",
    "Resistor PTH",
    "Resistor SMD",
    "Transistor",
    "Indutor",
    "CI (Circuito Integrado)",
    "Optoacoplador",
    "Outros",
]


class DatabaseHelper:
    @staticmethod
    def init_db():
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # Create base tables
        c.execute("""
            CREATE TABLE IF NOT EXISTS drawers (
                door_code TEXT PRIMARY KEY CHECK(length(door_code) = 4),
                capacity INTEGER
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS subdivisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drawer_code TEXT,
                subdivision_index INTEGER,
                FOREIGN KEY(drawer_code) REFERENCES drawers(door_code)
            )
        """)

        # MIGRATION: Remove capacity constraint from drawers table if it exists
        c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='drawers'")
        row = c.fetchone()
        if row and "capacity <=" in row[0]:
            c.execute(
                "CREATE TABLE drawers_new (door_code TEXT PRIMARY KEY CHECK(length(door_code) = 4), capacity INTEGER)"
            )
            c.execute("INSERT INTO drawers_new SELECT * FROM drawers")
            c.execute("DROP TABLE drawers")
            c.execute("ALTER TABLE drawers_new RENAME TO drawers")

        c.execute("""
            CREATE TABLE IF NOT EXISTS components (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                raw_value TEXT,
                normalized_base_value REAL,
                quantity INTEGER DEFAULT 0,
                subdivision_id INTEGER,
                FOREIGN KEY(subdivision_id) REFERENCES subdivisions(id)
            )
        """)

        # MIGRATION: Add missing columns if they don't exist
        c.execute("PRAGMA table_info(components)")
        existing_columns = [col[1] for col in c.fetchall()]

        if "voltage" not in existing_columns:
            c.execute("ALTER TABLE components ADD COLUMN voltage TEXT")
        if "tolerance" not in existing_columns:
            c.execute("ALTER TABLE components ADD COLUMN tolerance TEXT")
        if "component_type" not in existing_columns:
            c.execute("ALTER TABLE components ADD COLUMN component_type TEXT")

        c.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                logic_type TEXT NOT NULL,
                fields_json TEXT DEFAULT '[]'
            )
        """)

        c.execute("PRAGMA table_info(categories)")
        existing_cat_cols = [col[1] for col in c.fetchall()]
        if "fields_json" not in existing_cat_cols:
            c.execute("ALTER TABLE categories ADD COLUMN fields_json TEXT DEFAULT '[]'")

        c.execute("SELECT count(*) FROM categories")
        if c.fetchone()[0] == 0:
            for cat in CATEGORIES:
                c.execute(
                    "INSERT INTO categories (name, logic_type, fields_json) VALUES (?, ?, ?)",
                    (cat, cat, "[]"),
                )

        c.execute("DELETE FROM categories WHERE name IN ('MOSFET', 'IGBT')")

        conn.commit()
        conn.close()

    @staticmethod
    def get_categories():
        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        c.execute("SELECT name, logic_type, fields_json FROM categories ORDER BY id")
        rows = c.fetchall()
        conn.close()
        return rows

    @staticmethod
    def get_connection():
        return sqlite3.connect(DB_FILE)


class SMDDecoder:
    EIA96_MULTIPLIERS = {
        "Z": 0.001,
        "Y": 0.01,
        "R": 0.01,
        "X": 0.1,
        "S": 0.1,
        "A": 1,
        "B": 10,
        "C": 100,
        "D": 1000,
        "E": 10000,
        "F": 100000,
    }

    EIA96_VALUES = [
        100,
        102,
        105,
        107,
        110,
        113,
        115,
        118,
        121,
        124,
        127,
        130,
        133,
        137,
        140,
        143,
        147,
        150,
        154,
        158,
        162,
        165,
        169,
        174,
        178,
        182,
        187,
        191,
        196,
        200,
        205,
        210,
        215,
        221,
        226,
        232,
        237,
        243,
        249,
        255,
        261,
        267,
        274,
        280,
        287,
        294,
        301,
        309,
        316,
        324,
        332,
        340,
        348,
        357,
        365,
        374,
        383,
        392,
        402,
        412,
        422,
        432,
        442,
        453,
        464,
        475,
        487,
        499,
        511,
        523,
        536,
        549,
        562,
        576,
        590,
        604,
        619,
        634,
        649,
        665,
        681,
        698,
        715,
        732,
        750,
        768,
        787,
        806,
        825,
        845,
        866,
        887,
        909,
        931,
        953,
        976,
    ]

    CAP_VOLTAGE_CODES = {
        "e": 2.5,
        "G": 4,
        "J": 6.3,
        "A": 10,
        "C": 16,
        "D": 20,
        "E": 25,
        "V": 35,
        "H": 50,
        "T": 63,
        "x": 63,
    }

    @staticmethod
    def decode_resistor_smd(code):
        code = code.strip().upper()

        if "R" in code:
            try:
                val = float(code.replace("R", "."))
                return val, None
            except ValueError:
                pass

        match_eia96 = re.match(r"^(\d{2})([A-Z])$", code)
        if match_eia96:
            code_num = int(match_eia96.group(1))
            multiplier = match_eia96.group(2)
            if 1 <= code_num <= 96 and multiplier in SMDDecoder.EIA96_MULTIPLIERS:
                val = (
                    SMDDecoder.EIA96_VALUES[code_num - 1]
                    * SMDDecoder.EIA96_MULTIPLIERS[multiplier]
                )
                return float(val), "1%"

        match_digits = re.match(r"^(\d+)(\d)$", code)
        if match_digits:
            base = int(match_digits.group(1))
            mult = int(match_digits.group(2))
            val = base * (10**mult)
            tol = "5%" if len(code) == 3 else "1%"
            return float(val), tol

        return None, None

    @staticmethod
    def decode_capacitor_smd(code):
        code = code.strip()

        match_explicit = re.search(
            r"^([\d\.]+)\s*(uF|u|nF|n|pF|p|mF|m)?\s*[\s,]*(\d+)\s*V$",
            code,
            re.IGNORECASE,
        )
        if match_explicit:
            val = float(match_explicit.group(1))
            unit = (match_explicit.group(2) or "").lower()
            voltage = f"{match_explicit.group(3)}V"

            if "p" in unit:
                val *= 1e-12
            elif "n" in unit:
                val *= 1e-9
            elif "m" in unit:
                val *= 1e-3
            else:
                val *= 1e-6

            return val, voltage

        match_letter = re.match(r"^([a-zA-Z])(\d{2})(\d)$", code)
        if match_letter:
            letter = match_letter.group(1)
            if letter not in SMDDecoder.CAP_VOLTAGE_CODES:
                letter = letter.upper()

            voltage = None
            if letter in SMDDecoder.CAP_VOLTAGE_CODES:
                voltage = f"{SMDDecoder.CAP_VOLTAGE_CODES[letter]}V"

            base = int(match_letter.group(2))
            mult = int(match_letter.group(3))

            val_pf = base * (10**mult)
            val = val_pf * 1e-12
            return val, voltage

        match_3digit = re.match(r"^(\d{2})(\d)$", code)
        if match_3digit:
            base = int(match_3digit.group(1))
            mult = int(match_3digit.group(2))
            val_pf = base * (10**mult)
            val = val_pf * 1e-12
            return val, None

        return None, None

    @staticmethod
    def parse_search_query(query):
        """Converts human readable '10k', '100n' into numeric values."""
        query = query.strip().replace(",", ".")

        if "R" in query.upper() and not re.search(r"[a-qs-zA-QS-Z]", query):
            try:
                return float(query.upper().replace("R", "."))
            except:
                pass

        match = re.match(
            r"^([\d\.]+)\s*(p|n|u|m|M|k|K|G)?([fF]|ohms|ohm|Ohm|R)?$", query
        )
        if match:
            try:
                val = float(match.group(1))
                mult = match.group(2)

                if mult == "p":
                    val *= 1e-12
                elif mult == "n":
                    val *= 1e-9
                elif mult in ("u", "U"):
                    val *= 1e-6
                elif mult == "m":
                    val *= 1e-3
                elif mult in ("k", "K"):
                    val *= 1e3
                elif mult == "M":
                    val *= 1e6
                elif mult == "G":
                    val *= 1e9

                return val
            except ValueError:
                pass

        return None

    @staticmethod
    def format_resistance(val):
        if val is None or pd.isna(val) or val == "":
            return ""
        val = float(val)
        if val >= 1e6:
            return f"{val/1e6:g}MΩ"
        if val >= 1e3:
            return f"{val/1e3:g}kΩ"
        return f"{val:g}Ω"

    @staticmethod
    def format_capacitance(val):
        if val is None or pd.isna(val) or val == "":
            return ""
        val = float(val)
        if val >= 1e-3:
            return f"{val/1e-3:g}mF"
        if val >= 1e-6:
            return f"{val/1e-6:g}µF"
        if val >= 1e-9:
            return f"{val/1e-9:g}nF"
        return f"{val/1e-12:g}pF"


class PTHResistorCalculator:
    DIGITS = {
        "Preto": 0,
        "Marrom": 1,
        "Vermelho": 2,
        "Laranja": 3,
        "Amarelo": 4,
        "Verde": 5,
        "Azul": 6,
        "Violeta": 7,
        "Cinza": 8,
        "Branco": 9,
    }
    MULTIPLIERS = {
        "Preto": 1,
        "Marrom": 10,
        "Vermelho": 100,
        "Laranja": 1000,
        "Amarelo": 10000,
        "Verde": 100000,
        "Azul": 1000000,
        "Violeta": 10000000,
        "Cinza": 100000000,
        "Branco": 1000000000,
        "Dourado": 0.1,
        "Prateado": 0.01,
    }
    TOLERANCES = {
        "Marrom": "1%",
        "Vermelho": "2%",
        "Verde": "0.5%",
        "Azul": "0.25%",
        "Violeta": "0.1%",
        "Cinza": "0.05%",
        "Dourado": "5%",
        "Prateado": "10%",
    }
    TEMP_COEFFS = {
        "Marrom": "100ppm",
        "Vermelho": "50ppm",
        "Laranja": "15ppm",
        "Amarelo": "25ppm",
        "Azul": "10ppm",
        "Violeta": "5ppm",
        "Branco": "1ppm",
    }

    @staticmethod
    def calculate(bands):
        if not bands:
            return ""
        try:
            if len(bands) == 4:
                val = (
                    PTHResistorCalculator.DIGITS[bands[0]] * 10
                    + PTHResistorCalculator.DIGITS[bands[1]]
                ) * PTHResistorCalculator.MULTIPLIERS[bands[2]]
                tol = PTHResistorCalculator.TOLERANCES.get(bands[3], "")
                return f"{SMDDecoder.format_resistance(val)} {tol}".strip()
            elif len(bands) == 5:
                val = (
                    PTHResistorCalculator.DIGITS[bands[0]] * 100
                    + PTHResistorCalculator.DIGITS[bands[1]] * 10
                    + PTHResistorCalculator.DIGITS[bands[2]]
                ) * PTHResistorCalculator.MULTIPLIERS[bands[3]]
                tol = PTHResistorCalculator.TOLERANCES.get(bands[4], "")
                return f"{SMDDecoder.format_resistance(val)} {tol}".strip()
            elif len(bands) == 6:
                val = (
                    PTHResistorCalculator.DIGITS[bands[0]] * 100
                    + PTHResistorCalculator.DIGITS[bands[1]] * 10
                    + PTHResistorCalculator.DIGITS[bands[2]]
                ) * PTHResistorCalculator.MULTIPLIERS[bands[3]]
                tol = PTHResistorCalculator.TOLERANCES.get(bands[4], "")
                tc = PTHResistorCalculator.TEMP_COEFFS.get(bands[5], "")
                return f"{SMDDecoder.format_resistance(val)} {tol} {tc}".strip()
            return ""
        except KeyError:
            return ""


class CategoryUIBuilder:
    """Shared class to build exactly identical UI components for both Registration and Search"""

    @staticmethod
    def build_fields(parent_frame, category_config, is_search=False):
        category = category_config.get("logic_type", "Outros")
        fields_json = category_config.get("fields", "[]")
        try:
            custom_fields = json.loads(fields_json)
        except:
            custom_fields = []

        # Clear frame
        for widget in parent_frame.winfo_children():
            widget.destroy()

        inputs = {}

        # Helper to add simple text entry
        def add_entry(row, col, label_text, key, placeholder=None):
            ctk.CTkLabel(parent_frame, text=label_text).grid(
                row=row, column=col * 2, padx=(10, 5), pady=10, sticky="e"
            )
            if placeholder:
                entry = ctk.CTkEntry(
                    parent_frame, width=150, placeholder_text=placeholder
                )
            else:
                entry = ctk.CTkEntry(parent_frame, width=150)
            entry.grid(row=row, column=col * 2 + 1, padx=(0, 15), pady=10, sticky="w")
            inputs[key] = entry

        # Helper to add dropdown
        def add_combo(row, col, label_text, key, values, command=None):
            label = ctk.CTkLabel(parent_frame, text=label_text)
            label.grid(row=row, column=col * 2, padx=(10, 5), pady=10, sticky="e")
            # If search, add empty option at top
            vals = [""] + values if is_search else values
            var = ctk.StringVar(value=vals[0])
            combo = ctk.CTkOptionMenu(
                parent_frame, variable=var, values=vals, width=150, command=command
            )
            combo.grid(row=row, column=col * 2 + 1, padx=(0, 15), pady=10, sticky="w")
            inputs[key] = var
            return combo, label

        if category == "Resistor PTH":
            # For PTH Resistors, we implement the Segmented Button toggle
            method_var = ctk.StringVar(value="Entrada Direta")
            inputs["r_method"] = method_var

            method_menu = ctk.CTkSegmentedButton(
                parent_frame,
                variable=method_var,
                values=["Entrada Direta", "Cores (Bandas)"],
            )
            method_menu.grid(
                row=0, column=0, columnspan=4, padx=10, pady=(10, 0), sticky="ew"
            )

            direct_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
            direct_frame.grid(row=1, column=0, columnspan=4, sticky="ew")

            bands_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")

            # Direct Entry widgets
            ctk.CTkLabel(direct_frame, text="Valor (ex: 2k2):").grid(
                row=0, column=0, padx=5, pady=10
            )
            val_entry = ctk.CTkEntry(direct_frame, width=120)
            val_entry.grid(row=0, column=1, padx=5, pady=10)
            inputs["raw_value"] = val_entry

            ctk.CTkLabel(direct_frame, text="Tolerância:").grid(
                row=0, column=2, padx=5, pady=10
            )
            tol_entry = ctk.CTkEntry(direct_frame, width=120)
            tol_entry.grid(row=0, column=3, padx=5, pady=10)
            inputs["tolerance"] = tol_entry

            ctk.CTkLabel(direct_frame, text="Encapsulamento:").grid(
                row=0, column=4, padx=5, pady=10
            )
            type_entry = ctk.CTkEntry(direct_frame, width=120)
            type_entry.grid(row=0, column=5, padx=5, pady=10)
            inputs["component_type"] = type_entry

            # Bands widgets
            ctk.CTkLabel(bands_frame, text="Bandas:").grid(
                row=0, column=0, padx=5, pady=10
            )
            band_count_var = ctk.StringVar(value="4")
            inputs["r_band_count"] = band_count_var
            band_count_menu = ctk.CTkOptionMenu(
                bands_frame, variable=band_count_var, values=["4", "5", "6"], width=60
            )
            band_count_menu.grid(row=0, column=1, padx=5, pady=10)

            colors = [
                "Preto",
                "Marrom",
                "Vermelho",
                "Laranja",
                "Amarelo",
                "Verde",
                "Azul",
                "Violeta",
                "Cinza",
                "Branco",
                "Dourado",
                "Prateado",
            ]
            if is_search:
                colors = [""] + colors

            band_vars = []
            band_combos = []
            for i in range(6):
                var = ctk.StringVar(value=colors[0])
                band_vars.append(var)
                cb = ctk.CTkOptionMenu(
                    bands_frame, variable=var, values=colors, width=80
                )
                band_combos.append(cb)

            inputs["r_bands"] = band_vars

            def update_bands(*args):
                count = int(band_count_var.get())

                digits_colors = [
                    "Preto",
                    "Marrom",
                    "Vermelho",
                    "Laranja",
                    "Amarelo",
                    "Verde",
                    "Azul",
                    "Violeta",
                    "Cinza",
                    "Branco",
                ]
                multi_colors = [
                    "Preto",
                    "Marrom",
                    "Vermelho",
                    "Laranja",
                    "Amarelo",
                    "Verde",
                    "Azul",
                    "Violeta",
                    "Cinza",
                    "Branco",
                    "Dourado",
                    "Prateado",
                ]
                tol_colors = [
                    "Marrom",
                    "Vermelho",
                    "Verde",
                    "Azul",
                    "Violeta",
                    "Cinza",
                    "Dourado",
                    "Prateado",
                ]
                temp_colors = [
                    "Marrom",
                    "Vermelho",
                    "Laranja",
                    "Amarelo",
                    "Azul",
                    "Violeta",
                    "Branco",
                ]

                for i, cb in enumerate(band_combos):
                    if i < count:
                        cb.grid(row=0, column=2 + i, padx=2, pady=10)
                        vals = []
                        if count == 4:
                            if i < 2:
                                vals = digits_colors
                            elif i == 2:
                                vals = multi_colors
                            else:
                                vals = tol_colors
                        elif count == 5:
                            if i < 3:
                                vals = digits_colors
                            elif i == 3:
                                vals = multi_colors
                            else:
                                vals = tol_colors
                        elif count == 6:
                            if i < 3:
                                vals = digits_colors
                            elif i == 3:
                                vals = multi_colors
                            elif i == 4:
                                vals = tol_colors
                            else:
                                vals = temp_colors

                        if is_search:
                            vals = [""] + vals

                        cb.configure(values=vals)
                        if cb.get() not in vals:
                            cb.set(vals[0] if vals else "")
                    else:
                        cb.grid_forget()

            band_count_menu.configure(command=update_bands)

            def toggle_method(*args):
                if method_var.get() == "Entrada Direta":
                    bands_frame.grid_forget()
                    direct_frame.grid(row=1, column=0, columnspan=4, sticky="ew")
                else:
                    direct_frame.grid_forget()
                    bands_frame.grid(row=1, column=0, columnspan=4, sticky="ew")
                    update_bands()

            method_menu.configure(command=toggle_method)
            toggle_method()

        elif category == "Resistor SMD":
            add_entry(
                0,
                0,
                "Código SMD:",
                "raw_value",
                placeholder="(ex: 103, 4702, 01C, 4R7)",
            )
            add_entry(0, 1, "Tolerância (ex: 1%):", "tolerance")
            add_entry(0, 2, "Encapsulamento (ex: 0805):", "component_type")

        elif category == "Capacitor PTH":
            add_entry(0, 0, "Capacitância (ex: 100nF):", "raw_value")
            add_entry(0, 1, "Tensão Máx (ex: 50V):", "voltage")
            add_entry(0, 2, "Encapsulamento/Tipo:", "component_type")

        elif category == "Capacitor SMD":
            add_entry(
                0, 0, "Código SMD:", "raw_value", placeholder="(ex: 104, 226, 47 16V)"
            )
            add_entry(0, 1, "Tensão Máx (ex: 50V):", "voltage")
            add_entry(0, 2, "Encapsulamento/Tipo:", "component_type")

        elif category == "Transistor":

            def on_tipo_change(val):
                if val in ["BJT", "Darlington"]:
                    pol_label.grid()
                    pol_combo.grid()
                    pol_vals = ["NPN", "PNP"]
                    if is_search:
                        pol_vals.insert(0, "")
                    pol_combo.configure(values=pol_vals)
                    if inputs["transistor_pol"].get() not in pol_vals:
                        inputs["transistor_pol"].set(pol_vals[0])
                elif val == "MOSFET":
                    pol_label.grid()
                    pol_combo.grid()
                    pol_vals = ["Canal N", "Canal P"]
                    if is_search:
                        pol_vals.insert(0, "")
                    pol_combo.configure(values=pol_vals)
                    if inputs["transistor_pol"].get() not in pol_vals:
                        inputs["transistor_pol"].set(pol_vals[0])
                elif val == "IGBT":
                    pol_label.grid_remove()
                    pol_combo.grid_remove()
                    inputs["transistor_pol"].set("")
                else:  # empty etc (for search)
                    pol_label.grid()
                    pol_combo.grid()
                    pol_vals = ["NPN", "PNP", "Canal N", "Canal P"]
                    if is_search:
                        pol_vals.insert(0, "")
                    pol_combo.configure(values=pol_vals)

            tipo_combo, tipo_label = add_combo(
                0,
                0,
                "Tipo:",
                "transistor_tipo",
                ["BJT", "MOSFET", "Darlington", "IGBT"],
                command=on_tipo_change,
            )
            pol_combo, pol_label = add_combo(
                0,
                1,
                "Polaridade:",
                "transistor_pol",
                ["NPN", "PNP", "Canal N", "Canal P"],
            )
            add_entry(0, 2, "Encapsulamento:", "component_type")
            add_entry(1, 0, "Tensão Máx (VCEO/VDS):", "voltage")
            add_entry(1, 1, "Corrente Máx (IC/ID):", "tolerance")

            # Trigger initial state
            on_tipo_change(inputs["transistor_tipo"].get())

        elif category == "Indutor":
            add_entry(0, 0, "Indutância (ex: 10µH):", "raw_value")
            add_entry(0, 1, "Corrente Máx (ex: 2A):", "tolerance")
            add_entry(0, 2, "Encapsulamento:", "component_type")

        elif category == "CI (Circuito Integrado)":
            add_entry(0, 0, "Função/Modelo (ex: NE555):", "raw_value")
            add_entry(0, 1, "Número de Pinos:", "tolerance")
            add_entry(0, 2, "Encapsulamento:", "component_type")

        elif category == "Optoacoplador":
            add_entry(0, 0, "Tensão Isolação (ex: 5kV):", "voltage")
            add_entry(0, 1, "Tipo Saída (Fototransistor):", "component_type")

        else:  # Outros
            add_entry(0, 0, "Descrição / Valor:", "raw_value")
            add_entry(0, 1, "Tipo / Encapsulamento:", "component_type")

        return inputs

    @staticmethod
    def extract_values(category_config, inputs):
        category = category_config.get("logic_type", "Outros")
        fields_json = category_config.get("fields", "[]")
        try:
            custom_fields = json.loads(fields_json)
        except:
            custom_fields = []

        """Extract standardized DB values from the dynamic UI widgets"""
        raw_val = ""
        voltage = ""
        tolerance = ""
        comp_type = ""

        # Helper to safely get value from CTkEntry or StringVar
        def get_val(key):
            if key in inputs:
                val = inputs[key].get().strip()
                return val
            return ""

        if category == "Resistor PTH":
            method = get_val("r_method")
            if method == "Entrada Direta":
                raw_val = get_val("raw_value")
                tolerance = get_val("tolerance")
                comp_type = get_val("component_type")
            elif method == "Cores (Bandas)":
                count = int(get_val("r_band_count") or 4)
                bands = [var.get() for var in inputs.get("r_bands", [])[:count]]
                raw_val = "CORES: " + "-".join([b for b in bands if b])
                comp_type = get_val("component_type")

        elif category == "Transistor":
            tipo = get_val("transistor_tipo")
            pol = get_val("transistor_pol")
            if tipo or pol:
                raw_val = f"{tipo} ({pol})".strip(" ()")
            voltage = get_val("voltage")
            tolerance = get_val("tolerance")
            comp_type = get_val("component_type")

        else:
            raw_val = get_val("raw_value")
            voltage = get_val("voltage")
            tolerance = get_val("tolerance")
            comp_type = get_val("component_type")

        return raw_val, voltage, tolerance, comp_type


class CategoryEditorDialog(ctk.CTkToplevel):
    def __init__(
        self, master, title="Adicionar Categoria", initial_name="", initial_fields=None
    ):
        super().__init__(master)
        self.title(title)
        self.geometry("400x500")
        self.result = (None, None)
        self.grab_set()

        self.name_label = ctk.CTkLabel(self, text="Nome da Categoria:")
        self.name_label.pack(pady=(10, 0))
        self.name_entry = ctk.CTkEntry(self, width=300)
        self.name_entry.pack(pady=5)
        if initial_name:
            self.name_entry.insert(0, initial_name)

        self.fields_label = ctk.CTkLabel(self, text="Campos Personalizados:")
        self.fields_label.pack(pady=(15, 0))

        self.fields_frame = ctk.CTkScrollableFrame(self, width=350, height=250)
        self.fields_frame.pack(pady=5, fill="both", expand=True)

        self.fields_entries = []

        if initial_fields:
            for field in initial_fields:
                self.add_field(field)

        self.add_btn = ctk.CTkButton(
            self, text="+ Adicionar Campo", command=self.add_field
        )
        self.add_btn.pack(pady=5)

        self.save_btn = ctk.CTkButton(self, text="Salvar", command=self.save)
        self.save_btn.pack(pady=15)

    def add_field(self, initial_value=""):
        row_frame = ctk.CTkFrame(self.fields_frame, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)
        entry = ctk.CTkEntry(row_frame, width=250, placeholder_text="Nome do Campo")
        entry.pack(side="left", padx=5)
        if initial_value:
            entry.insert(0, initial_value)
        del_btn = ctk.CTkButton(
            row_frame,
            text="X",
            width=30,
            fg_color="red",
            command=lambda f=row_frame, e=entry: self.remove_field(f, e),
        )
        del_btn.pack(side="left")
        self.fields_entries.append(entry)

    def remove_field(self, frame, entry):
        frame.destroy()
        if entry in self.fields_entries:
            self.fields_entries.remove(entry)

    def save(self):
        name = self.name_entry.get().strip()
        if not name:
            import tkinter.messagebox as messagebox

            messagebox.showwarning("Aviso", "Nome da categoria é obrigatório.")
            return
        fields = [e.get().strip() for e in self.fields_entries if e.get().strip()]
        import json

        self.result = (name, json.dumps(fields))
        self.destroy()

    def get_result(self):
        self.wait_window()
        return self.result


class CategoryManagerWindow(ctk.CTkToplevel):
    def __init__(self, master, on_close_callback):
        super().__init__(master)
        self.title("Gerenciar Categorias")
        self.geometry("400x500")
        self.on_close_callback = on_close_callback
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.label = ctk.CTkLabel(
            self, text="Gerenciar Categorias", font=ctk.CTkFont(size=20, weight="bold")
        )
        self.label.pack(pady=10)

        self.listbox_frame = ctk.CTkScrollableFrame(self)
        self.listbox_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=20, pady=10)

        self.add_btn = ctk.CTkButton(
            self.btn_frame, text="Adicionar", command=self.add_category
        )
        self.add_btn.pack(side="left", expand=True, padx=5)

        self.edit_btn = ctk.CTkButton(
            self.btn_frame, text="Editar", command=self.edit_category
        )
        self.edit_btn.pack(side="left", expand=True, padx=5)

        self.del_btn = ctk.CTkButton(
            self.btn_frame, text="Excluir", command=self.delete_category
        )
        self.del_btn.pack(side="left", expand=True, padx=5)

        self.selected_category = ctk.StringVar(value="")
        self.refresh_list()

    def refresh_list(self):
        for widget in self.listbox_frame.winfo_children():
            widget.destroy()

        import sqlite3
        from tkinter import messagebox

        categories = DatabaseHelper.get_categories()
        for cat in categories:
            name = cat[0]
            rb = ctk.CTkRadioButton(
                self.listbox_frame,
                text=name,
                variable=self.selected_category,
                value=name,
            )
            rb.pack(anchor="w", pady=5)

    def add_category(self):
        dialog = CategoryEditorDialog(self, title="Adicionar Categoria")
        name, fields_json = dialog.get_result()
        if not name:
            return

        name = name.strip()
        if name:
            import sqlite3
            from tkinter import messagebox

            try:
                conn = DatabaseHelper.get_connection()
                c = conn.cursor()
                c.execute(
                    "INSERT INTO categories (name, logic_type, fields_json) VALUES (?, ?, ?)",
                    (name, "Outros", fields_json),
                )
                conn.commit()
                self.refresh_list()
                self.on_close_callback()
            except sqlite3.IntegrityError:
                messagebox.showerror("Erro", "Esta categoria já existe.")
            finally:
                conn.close()

    def edit_category(self):
        old_name = self.selected_category.get()
        if not old_name:
            import tkinter.messagebox as messagebox

            messagebox.showwarning("Aviso", "Selecione uma categoria para editar.")
            return

        import sqlite3

        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        c.execute(
            "SELECT logic_type, fields_json FROM categories WHERE name = ?", (old_name,)
        )
        row = c.fetchone()
        conn.close()

        if row and row[0] != "Outros":
            # Standard category: Only allow rename
            dialog = ctk.CTkInputDialog(
                text=f"Novo nome para '{old_name}' (Campos são fixos para categorias base):",
                title="Renomear Categoria",
            )
            new_name = dialog.get_input()
            if not new_name:
                return
            new_name = new_name.strip()
            fields_json = row[1]
        else:
            # Custom category: allow full edit
            import json

            initial_fields = []
            if row and row[1]:
                try:
                    initial_fields = json.loads(row[1])
                except:
                    pass
            dialog = CategoryEditorDialog(
                self,
                title="Editar Categoria",
                initial_name=old_name,
                initial_fields=initial_fields,
            )
            new_name, fields_json = dialog.get_result()
            if not new_name:
                return
            new_name = new_name.strip()

        if new_name and new_name != old_name:
            import sqlite3
            from tkinter import messagebox

            conn = DatabaseHelper.get_connection()
            c = conn.cursor()
            try:
                c.execute(
                    "UPDATE categories SET name = ?, fields_json = ? WHERE name = ?",
                    (new_name, fields_json, old_name),
                )
                c.execute(
                    "UPDATE components SET category = ? WHERE category = ?",
                    (new_name, old_name),
                )
                conn.commit()
                self.selected_category.set(new_name)
                self.refresh_list()
                self.on_close_callback()
            except sqlite3.IntegrityError:
                messagebox.showerror("Erro", "Já existe uma categoria com este nome.")
            finally:
                conn.close()
        elif new_name == old_name:
            # Maybe just fields changed
            import sqlite3

            conn = DatabaseHelper.get_connection()
            c = conn.cursor()
            c.execute(
                "UPDATE categories SET fields_json = ? WHERE name = ?",
                (fields_json, old_name),
            )
            conn.commit()
            conn.close()
            self.on_close_callback()

    def delete_category(self):
        name = self.selected_category.get()
        if not name:
            import tkinter.messagebox as messagebox

            messagebox.showwarning("Aviso", "Selecione uma categoria para excluir.")
            return

        import sqlite3
        from tkinter import messagebox

        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        c.execute("SELECT count(*) FROM components WHERE category = ?", (name,))
        count = c.fetchone()[0]

        if count > 0:
            messagebox.showerror(
                "Erro",
                f"Não é possível excluir '{name}' pois existem {count} componentes usando esta categoria. Remova-os ou edite suas categorias primeiro.",
            )
            conn.close()
            return

        if messagebox.askyesno(
            "Confirmar", f"Tem certeza que deseja excluir a categoria '{name}'?"
        ):
            c.execute("DELETE FROM categories WHERE name = ?", (name,))
            conn.commit()
            self.selected_category.set("")
            self.refresh_list()
            self.on_close_callback()
        conn.close()

    def on_close(self):
        self.on_close_callback()
        self.destroy()


class DrawerRegistrationFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.label = ctk.CTkLabel(
            self,
            text="Gerenciamento de Gavetas",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.label.pack(pady=20, padx=20, anchor="w")

        self.form_frame = ctk.CTkFrame(self)
        self.form_frame.pack(pady=10, padx=20, fill="x")

        self.code_label = ctk.CTkLabel(
            self.form_frame, text="Código da Gaveta (4 dígitos):"
        )
        self.code_label.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        self.code_entry = ctk.CTkEntry(self.form_frame, width=200)
        self.code_entry.grid(row=0, column=1, padx=20, pady=20, sticky="w")

        self.cap_label = ctk.CTkLabel(self.form_frame, text="Número de Divisões:")
        self.cap_label.grid(row=1, column=0, padx=20, pady=20, sticky="w")

        self.cap_entry = ctk.CTkEntry(
            self.form_frame, width=200, placeholder_text="Ex: 5"
        )
        self.cap_entry.insert(0, "1")
        self.cap_entry.grid(row=1, column=1, padx=20, pady=20, sticky="w")

        self.submit_btn = ctk.CTkButton(
            self, text="Salvar Gaveta", command=self.save_drawer, height=40
        )
        self.submit_btn.pack(pady=10, padx=20, anchor="w")

        # Drawers list
        self.list_label = ctk.CTkLabel(
            self, text="Gavetas Existentes", font=ctk.CTkFont(size=18, weight="bold")
        )
        self.list_label.pack(pady=(20, 5), padx=20, anchor="w")

        self.list_frame = ctk.CTkScrollableFrame(self, height=300)
        self.list_frame.pack(pady=5, padx=20, fill="both", expand=True)

        self.editing_code = None
        self.load_drawers()

    def load_drawers(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        c.execute("SELECT door_code, capacity FROM drawers ORDER BY door_code")
        drawers = c.fetchall()
        conn.close()

        for idx, (code, cap) in enumerate(drawers):
            row_frame = ctk.CTkFrame(self.list_frame, fg_color=("gray85", "gray25"))
            row_frame.pack(fill="x", pady=2, padx=5)

            ctk.CTkLabel(row_frame, text=f"Gaveta {code} ({cap} divisões)").pack(
                side="left", padx=10, pady=5
            )

            del_btn = ctk.CTkButton(
                row_frame,
                text="Excluir",
                width=80,
                fg_color="red",
                hover_color="darkred",
                command=lambda c=code: self.delete_drawer(c),
            )
            del_btn.pack(side="right", padx=10, pady=5)

            edit_btn = ctk.CTkButton(
                row_frame,
                text="Editar",
                width=80,
                command=lambda c=code, cap=cap: self.edit_drawer(c, cap),
            )
            edit_btn.pack(side="right", padx=5, pady=5)

    def edit_drawer(self, code, capacity):
        self.editing_code = code
        self.code_entry.delete(0, "end")
        self.code_entry.insert(0, code)
        self.cap_entry.delete(0, "end")
        self.cap_entry.insert(0, str(capacity))
        self.submit_btn.configure(text="Atualizar Gaveta")

    def delete_drawer(self, code):
        if not messagebox.askyesno(
            "Confirmar Exclusão",
            "Tem certeza que deseja excluir esta gaveta?\n\nATENÇÃO: Todos os componentes contidos nela também serão permanentemente removidos.",
        ):
            return

        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        try:
            c.execute(
                "DELETE FROM components WHERE subdivision_id IN (SELECT id FROM subdivisions WHERE drawer_code = ?)",
                (code,),
            )
            c.execute("DELETE FROM subdivisions WHERE drawer_code = ?", (code,))
            c.execute("DELETE FROM drawers WHERE door_code = ?", (code,))
            conn.commit()
            messagebox.showinfo(
                "Sucesso",
                f"Gaveta {code} e seus componentes foram excluídos com sucesso.",
            )
            self.load_drawers()
        except Exception as e:
            messagebox.showerror(
                "Erro", f"Ocorreu um erro ao excluir a gaveta: {str(e)}"
            )
        finally:
            conn.close()

    def save_drawer(self):
        code = self.code_entry.get().strip()
        capacity_str = self.cap_entry.get().strip()

        if len(code) != 4 or not code.isdigit():
            messagebox.showerror(
                "Erro", "O código da gaveta deve ter exatamente 4 dígitos numéricos."
            )
            return

        if not capacity_str.isdigit() or int(capacity_str) < 1:
            messagebox.showerror(
                "Erro", "A capacidade de divisões deve ser um número inteiro positivo."
            )
            return

        capacity = int(capacity_str)

        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        try:
            if self.editing_code:
                # Editing existing drawer
                if self.editing_code != code:
                    # Rename drawer (door_code). Need to check if new code exists
                    c.execute("SELECT 1 FROM drawers WHERE door_code = ?", (code,))
                    if c.fetchone():
                        messagebox.showerror(
                            "Erro", f"Já existe uma gaveta com o código {code}."
                        )
                        return
                    c.execute(
                        "UPDATE subdivisions SET drawer_code = ? WHERE drawer_code = ?",
                        (code, self.editing_code),
                    )
                    c.execute(
                        "UPDATE drawers SET door_code = ?, capacity = ? WHERE door_code = ?",
                        (code, capacity, self.editing_code),
                    )
                else:
                    c.execute(
                        "UPDATE drawers SET capacity = ? WHERE door_code = ?",
                        (capacity, self.editing_code),
                    )

                # Manage subdivisions
                c.execute(
                    "SELECT count(*) FROM subdivisions WHERE drawer_code = ?", (code,)
                )
                current_subs = c.fetchone()[0]

                if capacity > current_subs:
                    for i in range(current_subs + 1, capacity + 1):
                        c.execute(
                            "INSERT INTO subdivisions (drawer_code, subdivision_index) VALUES (?, ?)",
                            (code, i),
                        )
                elif capacity < current_subs:
                    c.execute(
                        """
                        SELECT count(*) FROM components c
                        JOIN subdivisions s ON c.subdivision_id = s.id
                        WHERE s.drawer_code = ? AND s.subdivision_index > ?
                    """,
                        (code, capacity),
                    )
                    if c.fetchone()[0] > 0:
                        messagebox.showerror(
                            "Erro",
                            "Existem componentes nas divisões que seriam removidas. Por favor, mova ou exclua esses componentes antes de reduzir a capacidade.",
                        )
                        return
                    else:
                        c.execute(
                            "DELETE FROM subdivisions WHERE drawer_code = ? AND subdivision_index > ?",
                            (code, capacity),
                        )

                conn.commit()
                messagebox.showinfo("Sucesso", f"Gaveta {code} atualizada com sucesso!")
                self.editing_code = None
                self.submit_btn.configure(text="Salvar Gaveta")
            else:
                # New drawer
                c.execute(
                    "INSERT INTO drawers (door_code, capacity) VALUES (?, ?)",
                    (code, capacity),
                )
                for i in range(1, capacity + 1):
                    c.execute(
                        "INSERT INTO subdivisions (drawer_code, subdivision_index) VALUES (?, ?)",
                        (code, i),
                    )
                conn.commit()
                messagebox.showinfo(
                    "Sucesso",
                    f"Gaveta {code} registrada com sucesso com {capacity} divisões!",
                )

            self.code_entry.delete(0, "end")
            self.cap_entry.delete(0, "end")
            self.cap_entry.insert(0, "1")
            self.load_drawers()

        except sqlite3.IntegrityError:
            messagebox.showerror("Erro", f"Gaveta {code} já existe no sistema.")
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro inesperado: {str(e)}")
        finally:
            conn.close()


class ComponentRegistrationFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.label = ctk.CTkLabel(
            self,
            text="Registro de Componente",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.label.grid(row=0, column=0, columnspan=2, pady=20, padx=20, sticky="w")

        self.container = ctk.CTkFrame(self)
        self.container.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")

        # Target Drawer (Hierarchical Step 1)
        self.drawer_label = ctk.CTkLabel(self.container, text="Selecione a Gaveta:")
        self.drawer_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")

        self.drawer_var = ctk.StringVar(value="")
        self.drawer_menu = ctk.CTkOptionMenu(
            self.container,
            variable=self.drawer_var,
            values=[],
            command=self.on_drawer_select,
            width=200,
        )
        self.drawer_menu.grid(row=0, column=1, padx=20, pady=10, sticky="w")

        # Target Slot (Hierarchical Step 2)
        self.slot_label = ctk.CTkLabel(self.container, text="Selecione a Divisão:")
        self.slot_label.grid(row=1, column=0, padx=20, pady=10, sticky="w")

        self.slot_options = []
        self.slot_mapping = {}
        self.slot_var = ctk.StringVar(value="")
        self.slot_menu = ctk.CTkOptionMenu(
            self.container, variable=self.slot_var, values=[], width=400, command=self.on_slot_select
        )
        self.slot_menu.grid(row=1, column=1, padx=20, pady=10, sticky="w")

        # Component Base Fields
        self.name_label = ctk.CTkLabel(self.container, text="Nome do Componente:")
        self.name_label.grid(row=2, column=0, padx=20, pady=10, sticky="w")
        self.name_entry = ctk.CTkEntry(self.container, width=300)
        self.name_entry.grid(row=2, column=1, padx=20, pady=10, sticky="w")

        self.qty_label = ctk.CTkLabel(self.container, text="Quantidade:")
        self.qty_label.grid(row=3, column=0, padx=20, pady=10, sticky="w")
        self.qty_entry = ctk.CTkEntry(self.container, width=150)
        self.qty_entry.insert(0, "1")
        self.qty_entry.grid(row=3, column=1, padx=20, pady=10, sticky="w")

        # Category Selection
        self.cat_label = ctk.CTkLabel(self.container, text="Categoria:")
        self.cat_label.grid(row=4, column=0, padx=20, pady=10, sticky="w")

        self.cat_logic_map = {}
        self.cat_var = ctk.StringVar(value="")
        self.cat_menu = ctk.CTkOptionMenu(
            self.container,
            variable=self.cat_var,
            values=[],
            command=self.on_category_change,
        )
        self.cat_menu.grid(row=4, column=1, padx=20, pady=10, sticky="w")

        # Dynamic Frame Container
        self.dynamic_frame = ctk.CTkFrame(self.container, fg_color=("gray90", "gray13"))
        self.dynamic_frame.grid(
            row=5, column=0, columnspan=2, padx=20, pady=20, sticky="nsew"
        )

        self.dynamic_inputs = {}
        self.update_categories()

        self.submit_btn = ctk.CTkButton(
            self, text="Salvar Componente", command=self.save_component, height=40
        )
        self.submit_btn.grid(
            row=2, column=0, columnspan=2, pady=20, padx=20, sticky="w"
        )

        self.on_category_change(self.cat_var.get())

    def update_categories(self):
        rows = DatabaseHelper.get_categories()
        self.cat_logic_map = {
            row[0]: {"logic_type": row[1], "fields": row[2]} for row in rows
        }
        cat_names = list(self.cat_logic_map.keys())
        if cat_names:
            self.cat_menu.configure(values=cat_names)
            if self.cat_var.get() not in cat_names:
                self.cat_var.set(cat_names[0])
            self.on_category_change(self.cat_var.get())
        else:
            self.cat_menu.configure(values=["-"])
            self.cat_var.set("-")

    def update_drawers(self):
        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        c.execute("SELECT door_code FROM drawers ORDER BY door_code")
        drawers = c.fetchall()
        conn.close()

        drawer_list = [d[0] for d in drawers]

        if drawer_list:
            self.drawer_menu.configure(values=drawer_list)
            self.drawer_var.set(drawer_list[0])
            self.on_drawer_select(drawer_list[0])
        else:
            self.drawer_menu.configure(values=["Nenhuma gaveta"])
            self.drawer_var.set("Nenhuma gaveta")
            self.slot_menu.configure(values=["-"])
            self.slot_var.set("-")

    def on_drawer_select(self, drawer_code):
        if not drawer_code or drawer_code == "Nenhuma gaveta":
            return

        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        c.execute(
            """
            SELECT s.id, s.subdivision_index, c.id, c.name, c.quantity
            FROM subdivisions s
            LEFT JOIN components c ON s.id = c.subdivision_id
            WHERE s.drawer_code = ?
            ORDER BY s.subdivision_index
        """,
            (drawer_code,),
        )
        slots_data = c.fetchall()
        conn.close()

        self.slot_options = []
        self.slot_mapping = {}

        for slot in slots_data:
            sub_id, index, comp_id, comp_name, comp_qty = slot

            if comp_id:
                label = f"Divisão {index} - Ocupado: {comp_name} (Qtd: {comp_qty})"
            else:
                label = f"Divisão {index} - Vazio"

            self.slot_options.append(label)
            self.slot_mapping[label] = {"subdivision_id": sub_id, "comp_id": comp_id}

        if self.slot_options:
            self.slot_menu.configure(values=self.slot_options)
            self.slot_var.set(self.slot_options[0])
            self.on_slot_select(self.slot_options[0])
        else:
            self.slot_menu.configure(values=["Sem divisões"])
            self.slot_var.set("Sem divisões")

    def on_slot_select(self, slot_label):
        if slot_label not in self.slot_mapping:
            return
            
        comp_id = self.slot_mapping[slot_label]["comp_id"]
        if not comp_id:
            # Clear form
            self.name_entry.delete(0, "end")
            self.qty_entry.delete(0, "end")
            self.qty_entry.insert(0, "1")
            return
            
        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        c.execute("SELECT name, quantity, category, raw_value, voltage, tolerance, component_type FROM components WHERE id = ?", (comp_id,))
        comp = c.fetchone()
        conn.close()
        
        if comp:
            self.name_entry.delete(0, "end")
            self.name_entry.insert(0, comp[0])
            self.qty_entry.delete(0, "end")
            self.qty_entry.insert(0, str(comp[1]))
            
            self.cat_var.set(comp[2])
            self.on_category_change(comp[2])
            
            cat_config = getattr(self, "cat_logic_map", {}).get(comp[2], {"logic_type": "Outros", "fields": "[]"})
            
            # Helper to map raw values back to dynamic inputs
            import ast
            try:
                fields = ast.literal_eval(cat_config["fields"])
            except:
                fields = []
                
            for field in fields:
                field_name = field["name"]
                if field_name == "Código SMD" or field_name == "Capacitância" or field_name == "Indutância":
                    var = self.dynamic_inputs.get(field_name)
                    if var:
                        if isinstance(var, ctk.StringVar): var.set(comp[3] if comp[3] else "")
                        elif isinstance(var, ctk.CTkEntry): 
                            var.delete(0, "end")
                            var.insert(0, comp[3] if comp[3] else "")
                elif field_name == "Tensão Máx (VCEO/VDS)" or field_name == "Tensão":
                    var = self.dynamic_inputs.get(field_name)
                    if var:
                        if isinstance(var, ctk.StringVar): var.set(comp[4] if comp[4] else "")
                elif field_name == "Corrente Máx (IC/ID)" or field_name == "Tolerância":
                    var = self.dynamic_inputs.get(field_name)
                    if var:
                        if isinstance(var, ctk.StringVar): var.set(comp[5] if comp[5] else "")
                elif field_name == "Encapsulamento" or field_name == "Tipo":
                    var = self.dynamic_inputs.get(field_name)
                    if var:
                        if isinstance(var, ctk.StringVar): var.set(comp[6] if comp[6] else "")
                elif field_name == "Bandas":
                    if comp[3] and "CORES:" in comp[3]:
                        colors_str = comp[3].replace("CORES: ", "")
                        bands = colors_str.split("-")
                        count_var = self.dynamic_inputs.get("Bandas_count")
                        if count_var:
                            count_var.set(str(len(bands)))
                            
                        band_vars = self.dynamic_inputs.get("Bandas_vars", [])
                        for i, color in enumerate(bands):
                            if i < len(band_vars):
                                band_vars[i].set(color)

    def on_category_change(self, category):
        cat_config = getattr(self, "cat_logic_map", {}).get(
            category, {"logic_type": "Outros", "fields": "[]"}
        )
        self.dynamic_inputs = CategoryUIBuilder.build_fields(
            self.dynamic_frame, cat_config, is_search=False
        )

    def save_component(self):
        name = self.name_entry.get().strip()
        category = self.cat_var.get()
        qty = self.qty_entry.get().strip()
        slot_label = self.slot_var.get()

        if not name:
            messagebox.showerror("Erro", "O Nome do Componente é obrigatório.")
            return

        if not qty.isdigit():
            messagebox.showerror("Erro", "A Quantidade deve ser um número inteiro.")
            return

        if slot_label not in self.slot_mapping:
            messagebox.showerror("Erro", "Por favor, selecione uma divisão válida.")
            return

        slot_info = self.slot_mapping[slot_label]
        subdivision_id = slot_info["subdivision_id"]
        old_comp_id = slot_info["comp_id"]

        cat_config = getattr(self, "cat_logic_map", {}).get(
            category, {"logic_type": "Outros", "fields": "[]"}
        )
        raw_val, voltage, tolerance, comp_type = CategoryUIBuilder.extract_values(
            cat_config, self.dynamic_inputs
        )

        logic_type = cat_config.get("logic_type", "Outros")
        normalized_val = None

        if logic_type == "Resistor SMD" and raw_val:
            val, tol = SMDDecoder.decode_resistor_smd(raw_val)
            if val is not None:
                normalized_val = val
            if tol and not tolerance:
                tolerance = tol

        elif logic_type == "Capacitor SMD" and raw_val:
            val, volt = SMDDecoder.decode_capacitor_smd(raw_val)
            if val is not None:
                normalized_val = val
            if volt and not voltage:
                voltage = volt

        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        try:
            if old_comp_id:
                c.execute("DELETE FROM components WHERE id = ?", (old_comp_id,))

            c.execute(
                """
                INSERT INTO components 
                (name, category, raw_value, quantity, voltage, tolerance, component_type, subdivision_id, normalized_base_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    name,
                    category,
                    raw_val,
                    int(qty),
                    voltage,
                    tolerance,
                    comp_type,
                    subdivision_id,
                    normalized_val,
                ),
            )
            conn.commit()
            messagebox.showinfo("Sucesso", f"Componente {name} salvo com sucesso!")
            
            if hasattr(self.master, 'search_frame'):
                self.master.search_frame.perform_search()

            # Reset UI
            self.name_entry.delete(0, "end")
            self.qty_entry.delete(0, "end")
            self.qty_entry.insert(0, "1")
            self.on_category_change(category)
            self.on_drawer_select(self.drawer_var.get())

        except Exception as e:
            messagebox.showerror("Erro ao salvar componente", f"Detalhes: {str(e)}")
        finally:
            conn.close()


class SearchFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")

        self.label = ctk.CTkLabel(
            self, text="Pesquisa Paramétrica", font=ctk.CTkFont(size=24, weight="bold")
        )
        self.label.pack(pady=10, padx=20, anchor="w")

        # Main Search Area
        self.search_container = ctk.CTkFrame(self)
        self.search_container.pack(pady=10, padx=20, fill="x")

        self.search_entry = ctk.CTkEntry(
            self.search_container,
            width=300,
            placeholder_text="Pesquisar por Nome ou Valor...",
        )
        self.search_entry.grid(row=0, column=0, padx=20, pady=15, sticky="w")

        self.cat_logic_map = {}
        self.cat_var = ctk.StringVar(value="Todos")
        self.cat_menu = ctk.CTkOptionMenu(
            self.search_container,
            variable=self.cat_var,
            values=["Todos"],
            command=self.on_search_category_change,
        )
        self.cat_menu.grid(row=0, column=1, padx=20, pady=15, sticky="w")

        self.search_btn = ctk.CTkButton(
            self.search_container, text="Pesquisar", command=self.perform_search
        )
        self.search_btn.grid(row=0, column=2, padx=20, pady=15, sticky="w")

        # Dynamic Filters Area (Using same UI Builder for EXACT match)
        self.filters_frame = ctk.CTkFrame(self.search_container, fg_color="transparent")
        self.filters_frame.grid(
            row=1, column=0, columnspan=3, padx=20, pady=(0, 10), sticky="ew"
        )

        self.dynamic_inputs = {}
        self.update_categories()

        # Grid using ttk.Treeview
        self.tree_frame = ctk.CTkFrame(self)
        self.tree_frame.pack(pady=10, padx=20, fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#2b2b2b",
            foreground="white",
            rowheight=25,
            fieldbackground="#2b2b2b",
            bordercolor="#343638",
            borderwidth=0,
        )
        style.map("Treeview", background=[("selected", "#1f538d")])

        style.configure(
            "Treeview.Heading", background="#565b5e", foreground="white", relief="flat"
        )
        style.map("Treeview.Heading", background=[("active", "#3484F0")])

        columns = (
            "Nome",
            "Categoria",
            "Valor/Desc",
            "Tensão",
            "Tol/Corrente",
            "Tipo/Encaps.",
            "Qtd",
            "Localização",
        )
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=110)

        self.tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.scrollbar = ttk.Scrollbar(
            self.tree_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscroll=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y", pady=5)
        
        self.btn_adjust = ctk.CTkButton(self, text="Ajustar Estoque Selecionado", command=self.quick_adjust_stock)
        self.btn_adjust.pack(pady=(0, 10))
        
        self.tree.bind("<Double-1>", lambda e: self.quick_adjust_stock())

    def quick_adjust_stock(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione um componente na tabela primeiro.")
            return
            
        item = selected[0]
        tags = self.tree.item(item, "tags")
        if not tags:
            return
            
        comp_id = tags[0]
        values = self.tree.item(item, "values")
        comp_name = values[0]
        current_qty = int(values[6])
        
        StockAdjustmentModal(self, comp_id, comp_name, current_qty, self.perform_search)

    def update_categories(self):
        rows = DatabaseHelper.get_categories()
        self.cat_logic_map = {
            row[0]: {"logic_type": row[1], "fields": row[2]} for row in rows
        }
        cat_names = ["Todos"] + list(self.cat_logic_map.keys())
        self.cat_menu.configure(values=cat_names)
        if self.cat_var.get() not in cat_names:
            self.cat_var.set("Todos")
        self.on_search_category_change(self.cat_var.get())

    def on_search_category_change(self, category):
        if category == "Todos":
            for widget in self.filters_frame.winfo_children():
                widget.destroy()
            self.dynamic_inputs = {}
        else:
            cat_config = getattr(self, "cat_logic_map", {}).get(
                category, {"logic_type": "Outros", "fields": "[]"}
            )
            self.dynamic_inputs = CategoryUIBuilder.build_fields(
                self.filters_frame, cat_config, is_search=True
            )

    def perform_search(self):
        query_text = self.search_entry.get().strip()
        category = self.cat_var.get()

        conn = DatabaseHelper.get_connection()

        sql = """
            SELECT c.id, c.name, c.category, c.raw_value, c.voltage, c.tolerance, c.component_type, c.quantity, 
                   s.drawer_code, s.subdivision_index, c.normalized_base_value
            FROM components c
            JOIN subdivisions s ON c.subdivision_id = s.id
            WHERE 1=1
        """
        params = []

        parsed_query = SMDDecoder.parse_search_query(query_text) if query_text else None

        if query_text:
            if parsed_query is not None:
                margin = abs(parsed_query * 0.01) if parsed_query != 0 else 1e-12
                sql += " AND (c.name LIKE ? OR c.raw_value LIKE ? OR (c.normalized_base_value >= ? AND c.normalized_base_value <= ?))"
                params.extend(
                    [
                        f"%{query_text}%",
                        f"%{query_text}%",
                        parsed_query - margin,
                        parsed_query + margin,
                    ]
                )
            else:
                sql += " AND (c.name LIKE ? OR c.raw_value LIKE ?)"
                params.extend([f"%{query_text}%", f"%{query_text}%"])

        if category != "Todos":
            sql += " AND c.category = ?"
            params.append(category)

            # Extract formatted values using the shared builder
            cat_config = getattr(self, "cat_logic_map", {}).get(
                category, {"logic_type": "Outros", "fields": "[]"}
            )
            raw_val, voltage, tolerance, comp_type = CategoryUIBuilder.extract_values(
                cat_config, self.dynamic_inputs
            )

            if raw_val and "CORES:" not in raw_val:
                parsed_raw = SMDDecoder.parse_search_query(raw_val)
                if parsed_raw is not None:
                    margin = abs(parsed_raw * 0.01) if parsed_raw != 0 else 1e-12
                    sql += " AND (c.raw_value LIKE ? OR (c.normalized_base_value >= ? AND c.normalized_base_value <= ?))"
                    params.extend(
                        [f"%{raw_val}%", parsed_raw - margin, parsed_raw + margin]
                    )
                else:
                    sql += " AND c.raw_value LIKE ?"
                    params.append(f"%{raw_val}%")
            elif "CORES:" in raw_val and len(raw_val) > 6:
                sql += " AND c.raw_value LIKE ?"
                params.append(f"%{raw_val}%")

            if voltage:
                sql += " AND c.voltage LIKE ?"
                params.append(f"%{voltage}%")
            if tolerance:
                sql += " AND c.tolerance LIKE ?"
                params.append(f"%{tolerance}%")
            if comp_type:
                sql += " AND c.component_type LIKE ?"
                params.append(f"%{comp_type}%")

        try:
            df = pd.read_sql_query(sql, conn, params=params)
        except Exception as e:
            messagebox.showerror(
                "Erro de Pesquisa", f"Erro no banco de dados:\n{str(e)}"
            )
            return
        finally:
            conn.close()

        for item in self.tree.get_children():
            self.tree.delete(item)

        if df is not None and not df.empty:
            try:
                df.fillna("-", inplace=True)

                def format_location(row):
                    try:
                        idx = int(row["subdivision_index"])
                        drw = str(row["drawer_code"])
                        return drw if idx == 1 else f"{drw}-{idx}"
                    except:
                        return "Erro Loc."

                df["Location"] = df.apply(format_location, axis=1)

                for _, row in df.iterrows():
                    try:
                        cat = str(row["category"])
                        raw_val = str(row["raw_value"])
                        norm_val = row.get("normalized_base_value")

                        if (
                            norm_val != "-"
                            and not pd.isna(norm_val)
                            and norm_val is not None
                        ):
                            if cat == "Resistor SMD":
                                formatted = SMDDecoder.format_resistance(norm_val)
                                if formatted:
                                    raw_val = f"{raw_val} = {formatted}"
                            elif cat == "Capacitor SMD":
                                formatted = SMDDecoder.format_capacitance(norm_val)
                                if formatted:
                                    raw_val = f"{raw_val} = {formatted}"
                        elif cat == "Resistor PTH" and raw_val.startswith("CORES: "):
                            colors_str = raw_val.replace("CORES: ", "")
                            bands = colors_str.split("-")
                            formatted = PTHResistorCalculator.calculate(bands)
                            if formatted:
                                raw_val = formatted

                        self.tree.insert(
                            "",
                            "end",
                            values=(
                                str(row["name"]),
                                cat,
                                raw_val,
                                str(row["voltage"]),
                                str(row["tolerance"]),
                                str(row["component_type"]),
                                str(row["quantity"]),
                                str(row["Location"]),
                            ),
                            tags=(str(row["id"]),)
                        )
                    except Exception as tree_err:
                        continue
            except Exception as e:
                error_trace = traceback.format_exc()
                messagebox.showerror(
                    "Erro de Renderização",
                    f"Ocorreu um erro ao formatar os resultados:\n{str(e)}",
                )


class StockAdjustmentModal(ctk.CTkToplevel):
    def __init__(self, master, comp_id, comp_name, current_qty, callback):
        super().__init__(master)
        self.title("Ajustar Estoque")
        self.geometry("350x250")
        self.grab_set()
        
        self.comp_id = comp_id
        self.current_qty = current_qty
        self.callback = callback
        
        ctk.CTkLabel(self, text=f"Componente: {comp_name}", font=ctk.CTkFont(weight="bold")).pack(pady=(20, 10))
        ctk.CTkLabel(self, text=f"Estoque Atual: {current_qty}").pack()
        
        self.qty_var = ctk.StringVar(value="0")
        
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(pady=15)
        
        btn_minus = ctk.CTkButton(frame, text="-1", width=40, command=lambda: self.adjust_var(-1))
        btn_minus.grid(row=0, column=0, padx=5)
        
        self.entry = ctk.CTkEntry(frame, textvariable=self.qty_var, width=60, justify="center")
        self.entry.grid(row=0, column=1, padx=5)
        
        btn_plus = ctk.CTkButton(frame, text="+1", width=40, command=lambda: self.adjust_var(1))
        btn_plus.grid(row=0, column=2, padx=5)
        
        btn_confirm = ctk.CTkButton(self, text="Confirmar Ajuste", command=self.save)
        btn_confirm.pack(pady=10)
        
    def adjust_var(self, amount):
        try:
            val = int(self.qty_var.get())
        except:
            val = 0
        self.qty_var.set(str(val + amount))
        
    def save(self):
        try:
            adj = int(self.qty_var.get())
        except:
            messagebox.showerror("Erro", "Quantidade inválida.")
            return
            
        if adj == 0:
            self.destroy()
            return
            
        new_qty = max(0, self.current_qty + adj)
        
        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        c.execute("UPDATE components SET quantity = ? WHERE id = ?", (new_qty, self.comp_id))
        conn.commit()
        conn.close()
        
        self.callback()
        self.destroy()

class CalculatorsModal(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Calculadoras Eletrônicas")
        self.geometry("550x400")
        self.grab_set()
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(expand=True, fill="both", padx=10, pady=10)
        
        self.tabview.add("Resistor PTH")
        self.tabview.add("Resistor SMD")
        self.tabview.add("Capacitor SMD")
        
        self.build_pth_tab()
        self.build_smd_res_tab()
        self.build_smd_cap_tab()
        
    def build_pth_tab(self):
        tab = self.tabview.tab("Resistor PTH")
        
        top_frame = ctk.CTkFrame(tab, fg_color="transparent")
        top_frame.pack(pady=10)
        
        ctk.CTkLabel(top_frame, text="Bandas:").grid(row=0, column=0, padx=5)
        self.band_count_var = ctk.StringVar(value="4")
        menu = ctk.CTkOptionMenu(top_frame, variable=self.band_count_var, values=["4", "5", "6"], width=60, command=self.update_pth_bands)
        menu.grid(row=0, column=1, padx=5)
        
        self.bands_frame = ctk.CTkFrame(tab, fg_color="transparent")
        self.bands_frame.pack(pady=10)
        
        self.band_vars = []
        self.band_combos = []
        
        colors = ["Preto", "Marrom", "Vermelho", "Laranja", "Amarelo", "Verde", "Azul", "Violeta", "Cinza", "Branco", "Dourado", "Prateado"]
        
        for i in range(6):
            var = ctk.StringVar(value=colors[0])
            self.band_vars.append(var)
            cb = ctk.CTkOptionMenu(self.bands_frame, variable=var, values=colors, width=80, command=self.calc_pth)
            self.band_combos.append(cb)
            
        self.result_pth = ctk.CTkLabel(tab, text="-", font=ctk.CTkFont(size=24, weight="bold"))
        self.result_pth.pack(pady=20)
        
        self.update_pth_bands()
        
    def update_pth_bands(self, *args):
        count = int(self.band_count_var.get())
        
        digits_colors = ["Preto", "Marrom", "Vermelho", "Laranja", "Amarelo", "Verde", "Azul", "Violeta", "Cinza", "Branco"]
        multi_colors = ["Preto", "Marrom", "Vermelho", "Laranja", "Amarelo", "Verde", "Azul", "Violeta", "Cinza", "Branco", "Dourado", "Prateado"]
        tol_colors = ["Marrom", "Vermelho", "Verde", "Azul", "Violeta", "Cinza", "Dourado", "Prateado"]
        temp_colors = ["Marrom", "Vermelho", "Laranja", "Amarelo", "Azul", "Violeta", "Branco"]
        
        for i, cb in enumerate(self.band_combos):
            if i < count:
                cb.grid(row=0, column=i, padx=2, pady=10)
                vals = []
                if count == 4:
                    if i < 2: vals = digits_colors
                    elif i == 2: vals = multi_colors
                    else: vals = tol_colors
                elif count == 5:
                    if i < 3: vals = digits_colors
                    elif i == 3: vals = multi_colors
                    else: vals = tol_colors
                elif count == 6:
                    if i < 3: vals = digits_colors
                    elif i == 3: vals = multi_colors
                    elif i == 4: vals = tol_colors
                    else: vals = temp_colors
                    
                cb.configure(values=vals)
                if cb.get() not in vals:
                    cb.set(vals[0] if vals else "")
            else:
                cb.grid_forget()
        self.calc_pth()
        
    def calc_pth(self, *args):
        count = int(self.band_count_var.get())
        bands = [v.get() for v in self.band_vars[:count]]
        res = PTHResistorCalculator.calculate(bands)
        self.result_pth.configure(text=res if res else "Inválido")
        
    def build_smd_res_tab(self):
        tab = self.tabview.tab("Resistor SMD")
        ctk.CTkLabel(tab, text="Código SMD (ex: 103, 4R7):").pack(pady=(20, 5))
        
        var = ctk.StringVar()
        entry = ctk.CTkEntry(tab, textvariable=var, width=150, justify="center")
        entry.pack(pady=5)
        
        result_lbl = ctk.CTkLabel(tab, text="-", font=ctk.CTkFont(size=24, weight="bold"))
        result_lbl.pack(pady=20)
        
        def calc(*args):
            val, tol = SMDDecoder.decode_resistor_smd(var.get())
            if val is not None:
                res = SMDDecoder.format_resistance(val)
                result_lbl.configure(text=f"{res} {tol if tol else ''}".strip())
            else:
                result_lbl.configure(text="Inválido")
                
        var.trace_add("write", calc)
        
    def build_smd_cap_tab(self):
        tab = self.tabview.tab("Capacitor SMD")
        ctk.CTkLabel(tab, text="Código SMD (ex: 104, 476):").pack(pady=(20, 5))
        
        var = ctk.StringVar()
        entry = ctk.CTkEntry(tab, textvariable=var, width=150, justify="center")
        entry.pack(pady=5)
        
        result_lbl = ctk.CTkLabel(tab, text="-", font=ctk.CTkFont(size=24, weight="bold"))
        result_lbl.pack(pady=20)
        
        def calc(*args):
            val, v = SMDDecoder.decode_capacitor_smd(var.get())
            if val is not None:
                res = SMDDecoder.format_capacitance(val)
                result_lbl.configure(text=f"{res} {v if v else ''}".strip())
            else:
                result_lbl.configure(text="Inválido")
                
        var.trace_add("write", calc)



import json
import os

class ReleaseNotesModal(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Novidades da Versão")
        self.geometry("600x450")
        self.grab_set()

        lbl_title = ctk.CTkLabel(self, text="O que há de novo?", font=ctk.CTkFont(size=24, weight="bold"))
        lbl_title.pack(pady=(20, 10))

        textbox = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont(size=14))
        textbox.pack(expand=True, fill="both", padx=20, pady=(0, 20))
        
        changelog = """
## v1.0.5
* Correção de carregamento de dados nas gavetas (edição de componentes agora preenche os dados corretamente).
* Sincronização corrigida na tela de pesquisa paramétrica.
* Adicionado painel de novidades e registro de versão.

## v1.0.4
* Adicionadas ferramentas de Calculadora Eletrônica (Resistor PTH, Resistor SMD, Capacitor SMD).
* Adicionado ajuste rápido de estoque (+ / -) direto na aba de Pesquisa via duplo-clique.

## v1.0.3
* Calculadora de códigos de cores para resistores PTH e exibição formatada.
* Correções no gerenciamento de gavetas e salvamento de componentes.
"""
        textbox.insert("0.0", changelog.strip())
        textbox.configure(state="disabled")
        
        btn_close = ctk.CTkButton(self, text="Fechar", command=self.destroy)
        btn_close.pack(pady=(0, 20))


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Configure window
        self.title("Inventário de Componentes v1.0.5")
        self.geometry("1400x800")

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        DatabaseHelper.init_db()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.sidebar, text="Inventário", font=ctk.CTkFont(size=24, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))

        self.btn_drawer = ctk.CTkButton(
            self.sidebar, text="Registrar Gaveta", command=self.show_drawer_frame
        )
        self.btn_drawer.grid(row=1, column=0, padx=20, pady=10)

        self.btn_comp = ctk.CTkButton(
            self.sidebar, text="Registrar Componente", command=self.show_comp_frame
        )
        self.btn_comp.grid(row=2, column=0, padx=20, pady=10)

        self.btn_search = ctk.CTkButton(
            self.sidebar, text="Pesquisar Componentes", command=self.show_search_frame
        )
        self.btn_search.grid(row=3, column=0, padx=20, pady=10)

        self.btn_manage_cat = ctk.CTkButton(
            self.sidebar,
            text="Gerenciar Categorias",
            command=self.show_category_manager,
        )
        self.btn_manage_cat.grid(row=4, column=0, padx=20, pady=10)
        
        self.btn_calculators = ctk.CTkButton(
            self.sidebar,
            text="Calculadoras",
            command=self.show_calculators,
            fg_color="#8B0000",
            hover_color="#A52A2A"
        )
        self.btn_calculators.grid(row=5, column=0, padx=20, pady=10)
        
        self.btn_changelog = ctk.CTkButton(
            self.sidebar,
            text="Novidades da Versão",
            command=self.show_changelog,
            fg_color="#006400",
            hover_color="#008000"
        )
        self.btn_changelog.grid(row=6, column=0, padx=20, pady=(10, 30), sticky="s")

        self.drawer_frame = DrawerRegistrationFrame(self)
        self.comp_frame = ComponentRegistrationFrame(self)
        self.search_frame = SearchFrame(self)

        self.active_frame = None
        self.show_drawer_frame()
        
        self.check_changelog()

    def check_changelog(self):
        import json
        import os
        settings_path = "settings.json"
        current_version = "1.0.5"
        last_seen = "1.0.0"
        
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                last_seen = settings.get("last_seen_version", "1.0.0")
            except:
                pass
                
        if last_seen < current_version:
            self.show_changelog()
            try:
                with open(settings_path, "w", encoding="utf-8") as f:
                    json.dump({"last_seen_version": current_version}, f)
            except:
                pass

    def show_changelog(self):
        ReleaseNotesModal(self)

    def show_category_manager(self):
        CategoryManagerWindow(self, self.on_categories_updated)

    def show_calculators(self):
        CalculatorsModal(self)

    def on_categories_updated(self):
        if hasattr(self, "comp_frame"):
            self.comp_frame.update_categories()
        if hasattr(self, "search_frame"):
            self.search_frame.update_categories()

    def _hide_all_frames(self):
        if self.active_frame:
            self.active_frame.grid_forget()

    def show_drawer_frame(self):
        self._hide_all_frames()
        self.drawer_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.active_frame = self.drawer_frame

    def show_comp_frame(self):
        self._hide_all_frames()
        self.comp_frame.update_drawers()
        self.comp_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.active_frame = self.comp_frame

    def show_search_frame(self):
        self._hide_all_frames()
        self.search_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.search_frame.perform_search()
        self.active_frame = self.search_frame


if __name__ == "__main__":
    app = App()
    app.mainloop()

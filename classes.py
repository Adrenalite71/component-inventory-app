import customtkinter as ctk
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
## v1.0.9
* Calculadora de Resistores PTH atualizada com modo bidirecional (Valor para Cores).

## v1.0.8
* Sincronização bidirecional e tradutor automático de cores e valores para resistores.

## v1.0.7
* Correção do ciclo de estado (abas) para o Resistor PTH.

## v1.0.6
* Hotfix de carregamento de dados em campos de texto.

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

import re
import pandas as pd

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


class PTHResistorReverseParser:
    DIGITS_REV = {0: 'Preto', 1: 'Marrom', 2: 'Vermelho', 3: 'Laranja', 4: 'Amarelo', 5: 'Verde', 6: 'Azul', 7: 'Violeta', 8: 'Cinza', 9: 'Branco'}
    MULTIPLIERS_REV = {1: 'Preto', 10: 'Marrom', 100: 'Vermelho', 1000: 'Laranja', 10000: 'Amarelo', 100000: 'Verde', 1000000: 'Azul', 10000000: 'Violeta', 100000000: 'Cinza', 1000000000: 'Branco', 0.1: 'Dourado', 0.01: 'Prateado'}
    TOLERANCES_REV = {'1%': 'Marrom', '2%': 'Vermelho', '0.5%': 'Verde', '0.25%': 'Azul', '0.1%': 'Violeta', '0.05%': 'Cinza', '5%': 'Dourado', '10%': 'Prateado'}

    @staticmethod
    def parse_val(s):
        if not s: return None
        s = str(s).upper().replace('R', '').replace('Ω', '').strip()
        if not s: return None
        mult = 1
        if 'K' in s:
            mult = 1000
            s = s.replace('K', '.')
        elif 'M' in s:
            mult = 1000000
            s = s.replace('M', '.')
        elif 'G' in s:
            mult = 1000000000
            s = s.replace('G', '.')
        
        if s.endswith('.'): s = s[:-1]
        if s.startswith('.'): s = '0' + s
        
        try:
            return float(s) * mult
        except ValueError:
            return None

    @staticmethod
    def get_bands(val_str, tol_str=''):
        val = PTHResistorReverseParser.parse_val(val_str)
        if val is None:
            return []
        
        if tol_str and not tol_str.endswith('%'):
            tol_str += '%'
        
        tol_color = PTHResistorReverseParser.TOLERANCES_REV.get(tol_str, 'Dourado')
        
        sci = f'{val:e}'
        m = re.match(r'^(\d)\.(\d*)e([+-]\d+)$', sci)
        if not m: return []
        
        d1 = int(m.group(1))
        digits_rest = m.group(2).rstrip('0')
        exp = int(m.group(3))
        
        if len(digits_rest) > 1:
            d2 = int(digits_rest[0])
            d3 = int(digits_rest[1])
            multiplier_exp = exp - 2
            mult_val = 10 ** multiplier_exp
            
            m_color = 'Preto'
            for k, v in PTHResistorReverseParser.MULTIPLIERS_REV.items():
                if abs(k - mult_val) < k*0.001:
                    m_color = v
                    break
            return [PTHResistorReverseParser.DIGITS_REV[d1], PTHResistorReverseParser.DIGITS_REV[d2], PTHResistorReverseParser.DIGITS_REV[d3], m_color, tol_color]
        else:
            d2 = int(digits_rest[0]) if digits_rest else 0
            multiplier_exp = exp - 1
            mult_val = 10 ** multiplier_exp
            
            m_color = 'Preto'
            for k, v in PTHResistorReverseParser.MULTIPLIERS_REV.items():
                if abs(k - mult_val) < k*0.001:
                    m_color = v
                    break
            
            if multiplier_exp == -1: m_color = 'Dourado'
            elif multiplier_exp == -2: m_color = 'Prateado'
            
            return [PTHResistorReverseParser.DIGITS_REV[d1], PTHResistorReverseParser.DIGITS_REV[d2], m_color, tol_color]


class PackManagerFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        
        title = ctk.CTkLabel(self, text="Lojinha de Packs de Conhecimento", font=("Segoe UI", 24, "bold"))
        title.grid(row=0, column=0, pady=20, padx=20, sticky="w")
        
        # Future: This list will be fetched via requests.get() from GitHub
        packs = [
            {"id": "pack_inversores", "nome": "Inversores de Potência (IGBTs, Gate Drives)", "autor": "Oficial (Gabriel S.)"},
            {"id": "pack_arduino", "nome": "Automação Arduino Básica", "autor": "Comunidade"}
        ]
        
        for i, p in enumerate(packs):
            frame = ctk.CTkFrame(self)
            frame.grid(row=i+1, column=0, padx=20, pady=10, sticky="ew")
            
            lbl = ctk.CTkLabel(frame, text=f"{p['nome']}\nAutor: {p['autor']}", font=("Segoe UI", 16), justify="left")
            lbl.pack(side="left", padx=15, pady=15)
            
            btn = ctk.CTkButton(frame, text="Baixar / Mesclar", command=lambda pack_id=p['id']: self.download_pack(pack_id))
            btn.pack(side="right", padx=15, pady=15)
            
    def download_pack(self, pack_id):
        import tkinter.messagebox as messagebox
        import component_knowledge
        
        # MOCK DATA for testing before GitHub integration
        mock_data = {}
        mock_data = {
            "fgh40n60": {
                "Categoria": "Transistor",
                "Tipo": "IGBT",
                "Encapsulamento": "TO-247",
                "Tensão Máx (VCEO/VDS)": "600",
                "Corrente Máx (IC/ID)": "40"
            },
            "ir2110": {
                "Categoria": "CI (Circuito Integrado)",
                "Função/Modelo": "Gate Driver High/Low Side",
                "Número de Pinos": "14",
                "Encapsulamento": "DIP-14"
            }
        }
            
        if mock_data:
            component_knowledge.merge_custom_knowledge(mock_data)
            messagebox.showinfo("Sucesso", f"Pacote '{pack_id}' integrado com sucesso!\nComponentes mesclados sem duplicatas.")
        else:
            messagebox.showwarning("Aviso", "Pacote vazio ou ainda não implementado.")


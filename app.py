import sqlite3
import customtkinter as ctk
from tkinter import ttk, messagebox
import pandas as pd
import traceback

DB_FILE = "inventory.db"

CATEGORIES = [
    "Capacitor PTH", 
    "Capacitor SMD",
    "Resistor PTH", 
    "Resistor SMD", 
    "Transistor",
    "Indutor",
    "CI (Circuito Integrado)",
    "MOSFET", 
    "IGBT", 
    "Optoacoplador", 
    "Outros"
]

class DatabaseHelper:
    @staticmethod
    def init_db():
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Create base tables
        c.execute('''
            CREATE TABLE IF NOT EXISTS drawers (
                door_code TEXT PRIMARY KEY CHECK(length(door_code) = 4),
                capacity INTEGER CHECK(capacity >= 1 AND capacity <= 5)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS subdivisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drawer_code TEXT,
                subdivision_index INTEGER,
                FOREIGN KEY(drawer_code) REFERENCES drawers(door_code)
            )
        ''')
        c.execute('''
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
        ''')
        
        # MIGRATION: Add missing columns if they don't exist
        c.execute("PRAGMA table_info(components)")
        existing_columns = [col[1] for col in c.fetchall()]
        
        if "voltage" not in existing_columns:
            c.execute("ALTER TABLE components ADD COLUMN voltage TEXT")
        if "tolerance" not in existing_columns:
            c.execute("ALTER TABLE components ADD COLUMN tolerance TEXT")
        if "component_type" not in existing_columns:
            c.execute("ALTER TABLE components ADD COLUMN component_type TEXT")
            
        conn.commit()
        conn.close()

    @staticmethod
    def get_connection():
        return sqlite3.connect(DB_FILE)


class CategoryUIBuilder:
    """Shared class to build exactly identical UI components for both Registration and Search"""
    
    @staticmethod
    def build_fields(parent_frame, category, is_search=False):
        # Clear frame
        for widget in parent_frame.winfo_children():
            widget.destroy()
            
        inputs = {}
        
        # Helper to add simple text entry
        def add_entry(row, col, label_text, key):
            ctk.CTkLabel(parent_frame, text=label_text).grid(row=row, column=col*2, padx=(10, 5), pady=10, sticky="e")
            entry = ctk.CTkEntry(parent_frame, width=150)
            entry.grid(row=row, column=col*2+1, padx=(0, 15), pady=10, sticky="w")
            inputs[key] = entry
            
        # Helper to add dropdown
        def add_combo(row, col, label_text, key, values):
            ctk.CTkLabel(parent_frame, text=label_text).grid(row=row, column=col*2, padx=(10, 5), pady=10, sticky="e")
            # If search, add empty option at top
            vals = [""] + values if is_search else values
            var = ctk.StringVar(value=vals[0])
            combo = ctk.CTkOptionMenu(parent_frame, variable=var, values=vals, width=150)
            combo.grid(row=row, column=col*2+1, padx=(0, 15), pady=10, sticky="w")
            inputs[key] = var

        if category == "Resistor PTH":
            # For PTH Resistors, we implement the Segmented Button toggle
            method_var = ctk.StringVar(value="Entrada Direta")
            inputs['r_method'] = method_var
            
            method_menu = ctk.CTkSegmentedButton(parent_frame, variable=method_var, values=["Entrada Direta", "Cores (Bandas)"])
            method_menu.grid(row=0, column=0, columnspan=4, padx=10, pady=(10, 0), sticky="ew")
            
            direct_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
            direct_frame.grid(row=1, column=0, columnspan=4, sticky="ew")
            
            bands_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
            
            # Direct Entry widgets
            ctk.CTkLabel(direct_frame, text="Valor (ex: 2k2):").grid(row=0, column=0, padx=5, pady=10)
            val_entry = ctk.CTkEntry(direct_frame, width=120)
            val_entry.grid(row=0, column=1, padx=5, pady=10)
            inputs['raw_value'] = val_entry
            
            ctk.CTkLabel(direct_frame, text="Tolerância:").grid(row=0, column=2, padx=5, pady=10)
            tol_entry = ctk.CTkEntry(direct_frame, width=120)
            tol_entry.grid(row=0, column=3, padx=5, pady=10)
            inputs['tolerance'] = tol_entry
            
            ctk.CTkLabel(direct_frame, text="Encapsulamento:").grid(row=0, column=4, padx=5, pady=10)
            type_entry = ctk.CTkEntry(direct_frame, width=120)
            type_entry.grid(row=0, column=5, padx=5, pady=10)
            inputs['component_type'] = type_entry
            
            # Bands widgets
            ctk.CTkLabel(bands_frame, text="Bandas:").grid(row=0, column=0, padx=5, pady=10)
            band_count_var = ctk.StringVar(value="4")
            inputs['r_band_count'] = band_count_var
            band_count_menu = ctk.CTkOptionMenu(bands_frame, variable=band_count_var, values=["4", "5", "6"], width=60)
            band_count_menu.grid(row=0, column=1, padx=5, pady=10)
            
            colors = ["Preto", "Marrom", "Vermelho", "Laranja", "Amarelo", "Verde", "Azul", "Violeta", "Cinza", "Branco", "Dourado", "Prateado"]
            if is_search: colors = [""] + colors
            
            band_vars = []
            band_combos = []
            for i in range(6):
                var = ctk.StringVar(value=colors[0])
                band_vars.append(var)
                cb = ctk.CTkOptionMenu(bands_frame, variable=var, values=colors, width=80)
                band_combos.append(cb)
            
            inputs['r_bands'] = band_vars
            
            def update_bands(*args):
                count = int(band_count_var.get())
                for i, cb in enumerate(band_combos):
                    if i < count:
                        cb.grid(row=0, column=2+i, padx=2, pady=10)
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
            add_entry(0, 0, "Valor (ex: 2k2):", "raw_value")
            add_entry(0, 1, "Tolerância (ex: 1%):", "tolerance")
            add_entry(0, 2, "Encapsulamento (ex: 0805):", "component_type")
            
        elif category in ["Capacitor PTH", "Capacitor SMD"]:
            add_entry(0, 0, "Capacitância (ex: 100nF):", "raw_value")
            add_entry(0, 1, "Tensão Máx (ex: 50V):", "voltage")
            add_entry(0, 2, "Encapsulamento/Tipo:", "component_type")
            
        elif category == "Transistor":
            add_combo(0, 0, "Tipo:", "transistor_tipo", ["BJT", "MOSFET", "Darlington", "IGBT", "Outro"])
            add_combo(0, 1, "Polaridade:", "transistor_pol", ["NPN", "PNP", "Canal N", "Canal P", "Outra"])
            add_entry(0, 2, "Encapsulamento:", "component_type")
            add_entry(1, 0, "Tensão Máx (VCEO/VDS):", "voltage")
            add_entry(1, 1, "Corrente Máx (IC/ID):", "tolerance")
            
        elif category == "Indutor":
            add_entry(0, 0, "Indutância (ex: 10µH):", "raw_value")
            add_entry(0, 1, "Corrente Máx (ex: 2A):", "tolerance")
            add_entry(0, 2, "Encapsulamento:", "component_type")
            
        elif category == "CI (Circuito Integrado)":
            add_entry(0, 0, "Função/Modelo (ex: NE555):", "raw_value")
            add_entry(0, 1, "Número de Pinos:", "tolerance")
            add_entry(0, 2, "Encapsulamento:", "component_type")
            
        elif category == "MOSFET":
            add_entry(0, 0, "VDS Máx (ex: 60V):", "voltage")
            add_entry(0, 1, "ID Máx (ex: 30A):", "tolerance")
            add_combo(0, 2, "Tipo Canal:", "component_type", ["Canal N", "Canal P"])
            
        elif category == "IGBT":
            add_entry(0, 0, "VCE Máx (ex: 600V):", "voltage")
            add_entry(0, 1, "IC Máx (ex: 40A):", "tolerance")
            add_entry(0, 2, "Encapsulamento:", "component_type")
            
        elif category == "Optoacoplador":
            add_entry(0, 0, "Tensão Isolação (ex: 5kV):", "voltage")
            add_entry(0, 1, "Tipo Saída (Fototransistor):", "component_type")
            
        else: # Outros
            add_entry(0, 0, "Descrição / Valor:", "raw_value")
            add_entry(0, 1, "Tipo / Encapsulamento:", "component_type")
            
        return inputs
        
    @staticmethod
    def extract_values(category, inputs):
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
            method = get_val('r_method')
            if method == "Entrada Direta":
                raw_val = get_val('raw_value')
                tolerance = get_val('tolerance')
                comp_type = get_val('component_type')
            elif method == "Cores (Bandas)":
                count = int(get_val('r_band_count') or 4)
                bands = [var.get() for var in inputs.get('r_bands', [])[:count]]
                raw_val = "CORES: " + "-".join([b for b in bands if b])
                comp_type = get_val('component_type')
        
        elif category == "Transistor":
            tipo = get_val('transistor_tipo')
            pol = get_val('transistor_pol')
            if tipo or pol:
                raw_val = f"{tipo} ({pol})".strip(" ()")
            voltage = get_val('voltage')
            tolerance = get_val('tolerance')
            comp_type = get_val('component_type')
            
        else:
            raw_val = get_val('raw_value')
            voltage = get_val('voltage')
            tolerance = get_val('tolerance')
            comp_type = get_val('component_type')
            
        return raw_val, voltage, tolerance, comp_type


class DrawerRegistrationFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        self.label = ctk.CTkLabel(self, text="Registro de Gaveta", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=20, padx=20, anchor="w")
        
        self.form_frame = ctk.CTkFrame(self)
        self.form_frame.pack(pady=10, padx=20, fill="x")
        
        self.code_label = ctk.CTkLabel(self.form_frame, text="Código da Gaveta (4 dígitos):")
        self.code_label.grid(row=0, column=0, padx=20, pady=20, sticky="w")
        self.code_entry = ctk.CTkEntry(self.form_frame, width=200)
        self.code_entry.grid(row=0, column=1, padx=20, pady=20, sticky="w")
        
        self.cap_label = ctk.CTkLabel(self.form_frame, text="Capacidade de Divisões (1-5):")
        self.cap_label.grid(row=1, column=0, padx=20, pady=20, sticky="w")
        
        self.cap_var = ctk.StringVar(value="1")
        self.cap_menu = ctk.CTkOptionMenu(self.form_frame, variable=self.cap_var, values=["1", "2", "3", "4", "5"])
        self.cap_menu.grid(row=1, column=1, padx=20, pady=20, sticky="w")
        
        self.submit_btn = ctk.CTkButton(self, text="Registrar Gaveta", command=self.register_drawer, height=40)
        self.submit_btn.pack(pady=20, padx=20, anchor="w")

    def register_drawer(self):
        code = self.code_entry.get().strip()
        capacity = int(self.cap_var.get())
        
        if len(code) != 4 or not code.isdigit():
            messagebox.showerror("Erro", "O código da gaveta deve ter exatamente 4 dígitos numéricos.")
            return
            
        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO drawers (door_code, capacity) VALUES (?, ?)", (code, capacity))
            for i in range(1, capacity + 1):
                c.execute("INSERT INTO subdivisions (drawer_code, subdivision_index) VALUES (?, ?)", (code, i))
            conn.commit()
            messagebox.showinfo("Sucesso", f"Gaveta {code} registrada com sucesso com {capacity} divisões!")
            self.code_entry.delete(0, 'end')
        except sqlite3.IntegrityError:
            messagebox.showerror("Erro", f"Gaveta {code} já existe no sistema.")
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro inesperado: {str(e)}")
        finally:
            conn.close()


class ComponentRegistrationFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        self.label = ctk.CTkLabel(self, text="Registro de Componente", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.grid(row=0, column=0, columnspan=2, pady=20, padx=20, sticky="w")
        
        self.container = ctk.CTkFrame(self)
        self.container.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        # Target Drawer (Hierarchical Step 1)
        self.drawer_label = ctk.CTkLabel(self.container, text="Selecione a Gaveta:")
        self.drawer_label.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        
        self.drawer_var = ctk.StringVar(value="")
        self.drawer_menu = ctk.CTkOptionMenu(self.container, variable=self.drawer_var, values=[], command=self.on_drawer_select, width=200)
        self.drawer_menu.grid(row=0, column=1, padx=20, pady=10, sticky="w")
        
        # Target Slot (Hierarchical Step 2)
        self.slot_label = ctk.CTkLabel(self.container, text="Selecione a Divisão:")
        self.slot_label.grid(row=1, column=0, padx=20, pady=10, sticky="w")
        
        self.slot_options = []
        self.slot_mapping = {}
        self.slot_var = ctk.StringVar(value="")
        self.slot_menu = ctk.CTkOptionMenu(self.container, variable=self.slot_var, values=[], width=400)
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
        
        self.cat_var = ctk.StringVar(value=CATEGORIES[0])
        self.cat_menu = ctk.CTkOptionMenu(self.container, variable=self.cat_var, values=CATEGORIES, command=self.on_category_change)
        self.cat_menu.grid(row=4, column=1, padx=20, pady=10, sticky="w")
        
        # Dynamic Frame Container
        self.dynamic_frame = ctk.CTkFrame(self.container, fg_color=("gray90", "gray13"))
        self.dynamic_frame.grid(row=5, column=0, columnspan=2, padx=20, pady=20, sticky="nsew")
        
        self.dynamic_inputs = {}
        
        self.submit_btn = ctk.CTkButton(self, text="Salvar Componente", command=self.save_component, height=40)
        self.submit_btn.grid(row=2, column=0, columnspan=2, pady=20, padx=20, sticky="w")

        self.on_category_change(self.cat_var.get())

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
        c.execute("""
            SELECT s.id, s.subdivision_index, c.id, c.name, c.quantity
            FROM subdivisions s
            LEFT JOIN components c ON s.id = c.subdivision_id
            WHERE s.drawer_code = ?
            ORDER BY s.subdivision_index
        """, (drawer_code,))
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
            self.slot_mapping[label] = {
                "subdivision_id": sub_id,
                "comp_id": comp_id
            }
            
        if self.slot_options:
            self.slot_menu.configure(values=self.slot_options)
            self.slot_var.set(self.slot_options[0])
        else:
            self.slot_menu.configure(values=["Sem divisões"])
            self.slot_var.set("Sem divisões")

    def on_category_change(self, category):
        self.dynamic_inputs = CategoryUIBuilder.build_fields(self.dynamic_frame, category, is_search=False)

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
        
        raw_val, voltage, tolerance, comp_type = CategoryUIBuilder.extract_values(category, self.dynamic_inputs)

        conn = DatabaseHelper.get_connection()
        c = conn.cursor()
        try:
            if old_comp_id:
                c.execute("DELETE FROM components WHERE id = ?", (old_comp_id,))
                
            c.execute('''
                INSERT INTO components 
                (name, category, raw_value, quantity, voltage, tolerance, component_type, subdivision_id, normalized_base_value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            ''', (name, category, raw_val, int(qty), voltage, tolerance, comp_type, subdivision_id))
            conn.commit()
            messagebox.showinfo("Sucesso", f"Componente {name} salvo com sucesso!")
            
            # Reset UI
            self.name_entry.delete(0, 'end')
            self.qty_entry.delete(0, 'end')
            self.qty_entry.insert(0, "1")
            self.on_category_change(category)
            self.on_drawer_select(self.drawer_var.get())
            
        except Exception as e:
            messagebox.showerror("Erro de Banco de Dados", str(e))
        finally:
            conn.close()


class SearchFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        
        self.label = ctk.CTkLabel(self, text="Pesquisa Paramétrica", font=ctk.CTkFont(size=24, weight="bold"))
        self.label.pack(pady=10, padx=20, anchor="w")
        
        # Main Search Area
        self.search_container = ctk.CTkFrame(self)
        self.search_container.pack(pady=10, padx=20, fill="x")
        
        self.search_entry = ctk.CTkEntry(self.search_container, width=300, placeholder_text="Pesquisar por Nome ou Valor...")
        self.search_entry.grid(row=0, column=0, padx=20, pady=15, sticky="w")
        
        search_categories = ["Todos"] + CATEGORIES
        self.cat_var = ctk.StringVar(value="Todos")
        self.cat_menu = ctk.CTkOptionMenu(self.search_container, variable=self.cat_var, values=search_categories, command=self.on_search_category_change)
        self.cat_menu.grid(row=0, column=1, padx=20, pady=15, sticky="w")
        
        self.search_btn = ctk.CTkButton(self.search_container, text="Pesquisar", command=self.perform_search)
        self.search_btn.grid(row=0, column=2, padx=20, pady=15, sticky="w")
        
        # Dynamic Filters Area (Using same UI Builder for EXACT match)
        self.filters_frame = ctk.CTkFrame(self.search_container, fg_color="transparent")
        self.filters_frame.grid(row=1, column=0, columnspan=3, padx=20, pady=(0, 10), sticky="ew")
        
        self.dynamic_inputs = {}
        
        # Grid using ttk.Treeview
        self.tree_frame = ctk.CTkFrame(self)
        self.tree_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#2b2b2b", 
                        foreground="white", 
                        rowheight=25, 
                        fieldbackground="#2b2b2b",
                        bordercolor="#343638",
                        borderwidth=0)
        style.map('Treeview', background=[('selected', '#1f538d')])
        
        style.configure("Treeview.Heading", 
                        background="#565b5e", 
                        foreground="white", 
                        relief="flat")
        style.map("Treeview.Heading", background=[('active', '#3484F0')])

        columns = ("Nome", "Categoria", "Valor/Desc", "Tensão", "Tol/Corrente", "Tipo/Encaps.", "Qtd", "Localização")
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show="headings")
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=110)
        
        self.tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        self.scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y", pady=5)

    def on_search_category_change(self, category):
        if category == "Todos":
            for widget in self.filters_frame.winfo_children():
                widget.destroy()
            self.dynamic_inputs = {}
        else:
            self.dynamic_inputs = CategoryUIBuilder.build_fields(self.filters_frame, category, is_search=True)

    def perform_search(self):
        query_text = self.search_entry.get().strip()
        category = self.cat_var.get()
        
        conn = DatabaseHelper.get_connection()
        
        sql = """
            SELECT c.name, c.category, c.raw_value, c.voltage, c.tolerance, c.component_type, c.quantity, 
                   s.drawer_code, s.subdivision_index
            FROM components c
            JOIN subdivisions s ON c.subdivision_id = s.id
            WHERE 1=1
        """
        params = []
        
        if query_text:
            sql += " AND (c.name LIKE ? OR c.raw_value LIKE ?)"
            params.extend([f"%{query_text}%", f"%{query_text}%"])
            
        if category != "Todos":
            sql += " AND c.category = ?"
            params.append(category)
            
            # Extract formatted values using the shared builder
            raw_val, voltage, tolerance, comp_type = CategoryUIBuilder.extract_values(category, self.dynamic_inputs)
            
            if raw_val and "CORES:" not in raw_val:
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
            messagebox.showerror("Erro de Pesquisa", f"Erro no banco de dados:\n{str(e)}")
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
                        idx = int(row['subdivision_index'])
                        drw = str(row['drawer_code'])
                        return drw if idx == 1 else f"{drw}-{idx}"
                    except:
                        return "Erro Loc."
                        
                df['Location'] = df.apply(format_location, axis=1)
                
                for _, row in df.iterrows():
                    try:
                        self.tree.insert("", "end", values=(
                            str(row['name']), 
                            str(row['category']), 
                            str(row['raw_value']), 
                            str(row['voltage']), 
                            str(row['tolerance']), 
                            str(row['component_type']), 
                            str(row['quantity']), 
                            str(row['Location'])
                        ))
                    except Exception as tree_err:
                        print(f"Skipping row rendering error: {tree_err}")
                        continue
            except Exception as e:
                error_trace = traceback.format_exc()
                print(error_trace)
                messagebox.showerror("Erro de Renderização", f"Ocorreu um erro ao formatar os resultados:\n{str(e)}")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Sistema de Inventário Paramétrico de Componentes")
        self.geometry("1100x700")
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        DatabaseHelper.init_db()
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="Inventário", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))
        
        self.btn_drawer = ctk.CTkButton(self.sidebar, text="Registrar Gaveta", command=self.show_drawer_frame)
        self.btn_drawer.grid(row=1, column=0, padx=20, pady=10)
        
        self.btn_comp = ctk.CTkButton(self.sidebar, text="Registrar Componente", command=self.show_comp_frame)
        self.btn_comp.grid(row=2, column=0, padx=20, pady=10)
        
        self.btn_search = ctk.CTkButton(self.sidebar, text="Pesquisar Componentes", command=self.show_search_frame)
        self.btn_search.grid(row=3, column=0, padx=20, pady=10)
        
        self.drawer_frame = DrawerRegistrationFrame(self)
        self.comp_frame = ComponentRegistrationFrame(self)
        self.search_frame = SearchFrame(self)
        
        self.active_frame = None
        self.show_drawer_frame()

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

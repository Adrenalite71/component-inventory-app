import json
import sqlite3
import pandas as pd
from network import DatabaseManager

class LocalDatabaseManager:
    @staticmethod
    def init_db():
        conn = DatabaseManager.get_connection()
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
            c.execute("CREATE TABLE drawers_new (door_code TEXT PRIMARY KEY CHECK(length(door_code) = 4), capacity INTEGER)")
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
                properties TEXT DEFAULT '{}',
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
        if "properties" not in existing_columns:
            c.execute("ALTER TABLE components ADD COLUMN properties TEXT DEFAULT '{}'")

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
        row = c.fetchone()
        CATEGORIES = [
            "Resistor", "Capacitor", "Diodo", "Capacitor Eletrolítico", 
            "Capacitor Tântalo", "Capacitor Poliéster", "Capacitor Cerâmico", 
            "Capacitor PTH", "Capacitor SMD", "Resistor PTH", "Resistor SMD", 
            "Transistor", "Indutor", "CI (Circuito Integrado)", "Optoacoplador", "Outros"
        ]
        if row and row[0] == 0:
            for cat in CATEGORIES:
                c.execute(
                    "INSERT INTO categories (name, logic_type, fields_json) VALUES (?, ?, ?)",
                    (cat, cat, "[]"),
                )

        c.execute("DELETE FROM categories WHERE name IN ('MOSFET', 'IGBT')")

        c.execute("""
            CREATE TABLE IF NOT EXISTS learned_specs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                properties_json TEXT NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    @staticmethod
    def execute_query(sql, params=None):
        conn = DatabaseManager.get_connection()
        c = conn.cursor()
        if params:
            c.execute(sql, params)
        else:
            c.execute(sql)
        conn.commit()
        
        last_row_id = c.lastrowid
        conn.close()
        return last_row_id

    @staticmethod
    def fetch_all(sql, params=None):
        conn = DatabaseManager.get_connection()
        c = conn.cursor()
        if params:
            c.execute(sql, params)
        else:
            c.execute(sql)
        result = c.fetchall()
        conn.close()
        return result

    @staticmethod
    def fetch_one(sql, params=None):
        conn = DatabaseManager.get_connection()
        c = conn.cursor()
        if params:
            c.execute(sql, params)
        else:
            c.execute(sql)
        result = c.fetchone()
        conn.close()
        return result

    # --- Category Methods ---
    @staticmethod
    def get_categories():
        return LocalDatabaseManager.fetch_all("SELECT name, logic_type, fields_json FROM categories ORDER BY id")
        
    @staticmethod
    def get_category_count():
        row = LocalDatabaseManager.fetch_one("SELECT count(*) FROM categories")
        return row[0] if row else 0

    @staticmethod
    def add_category(name, logic_type, fields_json):
        LocalDatabaseManager.execute_query(
            "INSERT INTO categories (name, logic_type, fields_json) VALUES (?, ?, ?)",
            (name, logic_type, fields_json)
        )
        
    @staticmethod
    def update_category(name, logic_type, fields_json, old_name):
        LocalDatabaseManager.execute_query(
            "UPDATE categories SET name = ?, logic_type = ?, fields_json = ? WHERE name = ?",
            (name, logic_type, fields_json, old_name)
        )

    @staticmethod
    def delete_category(name):
        LocalDatabaseManager.execute_query("DELETE FROM categories WHERE name = ?", (name,))
        
    @staticmethod
    def get_component_count_by_category(name):
        row = LocalDatabaseManager.fetch_one("SELECT count(*) FROM components WHERE category = ?", (name,))
        return row[0] if row else 0

    # --- Drawer Methods ---
    @staticmethod
    def get_drawers():
        return LocalDatabaseManager.fetch_all("SELECT door_code, capacity FROM drawers ORDER BY door_code")
        
    @staticmethod
    def get_drawer_codes():
        rows = LocalDatabaseManager.fetch_all("SELECT door_code FROM drawers ORDER BY door_code")
        return [r[0] for r in rows]

    @staticmethod
    def add_drawer(code, capacity):
        LocalDatabaseManager.execute_query("INSERT INTO drawers (door_code, capacity) VALUES (?, ?)", (code, capacity))
        for i in range(1, capacity + 1):
            LocalDatabaseManager.execute_query("INSERT INTO subdivisions (drawer_code, subdivision_index) VALUES (?, ?)", (code, i))

    @staticmethod
    def update_drawer(code, capacity, current_subs):
        LocalDatabaseManager.execute_query("UPDATE drawers SET capacity = ? WHERE door_code = ?", (capacity, code))
        if capacity > current_subs:
            for i in range(current_subs + 1, capacity + 1):
                LocalDatabaseManager.execute_query("INSERT INTO subdivisions (drawer_code, subdivision_index) VALUES (?, ?)", (code, i))
        elif capacity < current_subs:
            LocalDatabaseManager.execute_query("DELETE FROM subdivisions WHERE drawer_code = ? AND subdivision_index > ?", (code, capacity))

    @staticmethod
    def delete_drawer(code):
        LocalDatabaseManager.execute_query("DELETE FROM subdivisions WHERE drawer_code = ?", (code,))
        LocalDatabaseManager.execute_query("DELETE FROM drawers WHERE door_code = ?", (code,))

    @staticmethod
    def check_components_in_removed_subs(code, capacity):
        row = LocalDatabaseManager.fetch_one(
            "SELECT count(*) FROM components c JOIN subdivisions s ON c.subdivision_id = s.id WHERE s.drawer_code = ? AND s.subdivision_index > ?",
            (code, capacity)
        )
        return row[0] if row else 0
        
    @staticmethod
    def check_components_in_drawer(code):
        row = LocalDatabaseManager.fetch_one(
            "SELECT count(*) FROM components c JOIN subdivisions s ON c.subdivision_id = s.id WHERE s.drawer_code = ?",
            (code,)
        )
        return row[0] if row else 0

    @staticmethod
    def get_subdivisions(drawer_code):
        return LocalDatabaseManager.fetch_all(
            "SELECT subdivision_index FROM subdivisions WHERE drawer_code = ? ORDER BY subdivision_index",
            (drawer_code,)
        )
        
    @staticmethod
    def get_subdivision_id(drawer_code, sub_index):
        row = LocalDatabaseManager.fetch_one(
            "SELECT id FROM subdivisions WHERE drawer_code = ? AND subdivision_index = ?",
            (drawer_code, sub_index)
        )
        return row[0] if row else None

    @staticmethod
    def get_slots_with_components(drawer_code):
        return LocalDatabaseManager.fetch_all(
            """
            SELECT s.id, s.subdivision_index, c.id, c.name, c.quantity
            FROM subdivisions s
            LEFT JOIN components c ON s.id = c.subdivision_id
            WHERE s.drawer_code = ?
            ORDER BY s.subdivision_index
            """,
            (drawer_code,)
        )

    # --- Component Methods ---
    @staticmethod
    def add_component(name, category, raw_value, norm_val, quantity, sub_id, properties_json, voltage, tolerance, component_type):
        LocalDatabaseManager.execute_query(
            "INSERT INTO components (name, category, raw_value, normalized_base_value, quantity, subdivision_id, properties, voltage, tolerance, component_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, category, raw_value, norm_val, quantity, sub_id, properties_json, voltage, tolerance, component_type)
        )

    @staticmethod
    def update_component(comp_id, name, category, raw_value, norm_val, quantity, sub_id, properties_json, voltage, tolerance, component_type):
        LocalDatabaseManager.execute_query(
            "UPDATE components SET name=?, category=?, raw_value=?, normalized_base_value=?, quantity=?, subdivision_id=?, properties=?, voltage=?, tolerance=?, component_type=? WHERE id=?",
            (name, category, raw_value, norm_val, quantity, sub_id, properties_json, voltage, tolerance, component_type, comp_id)
        )

    @staticmethod
    def search_components(query_string=None):
        return LocalDatabaseManager.fetch_all(query_string)

    @staticmethod
    def save_learned_spec(name, properties_dict):
        if not name:
            return
        name_upper = name.strip().upper()
        props_json = json.dumps(properties_dict)
        try:
            LocalDatabaseManager.execute_query(
                "INSERT OR REPLACE INTO learned_specs (name, properties_json) VALUES (?, ?)",
                (name_upper, props_json)
            )
        except Exception as e:
            print(f"Error saving learned spec: {e}")

    @staticmethod
    def get_learned_spec(name):
        if not name:
            return None
        name_upper = name.strip().upper()
        try:
            rows = LocalDatabaseManager.fetch_all(
                "SELECT properties_json FROM learned_specs WHERE name = ?",
                (name_upper,)
            )
            if rows:
                return json.loads(rows[0][0])
        except Exception as e:
            print(f"Error getting learned spec: {e}")
        return None

    @staticmethod
    def delete_component(comp_id):
        LocalDatabaseManager.execute_query("DELETE FROM components WHERE id = ?", (comp_id,))

def clear_division(gaveta_id, divisao_numero):
    drawer_code = str(gaveta_id)
    if len(drawer_code) < 4:
        drawer_code = drawer_code.zfill(4)
    LocalDatabaseManager.execute_query(
        "DELETE FROM components WHERE subdivision_id = (SELECT id FROM subdivisions WHERE drawer_code = ? AND subdivision_index = ?)",
        (drawer_code, divisao_numero)
    )

    @staticmethod
    def update_quantity(comp_id, new_qty):
        LocalDatabaseManager.execute_query("UPDATE components SET quantity = ? WHERE id = ?", (new_qty, comp_id))

    @staticmethod
    def get_component(comp_id):
        return LocalDatabaseManager.fetch_one(
            "SELECT name, quantity, category, raw_value, voltage, tolerance, component_type, properties FROM components WHERE id = ?",
            (comp_id,)
        )

    @staticmethod
    def search_parametric(search_text, category, dynamic_filters):
        # We will use pandas read_sql from DatabaseManager network layer
        query = "SELECT c.id, c.name, c.category, c.raw_value, c.voltage, c.tolerance, c.component_type, c.normalized_base_value, c.quantity, s.drawer_code, s.subdivision_index, c.properties FROM components c LEFT JOIN subdivisions s ON c.subdivision_id = s.id WHERE 1=1"
        params = []
        
        if search_text:
            query += " AND c.name LIKE ?"
            params.append(f"%{search_text}%")
            
        if category and category != "Todos":
            query += " AND c.category = ?"
            params.append(category)
            
        if dynamic_filters:
            for field, val in dynamic_filters.items():
                if val:
                    query += f" AND json_extract(c.properties, '$.\"' || ? || '\"') = ?"
                    params.extend([field, val])

        # Execute query using pandas network abstraction
        df = DatabaseManager.read_sql(query, params)
        return df

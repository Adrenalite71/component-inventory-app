import sqlite3
import json
import firebase_admin
from firebase_admin import credentials, firestore

def main():
    print("=== Starting SQLite to Firestore Migration ===")
    
    # 1. Initialize Firebase Admin SDK
    print("Initializing Firebase Admin SDK...")
    try:
        cred = credentials.Certificate("./firebase-key.json")
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Successfully connected to Firestore.")
    except Exception as e:
        print(f"Error connecting to Firebase: {e}")
        return

    # 2. Connect to local SQLite database
    print("Connecting to local SQLite database 'inventory.db'...")
    try:
        conn = sqlite3.connect("inventory.db")
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
    except Exception as e:
        print(f"Error connecting to SQLite: {e}")
        return

    # Migrate Categories
    print("\n--- Migrating Categories ---")
    c.execute("SELECT * FROM categories")
    categories = c.fetchall()
    migrated_categories = 0
    for row in categories:
        cat_dict = dict(row)
        cat_name = cat_dict.get('name')
        
        # Parse fields_json back to dict
        fields_json = cat_dict.get('fields_json', '[]')
        try:
            cat_dict['fields_json'] = json.loads(fields_json)
        except Exception:
            cat_dict['fields_json'] = []
            
        try:
            # Use the category name as document ID if possible, otherwise let Firestore auto-generate
            doc_ref = db.collection('categories').document(cat_name)
            doc_ref.set(cat_dict)
            migrated_categories += 1
        except Exception as e:
            print(f"Failed to migrate category '{cat_name}': {e}")
            
    print(f"Successfully migrated {migrated_categories} categories!")

    # Migrate Drawers and Subdivisions
    print("\n--- Migrating Drawers ---")
    c.execute("SELECT * FROM drawers")
    drawers = c.fetchall()
    migrated_drawers = 0
    for row in drawers:
        drawer_dict = dict(row)
        drawer_code = drawer_dict.get('door_code')
        
        # Fetch subdivisions for this drawer
        c.execute("SELECT * FROM subdivisions WHERE drawer_code = ?", (drawer_code,))
        subdivisions = c.fetchall()
        
        sub_list = []
        for sub in subdivisions:
            sub_list.append(dict(sub))
            
        drawer_dict['subdivisions'] = sub_list
        
        try:
            # Use door_code as document ID
            doc_ref = db.collection('drawers').document(str(drawer_code))
            doc_ref.set(drawer_dict)
            migrated_drawers += 1
        except Exception as e:
            print(f"Failed to migrate drawer '{drawer_code}': {e}")
            
    print(f"Successfully migrated {migrated_drawers} drawers (with their subdivisions)!")

    # Migrate Components
    print("\n--- Migrating Components ---")
    c.execute("SELECT * FROM components")
    components = c.fetchall()
    migrated_components = 0
    for row in components:
        comp_dict = dict(row)
        comp_name = comp_dict.get('name')
        
        # Parse properties JSON string back to dict
        properties_json = comp_dict.get('properties', '{}')
        if properties_json:
            try:
                comp_dict['properties'] = json.loads(properties_json)
            except Exception:
                comp_dict['properties'] = {}
        else:
            comp_dict['properties'] = {}
            
        try:
            # Use the SQLite row ID as document ID to preserve references, or let it generate
            # Using SQLite ID to ensure it maps correctly if needed, though NoSQL relations differ
            doc_ref = db.collection('components').document(str(comp_dict['id']))
            doc_ref.set(comp_dict)
            migrated_components += 1
        except Exception as e:
            print(f"Failed to migrate component '{comp_name}': {e}")
            
    print(f"Successfully migrated {migrated_components} components!")
    
    conn.close()
    print("\n=== Migration Completed Successfully! ===")

if __name__ == "__main__":
    main()

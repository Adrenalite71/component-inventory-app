import sqlite3
import json
import threading
import urllib.request
import urllib.error
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
import pandas as pd

class RemoteCursor:
    def __init__(self, host_url):
        self.host_url = host_url
        self.last_results = []
        self.description = []
    
    def execute(self, sql, params=None):
        data = json.dumps({"sql": sql, "params": params or []}).encode('utf-8')
        req = urllib.request.Request(self.host_url + "/query", data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req) as response:
                resp_data = json.loads(response.read().decode('utf-8'))
                if resp_data.get("error"):
                    raise Exception(resp_data["error"])
                self.last_results = resp_data.get("results", [])
                cols = resp_data.get("columns", [])
                self.description = [(c,) for c in cols]
        except urllib.error.URLError as e:
            raise Exception(f"Erro de conexão com o servidor: {str(e)}")
    
    def fetchone(self):
        if self.last_results:
            return tuple(self.last_results[0])
        return None
        
    def fetchall(self):
        return [tuple(r) for r in self.last_results]

class RemoteConnection:
    def __init__(self, host_url):
        self.host_url = host_url
        
    def cursor(self):
        return RemoteCursor(self.host_url)
        
    def commit(self):
        pass
        
    def close(self):
        pass

class QueryHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/query":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
            except:
                payload = {}
            sql = payload.get("sql", "")
            params = payload.get("params", [])
            
            try:
                with DatabaseManager.DB_LOCK:
                    conn = sqlite3.connect("inventory.db")
                    c = conn.cursor()
                    if params:
                        c.execute(sql, tuple(params))
                    else:
                        c.execute(sql)
                    
                    is_read = sql.strip().upper().startswith("SELECT") or sql.strip().upper().startswith("PRAGMA")
                    if is_read:
                        results = c.fetchall()
                        columns = [desc[0] for desc in c.description] if c.description else []
                    else:
                        conn.commit()
                        results = []
                        columns = []
                    conn.close()
                    
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = json.dumps({"results": results, "columns": columns})
                self.wfile.write(response.encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = json.dumps({"error": str(e)})
                self.wfile.write(response.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            
    def log_message(self, format, *args):
        pass 

class DatabaseManager:
    MODE = "Local" 
    HOST_IP = "127.0.0.1"
    PORT = 8080
    DB_LOCK = threading.Lock()
    _server_thread = None
    _server_instance = None
    
    @classmethod
    def get_connection(cls):
        if cls.MODE == "Client":
            return RemoteConnection(f"http://{cls.HOST_IP}:{cls.PORT}")
        else:
            return sqlite3.connect("inventory.db", check_same_thread=False)

    @classmethod
    def read_sql(cls, sql, params=None):
        if cls.MODE == "Client":
            c = RemoteCursor(f"http://{cls.HOST_IP}:{cls.PORT}")
            c.execute(sql, params)
            cols = [desc[0] for desc in c.description]
            return pd.DataFrame(c.last_results, columns=cols)
        else:
            conn = cls.get_connection()
            try:
                return pd.read_sql_query(sql, conn, params=tuple(params) if params else None)
            finally:
                conn.close()
                
    @classmethod
    def start_server(cls):
        if cls._server_instance is None:
            cls._server_instance = HTTPServer(('0.0.0.0', cls.PORT), QueryHandler)
            cls._server_thread = threading.Thread(target=cls._server_instance.serve_forever, daemon=True)
            cls._server_thread.start()
            
    @classmethod
    def stop_server(cls):
        if cls._server_instance:
            cls._server_instance.shutdown()
            cls._server_instance.server_close()
            cls._server_instance = None
            if cls._server_thread:
                cls._server_thread.join(timeout=1)
                cls._server_thread = None

    @classmethod
    def get_local_ip(cls):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            ip = '127.0.0.1'
        finally:
            s.close()
        return ip

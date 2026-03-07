# -*- coding: utf-8 -*-
"""
Facilitador de Execucao - Quiz Vance V2.0

Execute este arquivo para iniciar o app
"""

import os
import sys
import warnings
import traceback
from core.encoding import configure_utf8
from core.error_monitor import setup_global_error_hooks, log_exception, log_message, log_event
from core.app_paths import ensure_runtime_dirs, get_db_path
from core.database_v2 import Database

# Configurar encoding para UTF-8 no Windows
configure_utf8()

# Verificar se esta no diretorio correto
if not os.path.exists("main_v2.py") or not os.path.exists("config.py"):
    print("[ERRO] Execute este arquivo do diretorio raiz do projeto!")
    print("   cd simulador-pro-v2")
    print("   python run.py")
    sys.exit(1)

# Habilitar captura global de erros
setup_global_error_hooks()
log_message("App startup", f"Python {sys.version.split()[0]}")
ensure_runtime_dirs()

# Verificar dependencias
try:
    warnings.filterwarnings(
        "ignore",
        category=ResourceWarning,
        module=r"flet\.messaging\.flet_socket_server"
    )
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        module=r"main_v2"
    )
    import flet
except ImportError:
    print("[ERRO] Flet nao instalado!")
    print("        pip install -r requirements.txt")
    sys.exit(1)

# Verificar se banco existe
db_path = get_db_path()
db_instance = None
if not db_path.exists():
    print("[WARN] Banco de dados nao encontrado!")
    print("       Inicializando banco local...")
    print()
    try:
        db_instance = Database(str(db_path))
        db_instance.iniciar_banco()
    except Exception as e:
        print(f"[ERRO] Erro no setup: {e}")
        sys.exit(1)

# Executar aplicacao
print("[INFO] Iniciando Quiz Vance V2.0...")
print()

from main_v2 import main
import flet as ft

try:
    log_event("app_start", f"python={sys.version.split()[0]}")
    ft.run(main, assets_dir="assets")
except Exception as ex:
    log_exception(ex, "run.py ft.run")
    print(f"[ERRO] Falha ao iniciar app: {ex}")
    traceback.print_exc()
    sys.exit(1)
finally:
    # Fechar pool de conexoes SQLite ao sair (mesma instancia criada no setup)
    if db_instance is not None:
        try:
            db_instance.shutdown()
        except Exception:
            pass

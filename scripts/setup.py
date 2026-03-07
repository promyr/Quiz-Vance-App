# -*- coding: utf-8 -*-
"""
Script de Setup Inicial - Quiz Vance V2.0

Configura o projeto pela primeira vez
"""

import os
import sys

# Adicionar diretÃ³rio raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database_v2 import Database


def criar_diretorios():
    """Cria diretÃ³rios necessÃ¡rios"""
    print("ðŸ“ Criando diretÃ³rios...")
    
    dirs = [
        "data",
        "data/pdfs",
        "data/cache",
        "assets",
        "assets/images",
        "assets/sounds",
        "logs"
    ]
    
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        print(f"  âœ… {dir_path}")


def inicializar_banco():
    """Inicializa banco de dados"""
    print("\nðŸ’¾ Inicializando banco de dados...")
    
    db = Database()
    db.iniciar_banco()
    
    print("  âœ… Banco criado e populado")


def verificar_dependencias():
    """Verifica se todas as dependÃªncias estÃ£o instaladas"""
    print("\nðŸ“¦ Verificando dependÃªncias...")
    
    required = [
        "flet",
        "google.generativeai",
        "openai",
        "requests"
    ]
    
    missing = []
    
    for package in required:
        try:
            __import__(package.replace("-", "_"))
            print(f"  âœ… {package}")
        except ImportError:
            print(f"  âŒ {package} - NÃƒO INSTALADO")
            missing.append(package)
    
    if missing:
        print(f"\nâš ï¸  Instale as dependÃªncias faltantes:")
        print(f"    pip install {' '.join(missing)}")
        return False
    
    return True


def criar_config_local():
    """Cria arquivo de configuraÃ§Ã£o local"""
    print("\nâš™ï¸  Criando configuraÃ§Ã£o local...")
    
    if os.path.exists("config_local.py"):
        print("  â­ï¸  config_local.py jÃ¡ existe, pulando...")
        return
    
    template = """# -*- coding: utf-8 -*-
'''
ConfiguraÃ§Ã£o Local - NÃƒO COMMITAR NO GIT!

Adicione suas chaves API aqui
'''

# Google OAuth (opcional)
GOOGLE_CLIENT_ID = "YOUR_CLIENT_ID.apps.googleusercontent.com"

# API Keys (pelo menos uma Ã© necessÃ¡ria)
GEMINI_API_KEY = "your_gemini_api_key_here"
OPENAI_API_KEY = "your_openai_api_key_here"
"""
    
    with open("config_local.py", "w", encoding="utf-8") as f:
        f.write(template)
    
    print("  âœ… config_local.py criado")
    print("  ðŸ“ Edite config_local.py e adicione suas API keys")


def exibir_proximo_passos():
    """Exibe prÃ³ximos passos"""
    print("\n" + "="*60)
    print("ðŸŽ‰ SETUP CONCLUÃDO!")
    print("="*60)
    print("\nðŸ“‹ PrÃ³ximos passos:")
    print("  1. Edite config_local.py com suas API keys")
    print("  2. Execute: python main_v2.py")
    print("  3. Crie uma conta e comece a estudar!")
    print("\nðŸ’¡ Dicas:")
    print("  â€¢ Use Gemini para comeÃ§ar (API gratuita)")
    print("  â€¢ Configure Google OAuth para login social")
    print("  â€¢ Rode os testes: python tests/test_suite.py")
    print()


def main():
    """Executa setup completo"""
    print("="*60)
    print("ðŸš€ SETUP - Quiz Vance V2.0")
    print("="*60)
    print()
    
    try:
        criar_diretorios()
        
        if not verificar_dependencias():
            print("\nâŒ Instale as dependÃªncias primeiro!")
            return
        
        inicializar_banco()
        criar_config_local()
        exibir_proximo_passos()
        
    except Exception as e:
        print(f"\nâŒ Erro durante setup: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


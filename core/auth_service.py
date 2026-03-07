# -*- coding: utf-8 -*-
"""
Serviço de Autenticação Google OAuth 2.0
"""

import requests
import json
import hashlib
import base64
import os
from urllib.parse import urlencode, parse_qs
from typing import Optional, Dict, Tuple
import secrets


class GoogleAuthService:
    """Gerencia autenticação via Google OAuth 2.0"""
    
    def __init__(self, client_id: str, redirect_uri: str, scopes: list):
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self.state = None
        self.code_verifier = None
        
    def _generate_code_verifier(self) -> str:
        """Gera code verifier para PKCE"""
        return base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
    
    def _generate_code_challenge(self, verifier: str) -> str:
        """Gera code challenge a partir do verifier"""
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')
    
    def get_auth_url(self) -> Tuple[str, str, str]:
        """
        Gera URL de autenticação Google
        Retorna: (url, state, code_verifier)
        """
        # Gerar state para CSRF protection
        self.state = secrets.token_urlsafe(32)
        
        # Gerar PKCE
        self.code_verifier = self._generate_code_verifier()
        code_challenge = self._generate_code_challenge(self.code_verifier)
        
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(self.scopes),
            'state': self.state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'access_type': 'offline',
            'prompt': 'consent'
        }
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        return auth_url, self.state, self.code_verifier
    
    def exchange_code_for_token(self, code: str, code_verifier: str) -> Optional[Dict]:
        """
        Troca authorization code por access token
        """
        token_url = "https://oauth2.googleapis.com/token"
        
        data = {
            'client_id': self.client_id,
            'code': code,
            'code_verifier': code_verifier,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri
        }
        
        try:
            response = requests.post(token_url, data=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[AUTH] Erro ao trocar código: {e}")
            return None
    
    def get_user_info(self, access_token: str) -> Optional[Dict]:
        """
        Obtém informações do usuário usando access token
        """
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        try:
            response = requests.get(userinfo_url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[AUTH] Erro ao obter info do usuário: {e}")
            return None
    
    def validate_state(self, received_state: str) -> bool:
        """Valida state para prevenir CSRF"""
        return received_state == self.state


class LocalAuthServer:
    """Servidor HTTP local para callback OAuth"""
    
    def __init__(self, port: int = 8550):
        self.port = port
        self.auth_code = None
        self.state = None
        self.error = None
        
    def start_and_wait(self, timeout: int = 120) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Inicia servidor e aguarda callback
        Retorna: (code, state, error)
        """
        import socket
        from threading import Thread, Event
        
        callback_received = Event()
        
        def handle_request(client_socket):
            try:
                request = client_socket.recv(1024).decode('utf-8')
                
                # Parse request
                if 'GET /' in request:
                    request_line = request.split('\n')[0]
                    path = request_line.split()[1]
                    
                    if '?' in path:
                        query_string = path.split('?')[1]
                        params = parse_qs(query_string)
                        
                        self.auth_code = params.get('code', [None])[0]
                        self.state = params.get('state', [None])[0]
                        self.error = params.get('error', [None])[0]
                
                # Enviar resposta HTML
                if self.error:
                    html = """
                    <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1 style="color: #EF4444;">❌ Erro na Autenticação</h1>
                    <p>Ocorreu um erro. Você pode fechar esta janela.</p>
                    </body></html>
                    """
                else:
                    html = """
                    <html><body style="font-family: Arial; text-align: center; padding: 50px;">
                    <h1 style="color: #10B981;">✅ Autenticação Concluída!</h1>
                    <p>Você pode fechar esta janela e voltar para o aplicativo.</p>
                    </body></html>
                    """
                
                response = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n{html}"
                client_socket.send(response.encode('utf-8'))
                client_socket.close()
                
                callback_received.set()
            except Exception as e:
                print(f"[AUTH] Erro ao processar request: {e}")
        
        def server_thread():
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            try:
                server.bind(('localhost', self.port))
                server.listen(1)
                server.settimeout(timeout)
                
                client, _ = server.accept()
                handle_request(client)
            except socket.timeout:
                print("[AUTH] Timeout aguardando callback")
            except Exception as e:
                print(f"[AUTH] Erro no servidor: {e}")
            finally:
                server.close()
        
        thread = Thread(target=server_thread, daemon=True)
        thread.start()
        
        # Aguardar callback ou timeout
        callback_received.wait(timeout=timeout)
        
        return self.auth_code, self.state, self.error


def authenticate_with_google(client_id: str, redirect_uri: str, scopes: list) -> Optional[Dict]:
    """
    Fluxo completo de autenticação Google OAuth
    
    Returns:
        Dict com user_info e tokens, ou None se falhar
    """
    import webbrowser
    
    print("[AUTH] Iniciando autenticação Google...")
    
    # Criar serviço de auth
    auth_service = GoogleAuthService(client_id, redirect_uri, scopes)
    
    # Gerar URL de autenticação
    auth_url, expected_state, code_verifier = auth_service.get_auth_url()
    
    # Iniciar servidor local
    server = LocalAuthServer(port=8550)
    
    # Abrir navegador
    print("[AUTH] Abrindo navegador...")
    webbrowser.open(auth_url)
    
    # Aguardar callback
    print("[AUTH] Aguardando callback...")
    code, state, error = server.start_and_wait()
    
    if error:
        print(f"[AUTH] Erro OAuth: {error}")
        return None
    
    if not code:
        print("[AUTH] Nenhum código recebido")
        return None
    
    # Validar state
    if not auth_service.validate_state(state):
        print("[AUTH] State inválido - possível ataque CSRF")
        return None
    
    # Trocar código por token
    print("[AUTH] Trocando código por token...")
    tokens = auth_service.exchange_code_for_token(code, code_verifier)
    
    if not tokens:
        print("[AUTH] Falha ao obter tokens")
        return None
    
    # Obter informações do usuário
    print("[AUTH] Obtendo informações do usuário...")
    user_info = auth_service.get_user_info(tokens['access_token'])
    
    if not user_info:
        print("[AUTH] Falha ao obter info do usuário")
        return None
    
    print("[AUTH] ✅ Autenticação bem-sucedida!")
    
    return {
        'user_info': user_info,
        'tokens': tokens
    }


# ========== INTEGRAÇÃO SIMPLES PARA TESTE ==========
def test_google_auth():
    """Função de teste"""
    from config import GOOGLE_OAUTH
    
    result = authenticate_with_google(
        client_id=GOOGLE_OAUTH['client_id'],
        redirect_uri=GOOGLE_OAUTH['redirect_uri'],
        scopes=GOOGLE_OAUTH['scopes']
    )
    
    if result:
        print("\n===== USER INFO =====")
        print(json.dumps(result['user_info'], indent=2))
        return result
    else:
        print("\n❌ Falha na autenticação")
        return None


if __name__ == "__main__":
    test_google_auth()

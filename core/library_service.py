# -*- coding: utf-8 -*-
import os
import shutil
import datetime
import hashlib
from urllib.parse import unquote, urlparse
from typing import List, Dict, Optional
from core.database_v2 import Database
from core.app_paths import get_library_dir

LIBRARY_DIR = str(get_library_dir())


def _normalize_local_path(file_path: str) -> str:
    raw = str(file_path or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("file://"):
        try:
            parsed = urlparse(raw)
            uri_path = unquote(parsed.path or "")
            if os.name == "nt" and len(uri_path) >= 3 and uri_path[0] == "/" and uri_path[2] == ":":
                uri_path = uri_path[1:]
            return uri_path or raw
        except Exception:
            return raw
    return raw

class LibraryService:
    def __init__(self, db: Database):
        self.db = db
        if not os.path.exists(LIBRARY_DIR):
            os.makedirs(LIBRARY_DIR, exist_ok=True)

    def adicionar_arquivo(self, user_id: int, file_path: str, categoria: str = "Geral") -> Dict:
        """
        Copia arquivo para biblioteca e registra no banco.
        """
        normalized = _normalize_local_path(file_path)
        if not normalized or str(normalized).lower().startswith("content://"):
            raise ValueError("caminho_arquivo_invalido")
        filename = os.path.basename(normalized)
        if not filename:
            raise ValueError("nome_arquivo_invalido")
        if not os.path.exists(normalized):
            raise FileNotFoundError(normalized)
        # Gerar nome unico para evitar colisao
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        safe_filename = f"{timestamp}_{filename}"
        dest_path = os.path.join(LIBRARY_DIR, safe_filename)
        
        try:
            shutil.copy2(normalized, dest_path)
            
            # Tentar contar paginas (se for PDF)
            total_paginas = 0
            if filename.lower().endswith(".pdf"):
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(dest_path)
                    total_paginas = len(reader.pages)
                except:
                    pass
            
            # Salvar no BD
            conn = self.db.conectar()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO biblioteca_pdfs 
                (user_id, nome_arquivo, caminho_arquivo, categoria, total_paginas)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, filename, dest_path, categoria, total_paginas))
            file_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return {
                "id": file_id,
                "nome": filename,
                "path": dest_path,
                "paginas": total_paginas
            }
            
        except Exception as e:
            print(f"[LIBRARY] Erro ao adicionar arquivo: {e}")
            if os.path.exists(dest_path):
                os.remove(dest_path)
            raise e

    def listar_arquivos(self, user_id: int) -> List[Dict]:
        """Lista arquivos do usuario."""
        conn = self.db.conectar()
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM biblioteca_pdfs 
            WHERE user_id = ? 
            ORDER BY data_upload DESC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows

    def excluir_arquivo(self, file_id: int, user_id: int) -> bool:
        """Remove arquivo do banco e do disco."""
        conn = self.db.conectar()
        cursor = conn.cursor()
        
        # Pegar caminho
        cursor.execute("SELECT caminho_arquivo FROM biblioteca_pdfs WHERE id = ? AND user_id = ?", (file_id, user_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False
            
        caminho = row[0]
        
        # Remover do BD
        cursor.execute("DELETE FROM biblioteca_pdfs WHERE id = ?", (file_id,))
        conn.commit()
        conn.close()
        
        # Remover do disco
        if caminho and os.path.exists(caminho):
            try:
                os.remove(caminho)
            except Exception as e:
                print(f"[LIBRARY] Erro ao deletar arquivo fisico: {e}")
                
        return True

    def get_conteudo_arquivo(self, file_id: int) -> str:
        """Lê o texto do arquivo."""
        conn = self.db.conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT caminho_arquivo FROM biblioteca_pdfs WHERE id = ?", (file_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return ""
            
        path = row[0]
        path = _normalize_local_path(path)
        if not os.path.exists(path):
            return ""
            
        # Reutilizar logica de leitura do main (mas simplificada aqui)
        # Idealmente mover _read_uploaded_study_text para um utilitario compartilhado
        # Por enquanto vou duplicar a logica basica ou importar se possivel
        # Vou implementar leitura basica aqui para ser self-contained
        
        ext = os.path.splitext(path)[1].lower()
        if ext == ".pdf":
            try:
                from core.helpers.pdf_ocr import read_pdf_with_ocr_fallback
                return read_pdf_with_ocr_fallback(path)
            except Exception:
                return ""
        else:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except:
                return ""

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# -*- coding: utf-8 -*-
"""Serviço de resumo/pacote: Markdown e exportação PDF simples."""

from __future__ import annotations

from pathlib import Path
from typing import Dict


class StudySummaryService:
    @staticmethod
    def _as_dict(value):
        return value if isinstance(value, dict) else {}

    def safe_file_stub(self, value: str) -> str:
        raw = str(value or "").strip().lower() or "pacote_estudo"
        chars = []
        for ch in raw:
            if ch.isalnum() or ch in ("-", "_"):
                chars.append(ch)
            else:
                chars.append("_")
        normalized = "".join(chars).strip("_")
        while "__" in normalized:
            normalized = normalized.replace("__", "_")
        return normalized[:64] or "pacote_estudo"

    def build_package_markdown(self, pkg: dict) -> str:
        pkg = self._as_dict(pkg)
        dados = self._as_dict(pkg.get("dados"))
        summary = self._as_dict(dados.get("summary_v2"))
        titulo = str(pkg.get("titulo") or "Pacote de Estudo")
        source_nome = str(pkg.get("source_nome") or "-")
        criado_em = str(pkg.get("created_at") or "-")
        resumo_curto = str(
            summary.get("resumo_curto")
            or summary.get("resumo")
            or dados.get("resumo")
            or "Resumo indisponivel."
        ).strip()
        topicos = summary.get("topicos_principais") or summary.get("topicos") or dados.get("topicos") or []
        definicoes = summary.get("definicoes") or []
        checklist = summary.get("checklist_de_estudo") or []
        flashcards = summary.get("sugestoes_flashcards") or dados.get("flashcards") or []
        questoes = summary.get("sugestoes_questoes") or dados.get("questoes") or []

        linhas = [
            f"# {titulo}",
            "",
            f"- Fonte: `{source_nome}`",
            f"- Criado em: `{criado_em}`",
            "",
            "## Resumo curto",
            resumo_curto,
            "",
        ]

        if isinstance(topicos, list) and topicos:
            linhas.append("## Topicos principais")
            for item in topicos[:12]:
                texto = str(item).strip()
                if texto:
                    linhas.append(f"- {texto}")
            linhas.append("")

        if isinstance(definicoes, list) and definicoes:
            linhas.append("## Definicoes")
            for item in definicoes[:12]:
                if isinstance(item, dict):
                    termo = str(item.get("termo") or "Conceito").strip()
                    definicao = str(item.get("definicao") or "").strip()
                else:
                    termo = "Conceito"
                    definicao = str(item).strip()
                if definicao:
                    linhas.append(f"- **{termo}**: {definicao}")
            linhas.append("")

        if isinstance(checklist, list) and checklist:
            linhas.append("## Checklist de estudo")
            for item in checklist[:15]:
                texto = str(item).strip()
                if texto:
                    linhas.append(f"- [ ] {texto}")
            linhas.append("")

        if isinstance(flashcards, list) and flashcards:
            linhas.append("## Sugestoes de flashcards")
            for idx, item in enumerate(flashcards[:20], start=1):
                if isinstance(item, dict):
                    frente = str(item.get("frente") or item.get("front") or "").strip()
                    verso = str(item.get("verso") or item.get("back") or "").strip()
                else:
                    frente = str(item).strip()
                    verso = ""
                if frente:
                    linhas.append(f"{idx}. **Frente:** {frente}")
                    if verso:
                        linhas.append(f"   **Verso:** {verso}")
            linhas.append("")

        if isinstance(questoes, list) and questoes:
            letras = ["A", "B", "C", "D", "E"]
            linhas.append("## Sugestoes de questoes")
            for idx, item in enumerate(questoes[:15], start=1):
                if isinstance(item, dict):
                    enunciado = str(item.get("enunciado") or item.get("pergunta") or "").strip()
                    alternativas = item.get("alternativas") or item.get("opcoes") or []
                    gabarito = item.get("gabarito", item.get("correta_index", 0))
                else:
                    enunciado = str(item).strip()
                    alternativas = []
                    gabarito = 0
                if not enunciado:
                    continue
                linhas.append(f"{idx}. {enunciado}")
                if isinstance(alternativas, list):
                    for a_idx, alt in enumerate(alternativas[:5]):
                        linhas.append(f"   - {letras[a_idx] if a_idx < len(letras) else a_idx + 1}) {str(alt).strip()}")
                try:
                    g_idx = int(gabarito)
                except Exception:
                    g_idx = 0
                g_idx = max(0, g_idx)
                letra = letras[g_idx] if g_idx < len(letras) else str(g_idx + 1)
                linhas.append(f"   - Gabarito: {letra}")
            linhas.append("")
        return "\n".join(linhas).strip() + "\n"

    def build_package_plain_text(self, pkg: dict) -> str:
        md = self.build_package_markdown(pkg)
        lines = []
        for line in md.splitlines():
            txt = str(line or "").strip()
            if not txt:
                lines.append("")
                continue
            txt = txt.replace("**", "").replace("`", "")
            if txt.startswith("# "):
                txt = txt[2:]
            elif txt.startswith("## "):
                txt = txt[3:]
            elif txt.startswith("- [ ] "):
                txt = "[] " + txt[6:]
            elif txt.startswith("- "):
                txt = txt[2:]
            lines.append(txt)
        return "\n".join(lines).strip() + "\n"

    def write_simple_pdf(self, path: Path, text: str):
        def _pdf_escape(raw: str) -> str:
            return str(raw or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        raw_lines = [str(x) for x in (text or "").splitlines()]
        pages = []
        max_lines = 46
        for start in range(0, max(1, len(raw_lines)), max_lines):
            chunk = raw_lines[start:start + max_lines] or [""]
            stream_lines = ["BT", "/F1 11 Tf", "14 TL", "50 790 Td"]
            for i, line in enumerate(chunk):
                safe = _pdf_escape(line[:100])
                if i == 0:
                    stream_lines.append(f"({safe}) Tj")
                else:
                    stream_lines.append(f"T* ({safe}) Tj")
            stream_lines.append("ET")
            pages.append("\n".join(stream_lines).encode("latin-1", errors="replace"))

        obj_count = 3 + (len(pages) * 2) + 1
        font_obj_num = obj_count
        kids_refs = []
        objects = [(1, b"<< /Type /Catalog /Pages 2 0 R >>")]
        first_page_obj = 3
        for i, page_stream in enumerate(pages):
            page_obj = first_page_obj + i * 2
            content_obj = page_obj + 1
            kids_refs.append(f"{page_obj} 0 R")
            page_dict = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 {font_obj_num} 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            ).encode("latin-1")
            content = f"<< /Length {len(page_stream)} >>\nstream\n".encode("latin-1") + page_stream + b"\nendstream"
            objects.append((page_obj, page_dict))
            objects.append((content_obj, content))
        objects.append((2, f"<< /Type /Pages /Kids [{' '.join(kids_refs)}] /Count {len(pages)} >>".encode("latin-1")))
        objects.append((font_obj_num, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))
        objects.sort(key=lambda x: x[0])

        with open(path, "wb") as f:
            f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
            offsets = [0]
            for num, payload in objects:
                offsets.append(f.tell())
                f.write(f"{num} 0 obj\n".encode("latin-1"))
                f.write(payload)
                f.write(b"\nendobj\n")
            xref_pos = f.tell()
            f.write(f"xref\n0 {obj_count + 1}\n".encode("latin-1"))
            f.write(b"0000000000 65535 f \n")
            for obj_num in range(1, obj_count + 1):
                off = offsets[obj_num] if obj_num < len(offsets) else 0
                f.write(f"{off:010d} 00000 n \n".encode("latin-1"))
            f.write(b"trailer\n")
            f.write(f"<< /Size {obj_count + 1} /Root 1 0 R >>\n".encode("latin-1"))
            f.write(b"startxref\n")
            f.write(f"{xref_pos}\n".encode("latin-1"))
            f.write(b"%%EOF\n")

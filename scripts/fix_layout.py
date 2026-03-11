import sys

with open(r'ui\views\quiz_view.py', 'r', encoding='utf-8') as f:
    text = f.read()

target1 = """            option_text = " ".join(str(alt or "").replace("\\r", "\\n").split())
            wrap_width = 30 if sw < 520 else (42 if sw < 760 else 58)
            option_text = textwrap.fill(
                option_text,
                width=wrap_width,
                break_long_words=False,
                break_on_hyphens=False,
            )
            options.append(ft.Radio(value=str(i), label=option_text, fill_color=fill_color, opacity=opacity))"""

replace1 = """            option_text = " ".join(str(alt or "").replace("\\r", "\\n").split())
            bg_color = ft.Colors.TRANSPARENT
            border_color = _color("borda", dark)
            is_selected = (selected == i)
            if is_selected:
                border_color = CORES["primaria"]
                bg_color = CORES["primaria"] + "11"
            
            if is_corrigido and selected is not None:
                if i == correta_idx:
                    border_color = CORES["sucesso"]
                    bg_color = CORES["sucesso"] + "11"
                elif i == selected and i != correta_idx:
                    border_color = CORES["erro"]
                    bg_color = CORES["erro"] + "11"

            opt_container = ft.Container(
                content=ft.Row(
                    [
                        ft.Radio(value=str(i), fill_color=fill_color),
                        ft.Text(option_text, expand=True, size=15, color=_color("texto", dark), weight=ft.FontWeight.W_500 if is_selected else ft.FontWeight.NORMAL)
                    ],
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.padding.symmetric(horizontal=12, vertical=8),
                border_radius=8,
                border=ft.border.all(1.5 if is_selected else 1, border_color),
                bgcolor=bg_color,
                opacity=opacity,
                data=str(i),
                on_click=_on_change,
                ink=True,
                disabled=estado.get("corrigido") or idx in estado.get("confirmados", set())
            )
            options.append(opt_container)"""

target2 = """        def _on_change(e):
            if estado["corrigido"] or idx in estado["confirmados"] or _is_skipped_question(idx):
                return
            valor = getattr(e.control, "value", None)
            if valor in (None, ""):
                valor = getattr(e, "data", None)
            try:"""

replace2 = """        def _on_change(e):
            if estado["corrigido"] or idx in estado["confirmados"] or _is_skipped_question(idx):
                return
            valor = getattr(e.control, "value", None)
            if valor in (None, ""):
                valor = getattr(e.control, "data", None)
            if valor in (None, ""):
                valor = getattr(e, "data", None)
            try:"""

# Convert Windows line endings to matching ones for exact replace
target1_win = target1.replace('\n', '\r\n')
replace1_win = replace1.replace('\n', '\r\n')
target2_win = target2.replace('\n', '\r\n')
replace2_win = replace2.replace('\n', '\r\n')

if target1_win in text and target2_win in text:
    text = text.replace(target1_win, replace1_win)
    text = text.replace(target2_win, replace2_win)
    with open(r'ui\views\quiz_view.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS")
elif target1 in text and target2 in text:
    text = text.replace(target1, replace1)
    text = text.replace(target2, replace2)
    with open(r'ui\views\quiz_view.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS")
else:
    print("FAILED TO MATCH")

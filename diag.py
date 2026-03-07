import traceback
import flet as ft
from ui.design_system import ds_btn_primary, ds_btn_secondary, ds_btn_ghost

if __name__ == "__main__":
    try:
        print("Testando primary...")
        btn = ds_btn_primary("Teste")
        print("Primary OK.")
        
        print("Testando secondary...")
        btn2 = ds_btn_secondary("Teste")
        print("Secondary OK.")

        print("Testando ghost...")
        btn3 = ds_btn_ghost("Teste")
        print("Ghost OK.")

    except Exception as e:
        with open("err.txt", "w") as f:
            f.write(traceback.format_exc())
        print("Erro capturado!")

# -*- coding: utf-8 -*-
"""
Sistema de Sons para Quiz Vance
Compativel com versoes do Flet com e sem suporte a Audio.
"""

from typing import Optional

import flet as ft


class SoundManager:
    """Gerenciador de sons com fallback seguro."""

    def __init__(self, page: ft.Page):
        self._page = page
        self.enabled = True
        self.sounds = {
            "acerto": "https://assets.mixkit.co/active_storage/sfx/2000/2000-preview.mp3",
            "erro": "https://assets.mixkit.co/active_storage/sfx/2955/2955-preview.mp3",
            "level_up": "https://assets.mixkit.co/active_storage/sfx/1435/1435-preview.mp3",
            "click": "https://assets.mixkit.co/active_storage/sfx/2568/2568-preview.mp3",
            "notification": "https://assets.mixkit.co/active_storage/sfx/2354/2354-preview.mp3",
        }
        self.audio_player: Optional[object] = None

        try:
            self._init_audio_player()
        except Exception as e:
            print(f"[WARN] Audio not available: {e}")
            self.enabled = False

    def _init_audio_player(self):
        """Inicializa o player de audio se disponivel na versao do Flet."""
        if not hasattr(ft, "Audio"):
            print("[INFO] ft.Audio not available in this Flet version")
            self.enabled = False
            return

        try:
            # Algumas versoes do Flet exigem src valido no construtor.
            self.audio_player = ft.Audio(
                src=self.sounds["click"],
                autoplay=False,
                volume=0.5,
                balance=0,
            )

            if not any(isinstance(c, ft.Audio) for c in self._page.overlay):
                self._page.overlay.append(self.audio_player)
                self._page.update()
        except Exception as e:
            print(f"[WARN] Error initializing audio: {e}")
            self.enabled = False
            self.audio_player = None

    def _play_sound(self, sound_url: str):
        if not self.enabled or not self.audio_player:
            return

        try:
            self.audio_player.src = sound_url
            self.audio_player.autoplay = True
            self.audio_player.update()
        except Exception as e:
            print(f"[WARN] Error playing sound: {e}")

    def play_acerto(self):
        self._play_sound(self.sounds["acerto"])

    def play_erro(self):
        self._play_sound(self.sounds["erro"])

    def play_level_up(self):
        self._play_sound(self.sounds["level_up"])

    def play_click(self):
        self._play_sound(self.sounds["click"])

    def play_notification(self):
        self._play_sound(self.sounds["notification"])

    def toggle_sound(self):
        self.enabled = not self.enabled
        return self.enabled

    def set_volume(self, volume: float):
        if not self.audio_player:
            return
        try:
            self.audio_player.volume = max(0.0, min(1.0, volume))
            self.audio_player.update()
        except Exception:
            pass


class SoundManagerFallback:
    """Fallback silencioso/visual quando audio nao esta disponivel."""

    def __init__(self, page: ft.Page):
        self._page = page
        self.enabled = True
        print("[INFO] Using SoundManager in silent mode (no audio)")

    def _show_visual_feedback(self, icon: str, color: str):
        # Fallback silencioso: nao tenta renderizar UI para evitar erros
        # durante troca de rotas/eventos.
        return

    def play_acerto(self):
        self._show_visual_feedback("OK", "green")

    def play_erro(self):
        self._show_visual_feedback("ERR", "red")

    def play_level_up(self):
        self._show_visual_feedback("UP", "purple")

    def play_click(self):
        pass

    def play_notification(self):
        self._show_visual_feedback("NOTIF", "blue")

    def toggle_sound(self):
        self.enabled = not self.enabled
        return self.enabled

    def set_volume(self, volume: float):
        pass


def create_sound_manager(page: ft.Page):
    """Factory para criar manager de som sem quebrar a aplicacao."""
    try:
        manager = SoundManager(page)
        if manager.enabled:
            print("[OK] SoundManager initialized with audio")
            return manager

        print("[WARN] Audio unavailable, using fallback")
        return SoundManagerFallback(page)
    except Exception as e:
        print(f"[WARN] Error creating SoundManager: {e}")
        print("[INFO] Using SoundManagerFallback")
        return SoundManagerFallback(page)


class SoundManagerModern:
    """Versao alternativa para Flet com controle Audio funcional."""

    def __init__(self, page: ft.Page):
        self._page = page
        self.enabled = True
        self.sounds = {
            "acerto": "https://assets.mixkit.co/active_storage/sfx/2000/2000-preview.mp3",
            "erro": "https://assets.mixkit.co/active_storage/sfx/2955/2955-preview.mp3",
            "level_up": "https://assets.mixkit.co/active_storage/sfx/1435/1435-preview.mp3",
        }
        self.audio_controls = {}

        if not hasattr(ft, "Audio"):
            self.enabled = False
            return

        try:
            for name, url in self.sounds.items():
                audio = ft.Audio(src=url, autoplay=False, volume=0.5)
                self.audio_controls[name] = audio
                self._page.overlay.append(audio)

            self._page.update()
            print("[OK] Audio initialized successfully")
        except Exception as e:
            print(f"[WARN] Error initializing audio: {e}")
            self.enabled = False

    def _play(self, name: str):
        if not self.enabled or name not in self.audio_controls:
            return

        try:
            audio = self.audio_controls[name]
            audio.autoplay = False
            audio.update()
            audio.autoplay = True
            audio.update()
        except Exception as e:
            print(f"[WARN] Error playing {name}: {e}")

    def play_acerto(self):
        self._play("acerto")

    def play_erro(self):
        self._play("erro")

    def play_level_up(self):
        self._play("level_up")

    def play_click(self):
        pass

    def play_notification(self):
        self.play_level_up()

    def toggle_sound(self):
        self.enabled = not self.enabled
        return self.enabled

    def set_volume(self, volume: float):
        for audio in self.audio_controls.values():
            try:
                audio.volume = max(0.0, min(1.0, volume))
                audio.update()
            except Exception:
                pass


# -*- coding: utf-8 -*-

import unittest

import core.services.quiz_filter_service as qfs_module
from core.services.quiz_filter_service import QuizFilterService


class TestQuizFilterService(unittest.TestCase):
    def test_taxonomy_options_accepts_sections_list(self):
        original = qfs_module.get_quiz_filter_taxonomy
        try:
            qfs_module.get_quiz_filter_taxonomy = lambda: {
                "sections": [
                    {
                        "key": "disciplinas",
                        "options": [{"id": "portugues", "label": "Portugues"}],
                    },
                    {
                        "key": "bancas",
                        "options": [{"id": "fgv", "label": "FGV"}],
                    },
                ]
            }
            data = QuizFilterService.taxonomy_options()
            self.assertEqual(data.get("disciplinas"), [{"id": "portugues", "label": "Portugues"}])
            self.assertEqual(data.get("bancas"), [{"id": "fgv", "label": "FGV"}])
        finally:
            qfs_module.get_quiz_filter_taxonomy = original

    def test_taxonomy_options_accepts_sections_dict(self):
        original = qfs_module.get_quiz_filter_taxonomy
        try:
            qfs_module.get_quiz_filter_taxonomy = lambda: {
                "sections": {
                    "disciplinas": [{"id": "matematica", "label": "Matematica"}],
                }
            }
            data = QuizFilterService.taxonomy_options()
            self.assertEqual(data.get("disciplinas"), [{"id": "matematica", "label": "Matematica"}])
        finally:
            qfs_module.get_quiz_filter_taxonomy = original


if __name__ == "__main__":
    unittest.main()

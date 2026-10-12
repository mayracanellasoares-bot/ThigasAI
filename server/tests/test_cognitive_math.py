import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cognitive_math import solve_simple_arithmetic
from test_app import gateway


class ArithmeticVerifierTests(unittest.TestCase):
    def test_exact_arithmetic_in_portuguese(self):
        examples = {
            'Quanto é 2 + 2?': 'Resultado verificado: **4**.',
            'Calcule (8 - 3) * 4': 'Resultado verificado: **20**.',
            '12,5 / 2': 'Resultado verificado: **6,25**.',
            '2^5': 'Resultado verificado: **32**.',
            '10 / 3': 'Resultado verificado: **10/3 (aprox. 3,33333333333)**.',
            '-7 + 10': 'Resultado verificado: **3**.',
            '5 ÷ 2': 'Resultado verificado: **2,5**.',
            '0,1 + 0,2': 'Resultado verificado: **0,3**.',
        }
        for prompt, answer in examples.items():
            with self.subTest(prompt=prompt):
                self.assertEqual(solve_simple_arithmetic(prompt), answer)

    def test_zero_division(self):
        self.assertEqual(solve_simple_arithmetic('5/0'), 'Divisão por zero não está definida.')

    def test_abstain_for_code_and_complex_questions(self):
        for prompt in ('print(2+2)', 'Explique por que 2 + 2 = 4', 'Oi',
                       '2**999999999999', '99999999999999999999999999 + 1',
                       '1; __import__("os")', 'math.sqrt(4)', '1e999'):
            with self.subTest(prompt=prompt):
                self.assertIsNone(solve_simple_arithmetic(prompt))

    def test_gateway_uses_calculator_without_provider_or_fabricated_tokens(self):
        with gateway.app.test_client() as client:
            login = client.post('/auth/login', data={'password': 'teste-senha-unica-123456789'})
            self.assertEqual(login.status_code, 303)
            with patch.object(gateway, 'ask_maritaca_result') as provider:
                response = client.post('/chat', json={'message': 'Quanto é 2 + 2?'})
            provider.assert_not_called()
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data['answer'], 'Resultado verificado: **4**.')
            self.assertEqual(data['model'], 'thigas-arithmetic-verifier-v1')
            self.assertEqual(data['usage'], {
                'prompt_tokens': None, 'completion_tokens': None, 'total_tokens': None
            })
            self.assertEqual(data['finish_reason'], 'verified')


if __name__ == '__main__':
    unittest.main()

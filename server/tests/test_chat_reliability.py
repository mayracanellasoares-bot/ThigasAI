import unittest
from unittest.mock import patch
from test_app import gateway


class ChatReliabilityTests(unittest.TestCase):
    def test_history_budget_preserves_latest_complete_exchange(self):
        history = [
            {'role': 'user', 'content': 'a' * 40000},
            {'role': 'assistant', 'content': 'b' * 40000},
            {'role': 'user', 'content': 'pergunta recente'},
            {'role': 'assistant', 'content': 'resposta recente'},
        ]
        messages = gateway.build_messages('corrija o resultado', history)
        self.assertLessEqual(sum(len(m['content']) for m in messages[1:]), 60000)
        self.assertEqual(messages[1:], history[-2:] + [{'role': 'user', 'content': 'corrija o resultado'}])

    def test_invalid_json_shape_is_rejected(self):
        with gateway.app.test_client() as client:
            client.post('/auth/login', data={'password': 'teste-senha-unica-123456789'})
            response = client.post('/chat', json=['pergunta'])
        self.assertEqual(response.status_code, 400)

    def test_explicit_maritaca_thinking_routes_to_maritaca(self):
        with patch.object(gateway, 'THIGAS_ENABLE_THINKING', True), patch.object(gateway, 'MARITACA_API_KEY', 'test'):
            self.assertEqual(gateway.choose_model('thinking'), gateway.MARITACA_THINKING_MODEL)

    def test_invalid_mode_does_not_fetch_url(self):
        with patch.object(gateway.link_inspector, 'fetch_public_page') as fetch:
            with gateway.app.test_client() as client:
                client.post('/auth/login', data={'password': 'teste-senha-unica-123456789'})
                response = client.post('/chat', json={'message': 'https://example.com', 'mode': 'invalid'})
        self.assertEqual(response.status_code, 400)
        fetch.assert_not_called()

    def test_duplicate_pending_user_message_is_not_sent_twice(self):
        messages = gateway.build_messages('pergunta', [{'role': 'user', 'content': 'pergunta'}])
        self.assertEqual([m for m in messages if m['role'] == 'user'], [{'role': 'user', 'content': 'pergunta'}])

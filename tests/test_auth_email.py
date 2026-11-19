import ast
import re
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from services.auth_email_service import (
    normalize_auth_email, email_wait_seconds, mark_email_attempt,
    auth_email_error_key,
)


class AuthEmailTests(unittest.TestCase):
    def test_normalization_preserves_mailbox_and_plus_tag(self):
        self.assertEqual(normalize_auth_email('  Name+news@GMAIL.com  '), 'Name+news@gmail.com')
        self.assertEqual(normalize_auth_email('a@bücher.de'), 'a@xn--bcher-kva.de')

    def test_rejects_malformed_and_reserved_addresses(self):
        for value in ('', 'a', 'a@@gmail.com', 'a b@gmail.com', 'a\n@gmail.com',
                      '.a@gmail.com', 'a..b@gmail.com', 'a@-gmail.com',
                      'a@gmail..com', 'a@example.com', 'a@sub.example.org', 'a@foo.test'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_auth_email(value)

    def test_cooldown_boundary_and_no_recipient_storage(self):
        state = {}
        self.assertEqual(email_wait_seconds(state, 0), 0)
        mark_email_attempt(state, 100)
        self.assertEqual(email_wait_seconds(state, 100.1), 60)
        self.assertEqual(email_wait_seconds(state, 159), 1)
        self.assertEqual(email_wait_seconds(state, 160), 0)
        self.assertEqual(list(state.values()), [100])

    def test_rate_limit_error_mapping(self):
        error = Exception('429: email rate limit exceeded')
        self.assertEqual(auth_email_error_key(error), 'auth_email_rate_limited')
        self.assertEqual(auth_email_error_key(Exception('Error sending recovery email')), 'auth_email_unavailable')

    def run_signup(self, email, state=None, error=None):
        # Execute the actual button handler without booting Streamlit or sending email.
        tree = ast.parse(Path(__file__).resolve().parents[1].joinpath('app.py').read_text())
        handler = next(node for node in ast.walk(tree) if isinstance(node, ast.If)
                       and isinstance(node.test, ast.Call)
                       and any(k.arg == 'key' and isinstance(k.value, ast.Constant)
                               and k.value.value == 'reg_btn' for k in node.test.keywords))
        st = SimpleNamespace(session_state=state if state is not None else {},
                             query_params={'megor_visitor': '00000000-0000-0000-0000-000000000000'},
                             error=Mock(), warning=Mock(), success=Mock())
        auth = SimpleNamespace(sign_up=Mock(side_effect=error))
        scope = dict(globals(), st=st, supabase=SimpleNamespace(auth=auth), email_reg=email,
                     password_reg='long-password', t=lambda key, **kw: key)
        exec(compile(ast.Module(body=handler.body, type_ignores=[]), '<signup>', 'exec'), scope)
        return st, auth

    def test_invalid_signup_never_calls_supabase(self):
        st, auth = self.run_signup('test@example.com')
        auth.sign_up.assert_not_called()
        st.error.assert_called_with('auth_email_invalid')

    def test_duplicate_signup_does_not_send_again(self):
        state = {}
        st, auth = self.run_signup('name@gmail.com', state)
        auth.sign_up.assert_called_once()
        self.assertEqual(auth.sign_up.call_args.args[0]['options']['data']['megor_visitor'],
                         '00000000-0000-0000-0000-000000000000')
        st, auth = self.run_signup('name@gmail.com', state)
        auth.sign_up.assert_not_called()
        st.warning.assert_called_once()

    def test_api_rate_limit_is_not_reported_as_success(self):
        st, auth = self.run_signup('name@gmail.com', error=Exception('email rate limit exceeded'))
        st.success.assert_not_called()
        st.error.assert_called_with('auth_email_rate_limited')


if __name__ == '__main__':
    unittest.main()

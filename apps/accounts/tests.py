from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class RegisterViewTests(TestCase):
    def test_register_valid_form_creates_and_logs_in_user(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "testuser",
                "email": "test@example.com",
                "password1": "StrongTestPass123!",
                "password2": "StrongTestPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.assertRedirects(
            response,
            reverse("accounts:login"),
            fetch_redirect_response=False,
        )

        self.assertTrue(User.objects.filter(username="testuser").exists())
        self.assertIn("_auth_user_id", self.client.session)

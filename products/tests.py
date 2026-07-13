from django.test import SimpleTestCase
from django.urls import reverse


class DarajaPaymentTests(SimpleTestCase):
    def test_daraja_view_returns_message_when_credentials_are_missing(self):
        response = self.client.post(
            reverse("daraja"),
            {"phone_number": "254712345678", "amount": "100"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Configuration")

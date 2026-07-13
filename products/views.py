import base64
import json
import os
import re
from datetime import datetime
from urllib import request as urllib_request

from django.http import JsonResponse
from django.shortcuts import render


# Create your views here.
def index(request):
    return render(request, 'index.html')


def about(request):
    return render(request, 'about.html', {'daraja_message': None, 'daraja_error': None})


def contact(request):
    return render(request, 'contact.html')


def gallery(request):
    return render(request, 'gallery.html')


def signup(request):
    return render(request, 'signup.html')


def login(request):
    return render(request, 'login.html')


def get_daraja_settings():
    consumer_key = os.getenv('SAFARICOM_CONSUMER_KEY', '').strip()
    consumer_secret = os.getenv('SAFARICOM_CONSUMER_SECRET', '').strip()
    short_code = os.getenv('SAFARICOM_SHORT_CODE', '').strip()
    passkey = os.getenv('SAFARICOM_PASSKEY', '').strip()
    callback_url = os.getenv('SAFARICOM_CALLBACK_URL', 'http://127.0.0.1:8000/daraja/callback/').strip()

    missing = [
        name for name, value in {
            'SAFARICOM_CONSUMER_KEY': consumer_key,
            'SAFARICOM_CONSUMER_SECRET': consumer_secret,
            'SAFARICOM_SHORT_CODE': short_code,
            'SAFARICOM_PASSKEY': passkey,
        }.items() if not value
    ]

    if missing:
        return None, f"Configuration missing for: {', '.join(missing)}"

    return {
        'consumer_key': consumer_key,
        'consumer_secret': consumer_secret,
        'short_code': short_code,
        'passkey': passkey,
        'callback_url': callback_url,
    }, None


def normalize_phone_number(phone_number):
    digits = re.sub(r'\D', '', phone_number)
    if digits.startswith('0'):
        digits = '254' + digits[1:]
    elif digits.startswith('+254'):
        digits = digits[1:]
    elif digits.startswith('254'):
        pass
    else:
        raise ValueError('Phone number must start with 254 or 0')

    if len(digits) != 12:
        raise ValueError('Phone number must be 12 digits long')
    return digits


def daraja(request):
    daraja_message = None
    daraja_error = None

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', '').strip()
        amount = request.POST.get('amount', '').strip()

        if not phone_number or not amount:
            daraja_error = 'Please provide both your phone number and amount.'
        else:
            try:
                phone = normalize_phone_number(phone_number)
                amount_value = int(float(amount))
            except ValueError as exc:
                daraja_error = str(exc)
            else:
                if amount_value <= 0:
                    daraja_error = 'Amount must be greater than zero.'
                else:
                    settings, config_error = get_daraja_settings()
                    if config_error:
                        daraja_error = config_error
                    else:
                        try:
                            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                            password = base64.b64encode(
                                f"{settings['short_code']}{settings['passkey']}{timestamp}".encode()
                            ).decode()

                            access_token_url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
                            auth = base64.b64encode(
                                f"{settings['consumer_key']}:{settings['consumer_secret']}".encode()
                            ).decode()

                            token_request = urllib_request.Request(
                                access_token_url,
                                headers={'Authorization': f'Basic {auth}'},
                            )
                            with urllib_request.urlopen(token_request, timeout=10) as token_response:
                                token_data = json.loads(token_response.read().decode())
                                access_token = token_data.get('access_token')

                            if not access_token:
                                raise ValueError('No access token received from Daraja.')

                            payload = {
                                'BusinessShortCode': settings['short_code'],
                                'Password': password,
                                'Timestamp': timestamp,
                                'TransactionType': 'CustomerPayBillOnline',
                                'Amount': amount_value,
                                'PartyA': phone,
                                'PartyB': settings['short_code'],
                                'PhoneNumber': phone,
                                'CallBackURL': settings['callback_url'],
                                'AccountReference': 'MyDjangoShop',
                                'TransactionDesc': 'Daraja payment prompt',
                            }

                            stk_request = urllib_request.Request(
                                'https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest',
                                data=json.dumps(payload).encode(),
                                headers={
                                    'Authorization': f'Bearer {access_token}',
                                    'Content-Type': 'application/json',
                                },
                                method='POST',
                            )
                            with urllib_request.urlopen(stk_request, timeout=10) as stk_response:
                                stk_data = json.loads(stk_response.read().decode())

                            if stk_data.get('ResponseCode') == '0':
                                daraja_message = 'Daraja prompt sent. Please complete the payment on your phone.'
                            else:
                                daraja_error = stk_data.get('ResponseDescription', 'Daraja request failed.')
                        except Exception as exc:
                            daraja_error = f'Daraja request failed: {exc}'

    return render(request, 'about.html', {
        'daraja_message': daraja_message,
        'daraja_error': daraja_error,
    })


def daraja_callback(request):
    return JsonResponse({'status': 'ok', 'message': 'Daraja callback received'})

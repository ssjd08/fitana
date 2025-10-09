"""
Payment gateway integrations.
Currently supports ZarinPal payment gateway and MockGateway for testing.
"""
import requests
import uuid
import random
from django.conf import settings
from typing import Dict, Optional

class MockGateway:
    """
    Mock payment gateway for testing purposes.
    Simulates payment gateway behavior without real transactions.
    
    Usage:
        gateway = MockGateway()
        result = gateway.request_payment(50000, "Test payment")
    """
    
    # In-memory storage for mock payments
    _mock_payments = {}
    
    def __init__(self, success_rate: float = 0.9):
        """
        Initialize mock gateway.
        
        Args:
            success_rate: Probability of successful payment (0.0 to 1.0)
                         Default 0.9 means 90% success rate
        """
        self.success_rate = success_rate
    
    def request_payment(
        self,
        amount: int,
        description: str,
        mobile: Optional[str] = None,
        email: Optional[str] = None,
        callback_url: Optional[str] = None
    ) -> Dict:
        """
        Mock payment request.
        
        Args:
            amount: Amount in Rials
            description: Payment description
            mobile: User's mobile (optional)
            email: User's email (optional)
            callback_url: Callback URL (optional)
        
        Returns:
            dict: Mock payment response
        """
        # Generate mock authority
        authority = f"MOCK{uuid.uuid4().hex[:30].upper()}"
        
        # Simulate random success/failure based on success_rate
        if random.random() > self.success_rate:
            return {
                'success': False,
                'error': 'Mock gateway simulated failure',
                'code': -12
            }
        
        # Store payment info for later verification
        self._mock_payments[authority] = {
            'amount': amount,
            'description': description,
            'mobile': mobile,
            'email': email,
            'status': 'pending',
            'verified': False
        }
        
        return {
            'success': True,
            'authority': authority,
            'payment_url': f'http://mock-gateway.test/pay/{authority}',
            'code': 100,
            'message': 'Mock payment initialized'
        }
    
    def verify_payment(self, authority: str, amount: int) -> Dict:
        """
        Mock payment verification.
        
        Args:
            authority: Authority code from request_payment
            amount: Original payment amount
        
        Returns:
            dict: Mock verification response
        """
        # Check if payment exists
        if authority not in self._mock_payments:
            return {
                'success': False,
                'error': 'Payment not found',
                'code': -10
            }
        
        payment = self._mock_payments[authority]
        
        # Check if already verified
        if payment['verified']:
            return {
                'success': True,
                'ref_id': f"MOCKREF{authority[-10:]}",
                'message': 'Payment already verified',
                'code': 101
            }
        
        # Check amount match
        if payment['amount'] != amount:
            return {
                'success': False,
                'error': 'Amount mismatch',
                'code': -52
            }
        
        # Simulate random verification failure (10% chance)
        if random.random() > 0.9:
            return {
                'success': False,
                'error': 'Mock verification failed',
                'code': -53
            }
        
        # Mark as verified
        payment['verified'] = True
        payment['status'] = 'verified'
        
        # Generate mock card number (last 4 digits)
        mock_card_pan = f"************{random.randint(1000, 9999)}"
        
        return {
            'success': True,
            'ref_id': f"MOCKREF{authority[-10:]}",
            'card_pan': mock_card_pan,
            'card_hash': f"HASH{uuid.uuid4().hex[:16].upper()}",
            'fee_type': 'Merchant',
            'fee': int(amount * 0.01),  # 1% fee
            'code': 100,
            'message': 'Mock payment verified successfully'
        }
    
    def unverified_transactions(self) -> Dict:
        """
        Get list of unverified mock transactions.
        
        Returns:
            dict: List of unverified authorities
        """
        unverified = [
            authority for authority, payment in self._mock_payments.items()
            if not payment['verified']
        ]
        
        return {
            'success': True,
            'authorities': unverified
        }
    
    @classmethod
    def reset(cls):
        """Reset all mock payments (useful for testing)."""
        cls._mock_payments.clear()
    
    @classmethod
    def get_payment_info(cls, authority: str) -> Optional[Dict]:
        """Get stored payment info (for debugging)."""
        return cls._mock_payments.get(authority)
    
    @classmethod
    def list_all_payments(cls) -> Dict:
        """List all mock payments (for debugging)."""
        return cls._mock_payments.copy()
    
    
class ZarinPalGateway:
    """
    ZarinPal payment gateway integration.
    
    Documentation: https://docs.zarinpal.com/paymentGateway/
    """
    
    # ZarinPal API endpoints
    SANDBOX_REQUEST_URL = 'https://sandbox.zarinpal.com/pg/v4/payment/request.json'
    SANDBOX_VERIFY_URL = 'https://sandbox.zarinpal.com/pg/v4/payment/verify.json'
    SANDBOX_START_PAY = 'https://sandbox.zarinpal.com/pg/StartPay/'
    
    PRODUCTION_REQUEST_URL = 'https://api.zarinpal.com/pg/v4/payment/request.json'
    PRODUCTION_VERIFY_URL = 'https://api.zarinpal.com/pg/v4/payment/verify.json'
    PRODUCTION_START_PAY = 'https://www.zarinpal.com/pg/StartPay/'
    
    def __init__(self):
        """Initialize ZarinPal gateway with settings."""
        self.merchant_id = getattr(settings, 'ZARINPAL_MERCHANT_ID', '')
        self.callback_url = getattr(settings, 'ZARINPAL_CALLBACK_URL', '')
        self.sandbox = getattr(settings, 'ZARINPAL_SANDBOX', True)
        
        # Set URLs based on environment
        if self.sandbox:
            self.request_url = self.SANDBOX_REQUEST_URL
            self.verify_url = self.SANDBOX_VERIFY_URL
            self.start_pay_url = self.SANDBOX_START_PAY
        else:
            self.request_url = self.PRODUCTION_REQUEST_URL
            self.verify_url = self.PRODUCTION_VERIFY_URL
            self.start_pay_url = self.PRODUCTION_START_PAY
    
    def request_payment(
        self, 
        amount: int, 
        description: str,
        mobile: Optional[str] = None,
        email: Optional[str] = None,
        callback_url: Optional[str] = None
    ) -> Dict:
        """
        Request payment from ZarinPal.
        
        Args:
            amount: Amount in Rials (IRR)
            description: Payment description
            mobile: User's mobile number (optional)
            email: User's email (optional)
            callback_url: Custom callback URL (optional, uses default if not provided)
        
        Returns:
            dict: {
                'success': bool,
                'authority': str,  # If successful
                'payment_url': str,  # If successful
                'error': str,  # If failed
                'code': int  # ZarinPal response code
            }
        """
        if not self.merchant_id:
            return {
                'success': False,
                'error': 'Merchant ID not configured',
                'code': -1
            }
        
        data = {
            'merchant_id': self.merchant_id,
            'amount': int(amount),
            'description': description,
            'callback_url': callback_url or self.callback_url,
        }
        
        # Add optional fields if provided
        metadata = []
        if mobile:
            data['mobile'] = mobile
            metadata.append({'mobile': mobile})
        if email:
            data['email'] = email
            metadata.append({'email': email})
        
        if metadata:
            data['metadata'] = metadata
        
        try:
            response = requests.post(
                self.request_url,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                data_section = result.get('data', {})
                code = data_section.get('code')
                
                if code == 100:
                    # Success
                    authority = data_section.get('authority')
                    return {
                        'success': True,
                        'authority': authority,
                        'payment_url': f'{self.start_pay_url}{authority}',
                        'code': code
                    }
                else:
                    # ZarinPal returned error
                    errors = result.get('errors', {})
                    return {
                        'success': False,
                        'error': errors.get('message', 'Unknown error from ZarinPal'),
                        'code': code,
                        'validations': errors.get('validations', [])
                    }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}',
                    'code': response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout - ZarinPal server did not respond',
                'code': -2
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': 'Connection error - Could not connect to ZarinPal',
                'code': -3
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Request failed: {str(e)}',
                'code': -4
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'code': -5
            }
    
    def verify_payment(self, authority: str, amount: int) -> Dict:
        """
        Verify payment with ZarinPal.
        
        Args:
            authority: Authority code from payment request
            amount: Original payment amount in Rials
        
        Returns:
            dict: {
                'success': bool,
                'ref_id': str,  # If successful
                'card_pan': str,  # Masked card number
                'card_hash': str,  # Card hash
                'fee_type': str,  # Fee type (Merchant/Payer)
                'fee': int,  # Transaction fee
                'error': str,  # If failed
                'code': int  # ZarinPal response code
            }
        """
        if not self.merchant_id:
            return {
                'success': False,
                'error': 'Merchant ID not configured',
                'code': -1
            }
        
        data = {
            'merchant_id': self.merchant_id,
            'authority': authority,
            'amount': int(amount)
        }
        
        try:
            response = requests.post(
                self.verify_url,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                data_section = result.get('data', {})
                code = data_section.get('code')
                
                if code == 100:
                    # Payment verified successfully
                    return {
                        'success': True,
                        'ref_id': str(data_section.get('ref_id')),
                        'card_pan': data_section.get('card_pan', ''),
                        'card_hash': data_section.get('card_hash', ''),
                        'fee_type': data_section.get('fee_type', ''),
                        'fee': data_section.get('fee', 0),
                        'code': code
                    }
                elif code == 101:
                    # Already verified
                    return {
                        'success': True,
                        'ref_id': str(data_section.get('ref_id')),
                        'message': 'Payment already verified',
                        'code': code
                    }
                else:
                    # Verification failed
                    errors = result.get('errors', {})
                    return {
                        'success': False,
                        'error': errors.get('message', 'Verification failed'),
                        'code': code,
                        'validations': errors.get('validations', [])
                    }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}',
                    'code': response.status_code
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout - ZarinPal server did not respond',
                'code': -2
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': 'Connection error - Could not connect to ZarinPal',
                'code': -3
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Request failed: {str(e)}',
                'code': -4
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'code': -5
            }
    
    def unverified_transactions(self) -> Dict:
        """
        Get list of unverified transactions.
        Useful for finding pending payments.
        
        Returns:
            dict: {
                'success': bool,
                'authorities': list,  # List of unverified authorities
                'error': str  # If failed
            }
        """
        url = 'https://api.zarinpal.com/pg/v4/payment/unVerified.json'
        
        data = {
            'merchant_id': self.merchant_id
        }
        
        try:
            response = requests.post(url, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('data', {}).get('code') == 100:
                    return {
                        'success': True,
                        'authorities': result.get('data', {}).get('authorities', [])
                    }
                else:
                    return {
                        'success': False,
                        'error': result.get('errors', {}).get('message', 'Failed to get unverified transactions')
                    }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


# Error code reference for ZarinPal
ZARINPAL_ERROR_CODES = {
    -1: "Merchant ID not configured",
    -2: "Request timeout",
    -3: "Connection error",
    -4: "Request failed",
    -5: "Unexpected error",
    -9: "Validation error - IP or Merchant ID is incorrect",
    -10: "Token not found",
    -11: "Token already used",
    -12: "Error in inputs (amount or merchant_id)",
    -15: "Terminal access denied",
    -16: "Access level is insufficient",
    -17: "User access denied for receiving payment",
    -30: "Terminal not allowed",
    -31: "Issue in getting token",
    -32: "Shaparak limit reached",
    -33: "Amount limit reached",
    -34: "Token already used in verify",
    -35: "Invalid callback URL",
    -40: "Allowed IPs do not match",
    -41: "Invalid currency",
    -42: "Currency conversion error",
    -50: "Amount is too low",
    -51: "Amount is too high",
    -52: "Incorrect amount",
    -53: "Payment already processed",
    -54: "Failed transaction access",
    100: "Success",
    101: "Payment already verified"
}
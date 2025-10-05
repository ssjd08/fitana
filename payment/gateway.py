# payment/gateway.py
import random
import string
import time
from typing import Dict, Any
from decimal import Decimal


class MockGateway:
    """Mock payment gateway for testing purposes."""
    
    @staticmethod
    def create_payment(amount: Decimal, card_number: str, description: str = "") -> Dict[str, Any]:
        """
        Create a payment request in the mock gateway.
        
        Args:
            amount: Payment amount
            card_number: Card number (will be masked)
            description: Payment description
            
        Returns:
            Dict containing gateway response
        """
        # Simulate network delay
        time.sleep(0.5)
        
        # Generate mock IDs
        ref_id = ''.join(random.choices(string.digits, k=10))
        tracking_code = ''.join(random.choices(string.digits, k=8))
        authority = ''.join(random.choices(string.ascii_uppercase + string.digits, k=36))
        
        # Simulate random success/failure (90% success rate)
        success = random.random() > 0.1
        
        if success:
            return {
                "status": "success",
                "ref_id": ref_id,
                "tracking_code": tracking_code,
                "authority": authority,
                "message": "Payment created successfully",
                "gateway_url": f"https://mock-gateway.com/pay/{authority}",
                "amount": str(amount),
                "card_last_four": card_number[-4:] if len(card_number) >= 4 else "****"
            }
        else:
            # Simulate various error scenarios
            errors = [
                {"code": "INVALID_CARD", "message": "Invalid card number"},
                {"code": "INSUFFICIENT_FUNDS", "message": "Insufficient funds"},
                {"code": "CARD_BLOCKED", "message": "Card is blocked"},
                {"code": "GATEWAY_ERROR", "message": "Gateway temporarily unavailable"}
            ]
            error = random.choice(errors)
            
            return {
                "status": "error",
                "error_code": error["code"],
                "message": error["message"],
                "ref_id": ref_id
            }
    
    @staticmethod
    def verify_payment(ref_id: str) -> Dict[str, Any]:
        """
        Verify a payment in the mock gateway.
        
        Args:
            ref_id: Reference ID from payment creation
            
        Returns:
            Dict containing verification response
        """
        # Simulate network delay
        time.sleep(0.3)
        
        # Simulate verification results (80% success rate)
        success = random.random() > 0.2
        
        if success:
            return {
                "status": "success",
                "ref_id": ref_id,
                "tracking_code": ''.join(random.choices(string.digits, k=8)),
                "card_hash": ''.join(random.choices(string.hexdigits.lower(), k=16)),
                "verified": True,
                "message": "Payment verified successfully"
            }
        else:
            # Simulate verification failures
            errors = [
                {"code": "NOT_VERIFIED", "message": "Payment not verified by user"},
                {"code": "ALREADY_VERIFIED", "message": "Payment already verified"},
                {"code": "EXPIRED", "message": "Payment verification expired"},
                {"code": "NOT_FOUND", "message": "Payment not found"}
            ]
            error = random.choice(errors)
            
            return {
                "status": "error",
                "error_code": error["code"],
                "message": error["message"],
                "ref_id": ref_id,
                "verified": False
            }
    
    @staticmethod
    def refund_payment(ref_id: str, amount: Decimal = None) -> Dict[str, Any]: # type: ignore
        """
        Refund a payment in the mock gateway.
        
        Args:
            ref_id: Reference ID of the original payment
            amount: Amount to refund (None for full refund)
            
        Returns:
            Dict containing refund response
        """
        # Simulate network delay
        time.sleep(0.4)
        
        # Simulate refund success (95% success rate)
        success = random.random() > 0.05
        
        if success:
            return {
                "status": "success",
                "ref_id": ref_id,
                "refund_id": ''.join(random.choices(string.digits, k=10)),
                "message": "Refund processed successfully",
                "refund_amount": str(amount) if amount else "full"
            }
        else:
            return {
                "status": "error",
                "error_code": "REFUND_FAILED",
                "message": "Refund processing failed",
                "ref_id": ref_id
            }


class ZarinPalGateway:
    """
    Real ZarinPal gateway implementation.
    This is a placeholder for actual ZarinPal integration.
    """
    
    MERCHANT_ID = "YOUR_MERCHANT_ID"  # Replace with actual merchant ID
    SANDBOX_URL = "https://sandbox.zarinpal.com/pg/rest/WebGate/"
    PRODUCTION_URL = "https://www.zarinpal.com/pg/rest/WebGate/"
    
    def __init__(self, sandbox=True):
        self.base_url = self.SANDBOX_URL if sandbox else self.PRODUCTION_URL
        self.sandbox = sandbox
    
    def create_payment(self, amount: int, description: str, callback_url: str) -> Dict[str, Any]:
        """
        Create payment request with ZarinPal.
        
        Note: This is a placeholder implementation.
        You'll need to implement actual API calls to ZarinPal.
        """
        import requests
        
        data = {
            'MerchantID': self.MERCHANT_ID,
            'Amount': amount,
            'Description': description,
            'CallbackURL': callback_url,
        }
        
        try:
            response = requests.post(
                f"{self.base_url}PaymentRequest.json",
                json=data,
                timeout=30
            )
            result = response.json()
            
            if result['Status'] == 100:
                return {
                    'status': 'success',
                    'authority': result['Authority'],
                    'payment_url': f"https://sandbox.zarinpal.com/pg/StartPay/{result['Authority']}" if self.sandbox else f"https://www.zarinpal.com/pg/StartPay/{result['Authority']}"
                }
            else:
                return {
                    'status': 'error',
                    'error_code': result['Status'],
                    'message': 'Payment creation failed'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error_code': 'NETWORK_ERROR',
                'message': str(e)
            }
    
    def verify_payment(self, authority: str, amount: int) -> Dict[str, Any]:
        """
        Verify payment with ZarinPal.
        
        Note: This is a placeholder implementation.
        """
        import requests
        
        data = {
            'MerchantID': self.MERCHANT_ID,
            'Authority': authority,
            'Amount': amount,
        }
        
        try:
            response = requests.post(
                f"{self.base_url}PaymentVerification.json",
                json=data,
                timeout=30
            )
            result = response.json()
            
            if result['Status'] == 100:
                return {
                    'status': 'success',
                    'ref_id': result['RefID'],
                    'verified': True
                }
            else:
                return {
                    'status': 'error',
                    'error_code': result['Status'],
                    'message': 'Payment verification failed'
                }
        except Exception as e:
            return {
                'status': 'error',
                'error_code': 'NETWORK_ERROR',
                'message': str(e)
            }
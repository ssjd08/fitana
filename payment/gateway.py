import random
import uuid

class MockGateway:
    """Simulates a card payment gateway."""

    @staticmethod
    def create_payment(amount, card_number, description=None):
        """Simulate sending payment request to gateway."""
        return {
            "ref_id": str(uuid.uuid4()),
            "tracking_code": str(uuid.uuid4())[:12],
            "status": "pending",
            "gateway_message": "Payment initiated successfully",
        }

    @staticmethod
    def verify_payment(ref_id):
        """Simulate verifying payment. 80% chance success."""
        success = random.random() < 0.8
        return {
            "status": "success" if success else "failed",
            "gateway_message": "Payment verified" if success else "Payment failed",
        }

from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import PhoneOTP


class Command(BaseCommand):
    help = 'Clean up expired OTP records from the database'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
    
    def handle(self, *args, **options):
        # Get expired OTPs
        expired_otps = PhoneOTP.objects.filter(expires_at__lt=timezone.now())
        count = expired_otps.count()
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would delete {count} expired OTP records')
            )
            if count > 0:
                self.stdout.write('Expired OTPs:')
                for otp in expired_otps[:10]:  # Show first 10
                    self.stdout.write(f'  - {otp.phone}: {otp.code} (expired: {otp.expires_at})')
                if count > 10:
                    self.stdout.write(f'  ... and {count - 10} more')
        else:
            # Actually delete expired OTPs
            deleted_count, _ = expired_otps.delete()
            
            if deleted_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully cleaned up {deleted_count} expired OTP records')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS('No expired OTP records found to clean up')
                )
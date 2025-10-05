from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def generate_user_plan_async(self, plan_generation_id):
    """Async task to generate user plan"""
    try:
        from .services import PlanGenerationService
        
        success = PlanGenerationService.generate_user_plan(plan_generation_id)
        
        if not success:
            logger.error(f"Plan generation failed for ID: {plan_generation_id}")
            raise Exception("Plan generation failed")
        
        logger.info(f"Plan generation completed successfully for ID: {plan_generation_id}")
        return f"Plan generated successfully for {plan_generation_id}"
        
    except Exception as exc:
        logger.error(f"Task failed for plan generation {plan_generation_id}: {str(exc)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
        
        # If max retries reached, update the plan generation status
        try:
            from .models import PlanGeneration
            plan_gen = PlanGeneration.objects.get(id=plan_generation_id)
            plan_gen.status = 'failed'
            plan_gen.error_message = f"Max retries exceeded: {str(exc)}"
            plan_gen.save()
        except:
            pass
        
        raise exc


@shared_task
def cleanup_failed_generations():
    """Cleanup old failed plan generations"""
    from django.utils import timezone
    from datetime import timedelta
    from .models import PlanGeneration
    
    cutoff_date = timezone.now() - timedelta(days=7)
    
    failed_generations = PlanGeneration.objects.filter(
        status='failed',
        created_at__lt=cutoff_date
    )
    
    count = failed_generations.count()
    failed_generations.delete()
    
    logger.info(f"Cleaned up {count} failed plan generations")
    return f"Cleaned up {count} failed generations"


@shared_task
def send_plan_ready_notification(user_id):
    """Send notification when plan is ready"""
    try:
        from django.contrib.auth import get_user_model
        # from .utils import send_email_notification  # Implement your notification system
        
        User = get_user_model()
        user = User.objects.get(id=user_id)
        
        # TODO: Implement your notification system
        # send_email_notification(
        #     user.email,
        #     "Your Personalized Plan is Ready!",
        #     "plan_ready_template.html",
        #     context={'user': user}
        # )
        
        logger.info(f"Plan ready notification sent to user {user.username}")
        return f"Notification sent to {user.username}"
        
    except Exception as e:
        logger.error(f"Failed to send notification to user {user_id}: {str(e)}")
        raise
        
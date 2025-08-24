import json
import logging
from typing import Dict, Any, Tuple
from django.utils import timezone
from django.db import transaction
from .models import PlanGeneration, WorkoutPlan, DietPlan, UserPlanSummary, UserProgress
from questionnaire.models import UserGoal, Answer

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI integration"""
    
    @staticmethod
    def generate_plans(user_goal: UserGoal) -> Dict[str, Any]:
        """
        Generate diet and workout plans using AI
        Replace this with your actual AI integration (OpenAI, Claude, etc.)
        """
        # Prepare questionnaire data
        questionnaire_data = AIService._prepare_questionnaire_data(user_goal)
        
        # Create AI prompt
        prompt = AIService._create_ai_prompt(questionnaire_data)
        
        # TODO: Replace with actual AI API call
        # response = openai.ChatCompletion.create(
        #     model="gpt-4",
        #     messages=[{"role": "user", "content": prompt}],
        #     temperature=0.7
        # )
        
        # For now, return dummy response
        return AIService._create_dummy_response(questionnaire_data)
    
    @staticmethod
    def _prepare_questionnaire_data(user_goal: UserGoal) -> Dict[str, Any]:
        """Prepare questionnaire data for AI"""
        answers = Answer.objects.filter(user=user_goal.user)
        
        data = {
            'goal': user_goal.goal.name,
            'user_info': {
                'age': None,
                'gender': None,
                'weight': None,
                'height': None,
                'activity_level': None,
                'dietary_restrictions': [],
                'fitness_experience': None,
                'available_equipment': [],
                'time_availability': None,
                'preferences': {}
            }
        }
        
        # Extract answers and map to structured data
        for answer in answers:
            question_text = answer.question.question.lower()
            answer_value = None
            if answer.text_answer:
                answer_value = answer.text_answer
            elif answer.numeric_answer:
                answer_value = answer.numeric_answer
            elif answer.choice_answer:
                answer_value = answer.choice_answer.choice  # or whatever field has the choice text
            elif answer.multi_choice_answer.exists():
                answer_value = [choice.text for choice in answer.multi_choice_answer.all()]
            
            # Map common question patterns to structured data
            if 'age' in question_text:
                data['user_info']['age'] = answer_value
            elif 'gender' in question_text:
                data['user_info']['gender'] = answer_value
            elif 'weight' in question_text:
                data['user_info']['weight'] = answer_value
            elif 'height' in question_text:
                data['user_info']['height'] = answer_value
            elif 'activity' in question_text:
                data['user_info']['activity_level'] = answer_value
            elif 'dietary' in question_text or 'food' in question_text:
                data['user_info']['dietary_restrictions'].append(answer_value)
            elif 'equipment' in question_text:
                data['user_info']['available_equipment'] = answer_value
            elif 'time' in question_text:
                data['user_info']['time_availability'] = answer_value
            else:
                # Store other answers as preferences
                data['user_info']['preferences'][question_text] = answer_value
        
        return data
    
    @staticmethod
    def _create_ai_prompt(data: Dict[str, Any]) -> str:
        """Create AI prompt for plan generation"""
        user_info = data['user_info']
        goal = data['goal']
        
        prompt = f"""
        Create a personalized {goal} plan for a user with the following information:
        
        Goal: {goal}
        Age: {user_info.get('age', 'Not specified')}
        Gender: {user_info.get('gender', 'Not specified')}
        Weight: {user_info.get('weight', 'Not specified')} kg
        Height: {user_info.get('height', 'Not specified')} cm
        Activity Level: {user_info.get('activity_level', 'Not specified')}
        Dietary Restrictions: {', '.join(user_info.get('dietary_restrictions', []))}
        Available Equipment: {', '.join(user_info.get('available_equipment', []))}
        Time Availability: {user_info.get('time_availability', 'Not specified')}
        
        Additional Preferences: {json.dumps(user_info.get('preferences', {}), indent=2)}
        
        Please provide a comprehensive response in the following JSON format:
        {{
            "workout_plan": {{
                "name": "Plan name",
                "description": "Plan description",
                "difficulty_level": "beginner/intermediate/advanced",
                "duration_weeks": 12,
                "sessions_per_week": 4,
                "workout_schedule": {{
                    "weekly_schedule": {{
                        "monday": {{"focus": "Upper Body", "exercises": [...]}},
                        "tuesday": {{"focus": "Cardio", "exercises": [...]}},
                        "wednesday": {{"focus": "Rest", "exercises": []}},
                        "thursday": {{"focus": "Lower Body", "exercises": [...]}},
                        "friday": {{"focus": "Full Body", "exercises": [...]}},
                        "saturday": {{"focus": "Cardio", "exercises": [...]}},
                        "sunday": {{"focus": "Rest", "exercises": []}}
                    }}
                }},
                "exercises": [
                    {{
                        "name": "Push-ups",
                        "category": "Strength",
                        "muscle_groups": ["chest", "shoulders", "triceps"],
                        "sets": 3,
                        "reps": "10-15",
                        "instructions": "Detailed instructions..."
                    }}
                ],
                "equipment_needed": ["dumbbells", "mat"]
            }},
            "diet_plan": {{
                "name": "Diet plan name",
                "description": "Diet plan description",
                "diet_type": "balanced/low_carb/high_protein/etc",
                "daily_calorie_target": 2000,
                "duration_weeks": 12,
                "protein_percentage": 25,
                "carb_percentage": 45,
                "fat_percentage": 30,
                "meal_plan": {{
                    "weekly_meals": {{
                        "monday": {{
                            "breakfast": {{"name": "Oatmeal", "calories": 350, "ingredients": [...]}},
                            "lunch": {{"name": "Chicken Salad", "calories": 450, "ingredients": [...]}},
                            "dinner": {{"name": "Salmon & Vegetables", "calories": 500, "ingredients": [...]}},
                            "snacks": [
                                {{"name": "Apple", "calories": 80, "ingredients": [...]}}
                            ]
                        }}
                    }}
                }},
                "food_restrictions": [],
                "preferred_foods": [],
                "shopping_list": [
                    {{"item": "Chicken breast", "quantity": "2 lbs", "category": "Protein"}},
                    {{"item": "Broccoli", "quantity": "3 heads", "category": "Vegetables"}}
                ]
            }}
        }}
        
        Make sure the plan is realistic, safe, and tailored to the user's specific needs and constraints."""
        
        return prompt
    
    @staticmethod
    def _create_dummy_response(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create dummy AI response for testing"""
        goal = data['goal']
        user_info = data['user_info']
        
        # Determine difficulty based on fitness experience
        fitness_exp = user_info.get('fitness_experience', 'beginner')
        if fitness_exp in ['advanced', 'expert']:
            difficulty = 'advanced'
        elif fitness_exp in ['intermediate', 'some']:
            difficulty = 'intermediate'
        else:
            difficulty = 'beginner'
        
        # Determine calorie target based on goal and user info
        base_calories = 2000
        if goal == 'lose_weight':
            calorie_target = base_calories - 300
        elif goal == 'gain_weight':
            calorie_target = base_calories + 400
        else:
            calorie_target = base_calories
        
        return {
            "workout_plan": {
                "name": f"{goal.replace('_', ' ').title()} Workout Plan",
                "description": f"A comprehensive {difficulty} level workout plan designed to help you {goal.replace('_', ' ')}.",
                "difficulty_level": difficulty,
                "duration_weeks": 12,
                "sessions_per_week": 4,
                "workout_schedule": {
                    "weekly_schedule": {
                        "monday": {"focus": "Upper Body", "exercises": ["push-ups", "pull-ups", "dumbbell rows"]},
                        "tuesday": {"focus": "Cardio", "exercises": ["running", "cycling", "burpees"]},
                        "wednesday": {"focus": "Rest", "exercises": []},
                        "thursday": {"focus": "Lower Body", "exercises": ["squats", "lunges", "deadlifts"]},
                        "friday": {"focus": "Full Body", "exercises": ["mountain climbers", "planks", "jumping jacks"]},
                        "saturday": {"focus": "Cardio", "exercises": ["swimming", "hiking", "dance"]},
                        "sunday": {"focus": "Rest", "exercises": []}
                    }
                },
                "exercises": [
                    {
                        "name": "Push-ups",
                        "category": "Strength",
                        "muscle_groups": ["chest", "shoulders", "triceps"],
                        "sets": 3,
                        "reps": "10-15",
                        "instructions": "Start in plank position, lower body until chest nearly touches floor, push back up."
                    },
                    {
                        "name": "Squats",
                        "category": "Strength",
                        "muscle_groups": ["quadriceps", "glutes", "hamstrings"],
                        "sets": 3,
                        "reps": "12-20",
                        "instructions": "Stand with feet shoulder-width apart, lower hips back and down, return to standing."
                    }
                ],
                "equipment_needed": ["dumbbells", "yoga mat", "resistance bands"]
            },
            "diet_plan": {
                "name": f"{goal.replace('_', ' ').title()} Nutrition Plan",
                "description": f"A balanced nutrition plan to support your {goal.replace('_', ' ')} goals.",
                "diet_type": "balanced",
                "daily_calorie_target": calorie_target,
                "duration_weeks": 12,
                "protein_percentage": 25,
                "carb_percentage": 45,
                "fat_percentage": 30,
                "meal_plan": {
                    "weekly_meals": {
                        "monday": {
                            "breakfast": {"name": "Oatmeal with Berries", "calories": 350, "ingredients": ["oats", "blueberries", "milk", "honey"]},
                            "lunch": {"name": "Grilled Chicken Salad", "calories": 450, "ingredients": ["chicken breast", "mixed greens", "tomatoes", "olive oil"]},
                            "dinner": {"name": "Baked Salmon with Vegetables", "calories": 500, "ingredients": ["salmon fillet", "broccoli", "sweet potato", "herbs"]},
                            "snacks": [
                                {"name": "Greek Yogurt", "calories": 120, "ingredients": ["greek yogurt", "almonds"]}
                            ]
                        }
                    }
                },
                "food_restrictions": user_info.get('dietary_restrictions', []),
                "preferred_foods": [],
                "shopping_list": [
                    {"item": "Chicken breast", "quantity": "2 lbs", "category": "Protein"},
                    {"item": "Salmon fillets", "quantity": "1 lb", "category": "Protein"},
                    {"item": "Mixed greens", "quantity": "2 bags", "category": "Vegetables"},
                    {"item": "Broccoli", "quantity": "3 heads", "category": "Vegetables"},
                    {"item": "Sweet potatoes", "quantity": "5 lbs", "category": "Carbohydrates"},
                    {"item": "Greek yogurt", "quantity": "32 oz", "category": "Dairy"},
                    {"item": "Oats", "quantity": "1 container", "category": "Carbohydrates"},
                    {"item": "Blueberries", "quantity": "2 cups", "category": "Fruits"}
                ]
            }
        }


class PlanGenerationService:
    """Service for handling plan generation logic"""
    
    @staticmethod
    def generate_user_plan(plan_generation_id: int) -> bool:
        """Generate user plan from questionnaire data"""
        try:
            with transaction.atomic():
                plan_generation = PlanGeneration.objects.select_for_update().get(id=plan_generation_id)
                
                if plan_generation.status != 'queued':
                    logger.warning(f"Plan generation {plan_generation_id} not in queued status")
                    return False
                
                # Update status to processing
                plan_generation.status = 'processing'
                plan_generation.started_at = timezone.now()
                plan_generation.save()
                
                # Generate plans using AI
                logger.info(f"Starting plan generation for {plan_generation.user_goal}")
                ai_response = AIService.generate_plans(plan_generation.user_goal)
                
                # Store AI response
                plan_generation.ai_response_raw = ai_response
                plan_generation.ai_prompt_sent = "Generated based on questionnaire data"  # Store actual prompt if needed
                
                # Create workout plan
                workout_data = ai_response['workout_plan']
                workout_plan = WorkoutPlan.objects.create(
                    user=plan_generation.user_goal.user,
                    user_goal=plan_generation.user_goal,
                    plan_generation=plan_generation,
                    name=workout_data['name'],
                    description=workout_data['description'],
                    difficulty_level=workout_data['difficulty_level'],
                    duration_weeks=workout_data['duration_weeks'],
                    sessions_per_week=workout_data['sessions_per_week'],
                    workout_schedule=workout_data['workout_schedule'],
                    exercises=workout_data['exercises'],
                    equipment_needed=workout_data['equipment_needed'],
                    generated_from_ai=True
                )
                
                # Create diet plan
                diet_data = ai_response['diet_plan']
                diet_plan = DietPlan.objects.create(
                    user=plan_generation.user_goal.user,
                    user_goal=plan_generation.user_goal,
                    plan_generation=plan_generation,
                    name=diet_data['name'],
                    description=diet_data['description'],
                    diet_type=diet_data['diet_type'],
                    daily_calorie_target=diet_data['daily_calorie_target'],
                    duration_weeks=diet_data['duration_weeks'],
                    protein_percentage=diet_data['protein_percentage'],
                    carb_percentage=diet_data['carb_percentage'],
                    fat_percentage=diet_data['fat_percentage'],
                    meal_plan=diet_data['meal_plan'],
                    food_restrictions=diet_data['food_restrictions'],
                    preferred_foods=diet_data['preferred_foods'],
                    shopping_list=diet_data['shopping_list'],
                    generated_from_ai=True
                )
                
                # Create plan summary
                plan_summary = UserPlanSummary.objects.create(
                    user=plan_generation.user_goal.user,
                    user_goal=plan_generation.user_goal,
                    diet_plan=diet_plan,
                    workout_plan=workout_plan
                )
                
                # Update plan generation
                plan_generation.workout_plan = workout_plan # type: ignore
                plan_generation.diet_plan = diet_plan # type: ignore
                plan_generation.status = 'completed'
                plan_generation.completed_at = timezone.now()
                if plan_generation.completed_at and plan_generation.started_at:
                    plan_generation.processing_time_seconds = (
                        plan_generation.completed_at - plan_generation.started_at
                    ).total_seconds() # type: ignore
                else:
                    plan_generation.processing_time_seconds = None
                plan_generation.save()
                
                # Update user progress
                progress = UserProgress.objects.get(user=plan_generation.user_goal.user)
                progress.mark_step_completed('plan_generation')
                
                logger.info(f"Plan generation completed for {plan_generation.user_goal}")
                return True
                
        except Exception as e:
            logger.error(f"Plan generation failed for {plan_generation_id}: {str(e)}")
            
            # Update plan generation with error
            try:
                plan_generation = PlanGeneration.objects.get(id=plan_generation_id)
                plan_generation.status = 'failed' # type: ignore
                plan_generation.error_message = str(e) # type: ignore
                plan_generation.completed_at = timezone.now() # type: ignore
                plan_generation.save() # type: ignore
            except:
                pass
            
            return False
    
    @staticmethod
    def create_dummy_plans(plan_generation: PlanGeneration):
        """Create dummy plans for testing purposes"""
        dummy_response = AIService._create_dummy_response({
            'goal': plan_generation.user_goal.goal.name,
            'user_info': {'fitness_experience': 'beginner'}
        })
        
        # Store dummy response
        plan_generation.ai_response_raw = dummy_response
        plan_generation.status = 'processing'
        plan_generation.started_at = timezone.now()
        plan_generation.save()
        
        # Create plans using dummy data
        workout_data = dummy_response['workout_plan']
        workout_plan = WorkoutPlan.objects.create(
            user=plan_generation.user_goal.user,
            user_goal=plan_generation.user_goal,
            plan_generation=plan_generation,
            name=workout_data['name'],
            description=workout_data['description'],
            difficulty_level=workout_data['difficulty_level'],
            duration_weeks=workout_data['duration_weeks'],
            sessions_per_week=workout_data['sessions_per_week'],
            workout_schedule=workout_data['workout_schedule'],
            exercises=workout_data['exercises'],
            equipment_needed=workout_data['equipment_needed'],
            generated_from_ai=True
        )
        
        diet_data = dummy_response['diet_plan']
        diet_plan = DietPlan.objects.create(
            user=plan_generation.user_goal.user,
            user_goal=plan_generation.user_goal,
            plan_generation=plan_generation,
            name=diet_data['name'],
            description=diet_data['description'],
            diet_type=diet_data['diet_type'],
            daily_calorie_target=diet_data['daily_calorie_target'],
            duration_weeks=diet_data['duration_weeks'],
            protein_percentage=diet_data['protein_percentage'],
            carb_percentage=diet_data['carb_percentage'],
            fat_percentage=diet_data['fat_percentage'],
            meal_plan=diet_data['meal_plan'],
            food_restrictions=diet_data['food_restrictions'],
            preferred_foods=diet_data['preferred_foods'],
            shopping_list=diet_data['shopping_list'],
            generated_from_ai=True
        )
        
        # Create plan summary
        UserPlanSummary.objects.create(
            user=plan_generation.user_goal.user,
            user_goal=plan_generation.user_goal,
            diet_plan=diet_plan,
            workout_plan=workout_plan
        )
        
        # Complete generation
        plan_generation.workout_plan = workout_plan # type: ignore
        plan_generation.diet_plan = diet_plan # type: ignore
        plan_generation.status = 'completed'
        plan_generation.completed_at = timezone.now()
        plan_generation.save()
        
        # Update user progress
        progress = UserProgress.objects.get(user=plan_generation.user_goal.user)
        progress.mark_step_completed('plan_generation')
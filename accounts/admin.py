from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django import forms
from django.utils.html import format_html
from django.utils import timezone
from .models import User, PhoneOTP


class UserCreationForm(forms.ModelForm):
    """A form for creating new users. Includes all the required
    fields, plus a repeated password."""
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('phone', 'first_name', 'last_name', 'email')

    def clean_password2(self):
        # Check that the two password entries match
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        # Save the provided password in hashed format
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    """A form for updating users. Includes all the fields on
    the user, but replaces the password field with admin's
    disabled password hash display field.
    """
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = ('phone', 'password', 'first_name', 'last_name', 'email', 
                 'birth_date', 'membership', 'is_active', 'is_staff', 'is_superuser')


class UserAdmin(BaseUserAdmin):
    # The forms to add and change user instances
    form = UserChangeForm
    add_form = UserCreationForm

    # The fields to be used in displaying the User model.
    list_display = ('phone', 'first_name', 'last_name', 'email', 'membership', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'membership', 'date_joined')
    
    # Fields for the user detail page
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Personal info', {'fields': ('username', 'first_name', 'last_name', 'email', 'birth_date')}),
        ('Membership', {'fields': ('membership',)}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    # add_fieldsets is not a standard ModelAdmin attribute. UserAdmin
    # overrides get_fieldsets to use this attribute when creating a user.
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'first_name', 'last_name', 'email', 'password1', 'password2'),
        }),
        ('Membership', {'fields': ('membership',)}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser'),
            'classes': ('collapse',)
        }),
    )
    
    search_fields = ('phone', 'first_name', 'last_name', 'email')
    ordering = ('phone',)
    filter_horizontal = ('groups', 'user_permissions')
    
    # Custom methods
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or "No Name"
    get_full_name.short_description = 'Full Name' # type: ignore
    
    def membership_display(self, obj):
        """Display membership with colored badges"""
        colors = {
            'B': '#CD7F32',  # Bronze
            'S': '#C0C0C0',  # Silver  
            'G': '#FFD700',  # Gold
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">● {}</span>',
            colors.get(obj.membership, '#000000'),
            obj.get_membership_display()
        )
    membership_display.short_description = 'Membership' # type: ignore
    membership_display.admin_order_field = 'membership' # type: ignore


@admin.register(PhoneOTP)
class PhoneOTPAdmin(admin.ModelAdmin):
    list_display = ('phone', 'code', 'is_used', 'is_expired_display', 'created_at', 'expires_at', 'session_id')
    list_filter = ('is_used', 'created_at', 'expires_at')
    search_fields = ('phone', 'code', 'session_id')
    readonly_fields = ('session_id', 'created_at', 'is_expired_display')
    ordering = ('-created_at',)
    
    # Custom field for better display
    def is_expired_display(self, obj):
        """Show if OTP is expired with colored status"""
        if obj.is_expired():
            return format_html('<span style="color: red;">● Expired</span>')
        else:
            time_left = obj.expires_at - timezone.now()
            minutes_left = int(time_left.total_seconds() / 60)
            return format_html(
                '<span style="color: green;">● Valid ({} min left)</span>',
                minutes_left
            )
    is_expired_display.short_description = 'Status' # type: ignore
    is_expired_display.admin_order_field = 'expires_at' # type: ignore
    
    def get_queryset(self, request):
        """Show most recent OTPs first"""
        return super().get_queryset(request).order_by('-created_at')
    
    # Custom actions
    actions = ['mark_as_used', 'delete_expired_otps']
    
    def mark_as_used(self, request, queryset):
        """Mark selected OTPs as used"""
        updated = queryset.update(is_used=True)
        self.message_user(request, f'{updated} OTP(s) marked as used.')
    mark_as_used.short_description = "Mark selected OTPs as used" # type: ignore
    
    def delete_expired_otps(self, request, queryset):
        """Delete expired OTPs"""
        expired_otps = queryset.filter(expires_at__lt=timezone.now())
        count = expired_otps.count()
        expired_otps.delete()
        self.message_user(request, f'{count} expired OTP(s) deleted.')
    delete_expired_otps.short_description = "Delete expired OTPs" # type: ignore


# Register the custom UserAdmin
admin.site.register(User, UserAdmin)

# Customize admin site headers
admin.site.site_header = "Your App Admin"
admin.site.site_title = "Your App Admin Portal"
admin.site.index_title = "Welcome to Your App Administration"


# Optional: Create a custom admin view for statistics
class AdminStatsView:
    """Custom view to show user statistics on admin dashboard"""
    
    @staticmethod
    def get_user_stats():
        from django.db.models import Count
        
        stats = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'staff_users': User.objects.filter(is_staff=True).count(),
            'membership_breakdown': User.objects.values('membership').annotate(
                count=Count('membership')
            ),
            'recent_signups': User.objects.filter(
                date_joined__gte=timezone.now() - timezone.timedelta(days=7)
            ).count(),
            'pending_otps': PhoneOTP.objects.filter(
                is_used=False,
                expires_at__gt=timezone.now()
            ).count(),
        }
        return stats

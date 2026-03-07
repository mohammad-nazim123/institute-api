from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django import forms
from .models import Institute, generate_unique_key


class InstituteAdminForm(forms.ModelForm):
    """Custom form that adds a 'Set Timer (months)' and editable admin key field."""
    timer_months = forms.IntegerField(
        required=False,
        min_value=0,
        label='Set Timer (months)',
        help_text='Set number of months from now. When the timer expires, events will auto-stop. Set to 0 or leave blank to clear the timer.'
    )
    admin_key_input = forms.CharField(
        required=False,
        max_length=32,
        label='Admin Key (32 chars)',
        help_text='Leave blank to auto-generate on save, or click "Generate Key" to fill it in.',
        widget=forms.TextInput(attrs={
            'id': 'admin_key_input_field',
            'style': 'font-family:monospace; letter-spacing:1px; width:360px;',
            'placeholder': 'Click "Generate Key" or leave blank to auto-generate',
            'maxlength': '32',
        })
    )

    class Meta:
        model = Institute
        fields = '__all__'

    class Media:
        js = ('admin/js/generate_admin_key.js',)


@admin.register(Institute)
class InstituteAdmin(admin.ModelAdmin):
    form = InstituteAdminForm
    list_display = ('id', 'name', 'show_full_key', 'status_badge', 'event_timer_end')
    search_fields = ('name',)
    list_filter = ('event_status',)
    readonly_fields = ('show_full_key',)
    actions = ['activate_events', 'pause_events', 'stop_events']

    def show_full_key(self, obj):
        """Display the full 32-character key without any truncation."""
        return format_html(
            '<code style="font-size:14px; letter-spacing:1px; word-break:break-all;">{}</code>',
            obj.admin_key
        )
    show_full_key.short_description = 'Admin Key (32 chars)'

    def status_badge(self, obj):
        """Show a colored badge for the event status."""
        colors = {
            'active': '#28a745',
            'paused': '#fd7e14',
            'stopped': '#dc3545',
        }
        color = colors.get(obj.event_status, '#6c757d')
        return format_html(
            '<span style="background:{}; color:#fff; padding:3px 10px; '
            'border-radius:12px; font-weight:bold; font-size:12px;">{}</span>',
            color,
            obj.get_event_status_display()
        )
    status_badge.short_description = 'Event Status'

    def get_fields(self, request, obj=None):
        if obj is None:
            # Creating a new institute
            return ['name', 'admin_key_input', 'event_status', 'timer_months']
        # Editing an existing institute
        return ['name', 'show_full_key', 'event_status', 'event_timer_end', 'timer_months']

    def save_model(self, request, obj, form, change):
        """Handle admin_key and timer_months before saving."""
        if not change:
            # Creating new — use the provided key or auto-generate
            provided_key = form.cleaned_data.get('admin_key_input', '').strip()
            if provided_key and len(provided_key) == 32:
                obj.admin_key = provided_key
            else:
                obj.admin_key = generate_unique_key()

        timer_months = form.cleaned_data.get('timer_months')
        if timer_months and timer_months > 0:
            obj.event_timer_end = timezone.now() + relativedelta(months=timer_months)
            if obj.event_status == 'stopped':
                obj.event_status = 'active'
        elif timer_months == 0:
            obj.event_timer_end = None

        super().save_model(request, obj, form, change)

    # ── Bulk Admin Actions ──────────────────────────────────

    @admin.action(description='✅ Activate selected institutes')
    def activate_events(self, request, queryset):
        updated = queryset.update(event_status='active')
        self.message_user(request, f'{updated} institute(s) activated.')

    @admin.action(description='⏸️ Pause selected institutes')
    def pause_events(self, request, queryset):
        updated = queryset.update(event_status='paused')
        self.message_user(request, f'{updated} institute(s) paused.')

    @admin.action(description='⛔ Stop selected institutes')
    def stop_events(self, request, queryset):
        updated = queryset.update(event_status='stopped', event_timer_end=None)
        self.message_user(request, f'{updated} institute(s) stopped.')

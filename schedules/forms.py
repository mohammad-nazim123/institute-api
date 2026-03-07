from django import forms
from .models import WeeklySchedule,ExamSchedule

class WeeklyEventForm(forms.ModelForm):
    start_time = forms.TimeField(
        input_formats=['%I:%M %p'], # Allows the user to type "10:00 AM"
        widget=forms.TimeInput(
            format='%I:%M %p',      # Displays the initial value as "10:00 AM"
            attrs={'placeholder': '10:00 AM'}
        )
    )
    end_time = forms.TimeField(
        input_formats=['%I:%M %p'], # Allows the user to type "10:00 AM"
        widget=forms.TimeInput(
            format='%I:%M %p',      # Displays the initial value as "10:00 AM"
            attrs={'placeholder': '10:00 AM'}
        )
    )

    class Meta:
        model = WeeklySchedule
        fields = ['start_time','end_time']

class ExamEventForm(ModelForm):
    start_time = forms.TimeField(
        input_formats=['%I:%M %p'],  # 10:00 AM
        widget=forms.TimeInput(format='%I:%M %p')
    )
    end_time = forms.TimeField(
        input_formats=['%I:%M %p'],  # 10:00 AM
        widget=forms.TimeInput(format='%I:%M %p')
    )
    exam_date = forms.DateField(
        input_formats=['%d, %b, %Y'],   # 15, Mar, 2026
        widget=forms.DateInput(
            format='%d, %b, %Y',
            attrs={'placeholder': '15, Mar, 2026'}
        )
    )

    class Meta:
        model = ExamSchedule
        fields = ['start_time','end_time','exam_date']
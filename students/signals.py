# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from .models import Student, StudentContactDetails, StudentEducationDetails

# @receiver(post_save, sender=Student)
# def create_student_details(sender, instance, created, **kwargs):
#     if created:
#         StudentContactDetails.objects.create(student=instance)
#         StudentEducationDetails.objects.create(student=instance)
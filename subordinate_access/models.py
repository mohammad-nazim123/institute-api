from django.db import models


class SubordinateAccess(models.Model):
    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='subordinate_accesses',
        null=True,
        blank=True,
    )
    post = models.CharField(max_length=100, default="")
    name = models.CharField(max_length=100, default="")
    access_control = models.CharField(max_length=100, default="")
    access_code = models.CharField(max_length=39, default="")
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['institute'], name='subacc_institute_idx'),
            models.Index(fields=['institute', 'name'], name='subacc_inst_name_idx'),
            models.Index(fields=['institute', 'access_code'], name='subacc_inst_code_idx'),
        ]

    def __str__(self):
        return f"{self.name} ({self.post})"


class SubordinateAccessVerificationRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    institute = models.ForeignKey(
        'iinstitutes_list.Institute',
        on_delete=models.CASCADE,
        related_name='subordinate_access_verification_requests',
    )
    subordinate_access = models.ForeignKey(
        SubordinateAccess,
        on_delete=models.CASCADE,
        related_name='verification_requests',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at', '-id']
        indexes = [
            models.Index(fields=['status', 'requested_at'], name='subacc_req_status_idx'),
            models.Index(fields=['institute', 'status'], name='subacc_req_inst_status_idx'),
        ]

    def __str__(self):
        return f"{self.subordinate_access.name} - {self.status}"

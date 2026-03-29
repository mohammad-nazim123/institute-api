from rest_framework import generics

from .models import PaymentNotification
from .permissions import InstitutePaymentNotificationPermission
from .serializers import PaymentNotificationSerializer


class PaymentNotificationListCreateView(generics.ListCreateAPIView):
    permission_classes = [InstitutePaymentNotificationPermission]
    serializer_class = PaymentNotificationSerializer

    def get_queryset(self):
        queryset = PaymentNotification.objects.select_related(
            'professor',
            'professor__experience',
        ).filter(
            institute=self.request._verified_institute
        ).order_by('-payment_month_key', 'id')

        professor_id = self.request.query_params.get('professor')
        if professor_id:
            queryset = queryset.filter(professor_id=professor_id)

        payment_month = self.request.query_params.get('payment_month')
        if payment_month:
            queryset = queryset.filter(payment_month_key=payment_month)

        return queryset

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context


class PaymentNotificationDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [InstitutePaymentNotificationPermission]
    serializer_class = PaymentNotificationSerializer

    def get_queryset(self):
        return PaymentNotification.objects.select_related(
            'professor',
            'professor__experience',
        ).filter(
            institute=self.request._verified_institute
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['institute'] = self.request._verified_institute
        return context

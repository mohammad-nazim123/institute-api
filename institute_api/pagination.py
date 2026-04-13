from django.core.paginator import EmptyPage, PageNotAnInteger
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination


class GracefulPageNumberPagination(PageNumberPagination):
    """
    Resolve empty or out-of-range pages to a safe page instead of returning 404.

    This keeps table-based UIs stable when filters return no rows or when the
    current page becomes invalid after deletes.
    """

    @staticmethod
    def _coerce_page_number(value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        page_size = self.get_page_size(request)
        if not page_size:
            return None

        paginator = self.django_paginator_class(queryset, page_size)
        page_number = request.query_params.get(self.page_query_param, 1)

        if page_number in self.last_page_strings:
            page_number = paginator.num_pages

        try:
            self.page = paginator.page(page_number)
        except PageNotAnInteger as exc:
            message = self.invalid_page_message.format(
                page_number=page_number,
                message=str(exc),
            )
            raise NotFound(message) from exc
        except EmptyPage:
            numeric_page_number = self._coerce_page_number(page_number)
            if paginator.count == 0 or (numeric_page_number is not None and numeric_page_number < 1):
                fallback_page_number = 1
            else:
                fallback_page_number = paginator.num_pages
            self.page = paginator.page(fallback_page_number)

        if paginator.num_pages > 1 and self.template is not None:
            self.display_page_controls = True

        return list(self.page)


class StandardResultsPagination(GracefulPageNumberPagination):
    """
    Default project-wide pagination.
    Clients can override page size via ?page_size=N (capped at 200).
    Response includes `count`, `next`, `previous`, and `results`.
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

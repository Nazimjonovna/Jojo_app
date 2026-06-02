from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def paginate_queryset(request, queryset, serializer_class, context=None, page_size=None):
    paginator = StandardResultsSetPagination()

    if page_size:
        paginator.page_size = page_size

    page = paginator.paginate_queryset(queryset, request)

    if page is not None:
        serializer = serializer_class(
            page,
            many=True,
            context=context or {}
        )

        return paginator.get_paginated_response(
            {
                "status": True,
                "results": serializer.data,
            }
        )

    serializer = serializer_class(
        queryset,
        many=True,
        context=context or {}
    )

    return Response(
        {
            "status": True,
            "results": serializer.data,
        }
    )
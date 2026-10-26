from django.shortcuts import render


class NotFoundPageMiddleware:
    """Use the site's 404 design, including during local development."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 404 and response.get('Content-Type', '').startswith('text/html'):
            return render(request, '404.html', status=404)
        return response

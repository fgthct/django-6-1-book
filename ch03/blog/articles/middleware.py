from django.http.multipartparser import MultiPartParser, MultiPartParserError

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


class ImageOnlyParser(MultiPartParser):
    """Immediately reject uploads that don't declare themselves as images."""

    def parse(self):
        post, files = super().parse()
        for _, file_list in files.lists():
            for file in file_list:
                if file.content_type not in ALLOWED_TYPES:
                    raise MultiPartParserError(
                        f"File type not allowed: {file.content_type}"
                    )
        return post, files


class ImageOnlyParserMiddleware:
    """Use the restrictive parser for requests to the admin area."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            request.multipart_parser_class = ImageOnlyParser
        return self.get_response(request)

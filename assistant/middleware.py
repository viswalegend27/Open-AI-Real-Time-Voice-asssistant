import time
import logging

logger = logging.getLogger(__name__)

class RequestLoggingMiddleware:
    # an middleware to log the time taken for each request
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        response = self.get_response(request)

        elapsed_time = time.time() - start_time
        logger.info(f"Request to {request.path} took {elapsed_time:.3f} seconds.")

        return response
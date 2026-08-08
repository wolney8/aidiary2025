"""Production WSGI entrypoint for hosted OpenMynd API deployments."""

from app import create_app


app = create_app()

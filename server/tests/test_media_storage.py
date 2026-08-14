from io import BytesIO

from flask import Flask

from services.media_storage import (
    R2_MEDIA_BACKEND,
    build_media_response,
    delete_image,
    media_path_exists,
    read_media_bytes,
    resolve_image_url,
    store_entry_asset,
    store_generated_image,
)


class FakeR2Client:
    def __init__(self):
        self.objects = {}
        self.deleted = []

    def put_object(self, *, Bucket, Key, Body, ContentType):
        self.objects[(Bucket, Key)] = {
            "body": Body,
            "content_type": ContentType,
        }

    def get_object(self, *, Bucket, Key):
        item = self.objects[(Bucket, Key)]
        return {"Body": BytesIO(item["body"])}

    def head_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise KeyError(Key)
        return {}

    def delete_object(self, *, Bucket, Key):
        self.deleted.append((Bucket, Key))
        self.objects.pop((Bucket, Key), None)


def _r2_app(fake_client):
    app = Flask(__name__)
    app.config.update(
        MEDIA_STORAGE_BACKEND=R2_MEDIA_BACKEND,
        MEDIA_BASE_URL="https://api.openmynd.example/media",
        MEDIA_URL_PREFIX="/media",
        R2_BUCKET_NAME="openmynd-test-media",
        R2_CLIENT=fake_client,
    )
    return app


def test_r2_media_backend_stores_reads_resolves_and_deletes_media():
    fake_client = FakeR2Client()
    app = _r2_app(fake_client)

    with app.test_request_context("/"):
        storage_key = store_generated_image(
            b"png-bytes",
            user_id=7,
            entry_kind="dream",
        )

        assert storage_key.startswith("entries/dream/7/")
        assert media_path_exists(storage_key) is True
        assert read_media_bytes(storage_key) == b"png-bytes"
        assert resolve_image_url(storage_key).startswith(
            "https://api.openmynd.example/media/entries/dream/7/"
        )

        delete_image(storage_key)

        assert media_path_exists(storage_key) is False
        assert fake_client.deleted == [("openmynd-test-media", storage_key)]


def test_r2_media_proxy_response_uses_storage_key_mimetype():
    fake_client = FakeR2Client()
    app = _r2_app(fake_client)

    with app.test_request_context("/"):
        storage_key = store_entry_asset(
            b"pdf-bytes",
            user_id=3,
            entry_kind="daily",
            filename="note.pdf",
        )

        response = build_media_response(storage_key)

        assert response is not None
        assert response.get_data() == b"pdf-bytes"
        assert response.mimetype == "application/pdf"


def test_r2_public_base_url_resolves_direct_object_url():
    fake_client = FakeR2Client()
    app = _r2_app(fake_client)
    app.config["R2_PUBLIC_BASE_URL"] = "https://media.openmynd.example"

    with app.test_request_context("/"):
        storage_key = store_generated_image(
            b"png-bytes",
            user_id=7,
            entry_kind="dream",
        )

        assert resolve_image_url(storage_key).startswith(
            "https://media.openmynd.example/entries/dream/7/"
        )

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from articles.models import Article

URL = "/admin/articles/article/add/"


def form_data(cover):
    return {"title": "Upload", "slug": "upload", "summary": "", "body": "x",
            "tags": "", "metadata": "", "cover": cover}


def png_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, "PNG")
    return buffer.getvalue()


def test_the_image_is_accepted(admin_client, db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    cover = SimpleUploadedFile("c.png", png_bytes(), content_type="image/png")
    response = admin_client.post(URL, form_data(cover))
    assert response.status_code == 302
    assert Article.objects.filter(slug="upload").exists()


def test_a_text_file_is_rejected_by_the_parser(admin_client, db):
    cover = SimpleUploadedFile("c.txt", b"hello", content_type="text/plain")
    response = admin_client.post(URL, form_data(cover))
    assert response.status_code == 400
    assert not Article.objects.filter(slug="upload").exists()


def test_a_fake_png_passes_the_parser_but_not_the_form(admin_client, db):
    cover = SimpleUploadedFile("c.png", b"this is not an image", content_type="image/png")
    response = admin_client.post(URL, form_data(cover))
    assert response.status_code == 200
    assert not Article.objects.filter(slug="upload").exists()

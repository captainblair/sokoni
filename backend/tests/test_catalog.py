from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.catalog.models import Product

pytestmark = pytest.mark.django_db

LIST_URL = reverse("product-list")


def detail_url(product):
    return reverse("product-detail", args=[product.id])


def create_product(client, name="Soda crate", **extra):
    payload = {"name": name}
    payload.update(extra)
    return client.post(LIST_URL, payload, format="json")


def test_create_product_uses_the_active_business(authenticated_client, business):
    response = create_product(authenticated_client, unit="crate", default_price="1200.00")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["business"] == str(business.id)
    assert response.data["unit"] == "crate"
    assert Decimal(response.data["default_price"]) == Decimal("1200.00")


def test_price_is_optional(authenticated_client, business):
    response = create_product(authenticated_client, name="Tomatoes", unit="kg")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["default_price"] is None


def test_negative_price_is_rejected(authenticated_client, business):
    response = create_product(authenticated_client, default_price="-5.00")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "default_price" in response.data


def test_duplicate_names_are_rejected_case_insensitively(authenticated_client, business):
    create_product(authenticated_client, name="Soda crate")

    response = create_product(authenticated_client, name="SODA CRATE")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Product.objects.filter(business=business).count() == 1


def test_the_same_product_may_exist_in_another_business(
    authenticated_client, business, business_factory, user
):
    second = business_factory(user, name="Second Shop")
    create_product(authenticated_client, name="Soda crate")

    response = create_product(authenticated_client, name="Soda crate", business=str(second.id))

    assert response.status_code == status.HTTP_201_CREATED


def test_search_matches_name(authenticated_client, business):
    create_product(authenticated_client, name="Soda crate")
    create_product(authenticated_client, name="Tomatoes")

    response = authenticated_client.get(LIST_URL, {"search": "tomat"})

    assert [item["name"] for item in response.data] == ["Tomatoes"]


def test_delete_archives_the_product(authenticated_client, business):
    created = create_product(authenticated_client)
    product = Product.objects.get(id=created.data["id"])

    response = authenticated_client.delete(detail_url(product))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    product.refresh_from_db()
    assert product.is_active is False


def test_cannot_reach_products_of_another_business(authenticated_client, other_business, business):
    foreign = Product.objects.create(business=other_business, name="Rival Stock")

    assert authenticated_client.get(detail_url(foreign)).status_code == status.HTTP_404_NOT_FOUND


def test_anonymous_access_is_rejected(api_client, business):
    assert api_client.get(LIST_URL).status_code == status.HTTP_401_UNAUTHORIZED

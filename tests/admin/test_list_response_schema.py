"""Tests for the generic ListResponse Pydantic schema."""

from pydantic import BaseModel


class TestListResponseSchema:
    def test_list_response_with_dicts(self):
        """ListResponse holds arbitrary dict items and all pagination fields."""
        from spellbook.admin.routes.schemas import ListResponse

        response = ListResponse(
            items=[{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}],
            total=42,
            page=2,
            per_page=25,
            pages=2,
        )
        d = response.model_dump()
        assert d == {
            "items": [{"id": 1, "name": "alice"}, {"id": 2, "name": "bob"}],
            "total": 42,
            "page": 2,
            "per_page": 25,
            "pages": 2,
        }

    def test_list_response_empty(self):
        """ListResponse with no items serializes correctly."""
        from spellbook.admin.routes.schemas import ListResponse

        response = ListResponse(
            items=[], total=0, page=1, per_page=50, pages=1,
        )
        d = response.model_dump()
        assert d == {"items": [], "total": 0, "page": 1, "per_page": 50, "pages": 1}

    def test_list_response_typed_with_model(self):
        """ListResponse[T] works with a concrete Pydantic model type."""
        from spellbook.admin.routes.schemas import ListResponse

        class Widget(BaseModel):
            name: str
            weight: float

        response = ListResponse[Widget](
            items=[Widget(name="gear", weight=1.5)],
            total=1,
            page=1,
            per_page=10,
            pages=1,
        )
        d = response.model_dump()
        assert d == {
            "items": [{"name": "gear", "weight": 1.5}],
            "total": 1,
            "page": 1,
            "per_page": 10,
            "pages": 1,
        }

    def test_list_response_typed_validates_items(self):
        """ListResponse[T] with a concrete type rejects invalid items."""
        from spellbook.admin.routes.schemas import ListResponse
        import pytest

        class Gadget(BaseModel):
            serial: int

        with pytest.raises(Exception):
            ListResponse[Gadget](
                items=[{"not_serial": "bad"}],
                total=1,
                page=1,
                per_page=10,
                pages=1,
            )

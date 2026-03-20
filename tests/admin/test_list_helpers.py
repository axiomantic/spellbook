"""Tests for admin list endpoint helper functions."""

import math

import pytest


class TestValidateSortOrder:
    def test_asc_variants(self):
        from spellbook.admin.routes.list_helpers import validate_sort_order

        assert validate_sort_order("asc") == "asc"
        assert validate_sort_order("ASC") == "asc"
        assert validate_sort_order("Asc") == "asc"

    def test_desc_variants(self):
        from spellbook.admin.routes.list_helpers import validate_sort_order

        assert validate_sort_order("desc") == "desc"
        assert validate_sort_order("DESC") == "desc"
        assert validate_sort_order("Desc") == "desc"

    def test_invalid_defaults_to_desc(self):
        from spellbook.admin.routes.list_helpers import validate_sort_order

        assert validate_sort_order("invalid") == "desc"
        assert validate_sort_order("") == "desc"
        assert validate_sort_order("ascending") == "desc"
        assert validate_sort_order("up") == "desc"


class TestComputePagination:
    def test_normal_pagination(self):
        from spellbook.admin.routes.list_helpers import compute_pagination

        result = compute_pagination(total=142, page=2, per_page=50)
        assert result == {"total": 142, "page": 2, "per_page": 50, "pages": 3}

    def test_empty_result_set(self):
        from spellbook.admin.routes.list_helpers import compute_pagination

        result = compute_pagination(total=0, page=1, per_page=50)
        assert result == {"total": 0, "page": 1, "per_page": 50, "pages": 1}

    def test_clamps_page_to_max(self):
        from spellbook.admin.routes.list_helpers import compute_pagination

        result = compute_pagination(total=10, page=999, per_page=50)
        assert result == {"total": 10, "page": 1, "per_page": 50, "pages": 1}

    def test_exact_page_boundary(self):
        from spellbook.admin.routes.list_helpers import compute_pagination

        result = compute_pagination(total=100, page=2, per_page=50)
        assert result == {"total": 100, "page": 2, "per_page": 50, "pages": 2}

    def test_single_item(self):
        from spellbook.admin.routes.list_helpers import compute_pagination

        result = compute_pagination(total=1, page=1, per_page=25)
        assert result == {"total": 1, "page": 1, "per_page": 25, "pages": 1}

    def test_page_just_over_boundary(self):
        from spellbook.admin.routes.list_helpers import compute_pagination

        # 101 items at 50 per page = 3 pages (ceil(101/50) = 3)
        result = compute_pagination(total=101, page=3, per_page=50)
        assert result == {"total": 101, "page": 3, "per_page": 50, "pages": 3}


class TestBuildListResponse:
    def test_builds_response_envelope(self):
        from spellbook.admin.routes.list_helpers import build_list_response

        items = [{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}]
        result = build_list_response(items=items, total=42, page=1, per_page=25)
        assert result == {
            "items": [{"id": 1, "name": "alpha"}, {"id": 2, "name": "beta"}],
            "total": 42,
            "page": 1,
            "per_page": 25,
            "pages": 2,
        }

    def test_empty_items(self):
        from spellbook.admin.routes.list_helpers import build_list_response

        result = build_list_response(items=[], total=0, page=1, per_page=25)
        assert result == {
            "items": [],
            "total": 0,
            "page": 1,
            "per_page": 25,
            "pages": 1,
        }

    def test_single_page(self):
        from spellbook.admin.routes.list_helpers import build_list_response

        items = [{"id": 1}]
        result = build_list_response(items=items, total=1, page=1, per_page=50)
        assert result == {
            "items": [{"id": 1}],
            "total": 1,
            "page": 1,
            "per_page": 50,
            "pages": 1,
        }

    def test_page_clamping_propagates(self):
        from spellbook.admin.routes.list_helpers import build_list_response

        items = [{"id": 1}]
        result = build_list_response(items=items, total=10, page=999, per_page=50)
        assert result == {
            "items": [{"id": 1}],
            "total": 10,
            "page": 1,
            "per_page": 50,
            "pages": 1,
        }

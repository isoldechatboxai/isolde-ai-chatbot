import logging

from flask import Flask

from app.services.search_router import SearchRouter


def test_search_router_does_not_log_query_content(caplog):
    app = Flask(__name__)
    query = "private document content that must not be logged"

    with app.app_context(), caplog.at_level(logging.INFO):
        result = SearchRouter().route_search(
            query,
            {"documents": [{"text": "private document content"}]},
        )

    assert result["total_matches"] == 1
    assert query not in caplog.text
    assert "query_length=" in caplog.text

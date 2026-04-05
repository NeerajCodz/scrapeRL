"""Tests for site template API endpoints."""

from fastapi.testclient import TestClient


class TestSitesAPI:
    """Validate /api/sites template routes."""

    def test_list_sites_returns_minimum_templates(self, client: TestClient) -> None:
        """List endpoint should expose a rich inbuilt catalog."""

        response = client.get("/api/sites")
        assert response.status_code == 200

        data = response.json()
        assert "sites" in data
        assert "count" in data
        assert data["count"] >= 30
        assert len(data["sites"]) >= 30

        site_ids = {site["site_id"] for site in data["sites"]}
        assert "reddit" in site_ids
        assert "github" in site_ids
        assert "youtube" in site_ids

    def test_get_specific_site_template(self, client: TestClient) -> None:
        """Fetch one known site template."""

        response = client.get("/api/sites/reddit")
        assert response.status_code == 200
        data = response.json()
        assert data["site_id"] == "reddit"
        assert "reddit.com" in data["domains"]
        assert "navigation_steps" in data
        assert len(data["navigation_steps"]) > 0

    def test_get_unknown_site_template_404(self, client: TestClient) -> None:
        """Unknown site IDs should return 404."""

        response = client.get("/api/sites/not-a-real-site")
        assert response.status_code == 404

    def test_match_site_by_asset_domain(self, client: TestClient) -> None:
        """Domain matching should pick correct template."""

        response = client.post(
            "/api/sites/match",
            json={
                "instructions": "get trending communities",
                "assets": ["https://reddit.com"],
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["matched"] is True
        assert payload["site"]["site_id"] == "reddit"

    def test_match_site_by_instruction_alias(self, client: TestClient) -> None:
        """Alias matching should work even when URL is missing."""

        response = client.post(
            "/api/sites/match",
            json={
                "instructions": "scrape latest youtube videos",
                "assets": [],
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["matched"] is True
        assert payload["site"]["site_id"] == "youtube"

    def test_match_site_returns_false_for_unknown(self, client: TestClient) -> None:
        """Matcher should return matched=false when no template fits."""

        response = client.post(
            "/api/sites/match",
            json={
                "instructions": "scrape intranet dashboard",
                "assets": ["https://internal.local.example"],
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["matched"] is False
        assert payload["site"] is None

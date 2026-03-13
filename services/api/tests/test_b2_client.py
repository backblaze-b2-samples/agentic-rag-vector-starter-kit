"""Tests for B2 client configuration and pagination."""

from app.config.settings import Settings


class TestB2Region:
    """Verify region is correctly derived from the S3 endpoint."""

    def test_default_endpoint_region(self):
        s = Settings(b2_s3_endpoint="https://s3.us-west-004.backblazeb2.com")
        assert s.b2_region == "us-west-004"

    def test_eu_endpoint_region(self):
        s = Settings(b2_s3_endpoint="https://s3.eu-central-003.backblazeb2.com")
        assert s.b2_region == "eu-central-003"

    def test_non_standard_endpoint_falls_back(self):
        s = Settings(b2_s3_endpoint="https://custom-endpoint.example.com")
        assert s.b2_region == "us-west-004"


class TestListFilesPagination:
    """Verify list_files paginates through all objects."""

    def test_pagination_collects_all_pages(self, monkeypatch):
        """list_files follows ContinuationToken across multiple pages."""
        from unittest.mock import MagicMock

        from app.repo import b2_client

        page1 = {
            "Contents": [
                {"Key": "uploads/a.txt", "Size": 10, "LastModified": "2026-01-01T00:00:00Z"},
            ],
            "IsTruncated": True,
            "NextContinuationToken": "token2",
        }
        page2 = {
            "Contents": [
                {"Key": "uploads/b.txt", "Size": 20, "LastModified": "2026-01-02T00:00:00Z"},
            ],
            "IsTruncated": False,
        }

        mock_client = MagicMock()
        mock_client.list_objects_v2.side_effect = [page1, page2]
        monkeypatch.setattr(b2_client, "get_s3_client", lambda: mock_client)

        files = b2_client.list_files(prefix="uploads/")
        assert len(files) == 2
        assert mock_client.list_objects_v2.call_count == 2
        # Second call should include the continuation token
        second_call_kwargs = mock_client.list_objects_v2.call_args_list[1][1]
        assert second_call_kwargs["ContinuationToken"] == "token2"

    def test_max_keys_limits_results(self, monkeypatch):
        """max_keys > 0 slices results after full pagination."""
        from unittest.mock import MagicMock

        from app.repo import b2_client

        page = {
            "Contents": [
                {"Key": f"uploads/{i}.txt", "Size": 10, "LastModified": f"2026-01-{i+1:02d}T00:00:00Z"}
                for i in range(5)
            ],
            "IsTruncated": False,
        }

        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = page
        monkeypatch.setattr(b2_client, "get_s3_client", lambda: mock_client)

        files = b2_client.list_files(prefix="uploads/", max_keys=2)
        assert len(files) == 2

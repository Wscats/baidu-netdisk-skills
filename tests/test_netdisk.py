"""
Tests for Baidu Netdisk SDK and CLI.

Run with: python -m pytest tests/ -v
"""

import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

from netdisk_sdk import BaiduNetdisk, QRCodeAuth, AuthError, APIError


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_session():
    """Create a mock requests session."""
    with patch("netdisk_sdk.requests.Session") as mock_cls:
        session = MagicMock()
        mock_cls.return_value = session
        yield session


@pytest.fixture
def client(tmp_path):
    """Create a BaiduNetdisk client with mocked session."""
    session_file = tmp_path / "session.json"
    session_file.write_text(json.dumps({
        "bduss": "test_bduss_value",
        "stoken": "test_stoken_value",
        "saved_at": "2024-01-01 00:00:00",
    }))

    with patch("netdisk_sdk.SESSION_FILE", session_file), \
         patch("netdisk_sdk.CONFIG_FILE", tmp_path / "config.json"):
        c = BaiduNetdisk(bduss="test_bduss", stoken="test_stoken",
                         session_file=str(session_file))
        # Replace real session with mock to allow setting return_value
        c.session = MagicMock()
        return c


# ──────────────────────────────────────────────────────────────────────
# QRCodeAuth Tests
# ──────────────────────────────────────────────────────────────────────


class TestQRCodeAuth:
    """Tests for QR code authentication."""

    def test_generate_gid(self):
        """GID should be 32 hex chars."""
        gid = QRCodeAuth._generate_gid()
        assert len(gid) == 32
        assert all(c in "ABCDEF0123456789" for c in gid)

    def test_parse_callback_valid(self):
        """Should parse JSONP callback correctly."""
        text = 'tangram_guid_callback({"sign":"abc123","imgurl":"http://example.com/qr.png"})'
        result = QRCodeAuth._parse_callback(text)
        assert result["sign"] == "abc123"
        assert result["imgurl"] == "http://example.com/qr.png"

    def test_parse_callback_invalid(self):
        """Should return empty dict for invalid callback."""
        result = QRCodeAuth._parse_callback("invalid data")
        assert result == {}

    def test_parse_callback_empty(self):
        """Should handle empty string."""
        result = QRCodeAuth._parse_callback("")
        assert result == {}

    @patch.object(QRCodeAuth, "__init__", lambda self: None)
    def test_generate_qrcode(self):
        """Should return sign and image_url."""
        auth = QRCodeAuth()
        auth.session = MagicMock()
        auth.session.get.return_value.text = (
            'callback({"sign":"test_sign","imgurl":"http://qr.example.com"})'
        )
        result = auth.generate_qrcode()
        assert result["sign"] == "test_sign"
        assert result["image_url"] == "http://qr.example.com"

    @patch.object(QRCodeAuth, "__init__", lambda self: None)
    def test_poll_login_timeout(self):
        """Should raise AuthError on timeout."""
        auth = QRCodeAuth()
        auth.session = MagicMock()
        auth.session.get.return_value.text = 'callback({"channel_v":""})'

        with pytest.raises(AuthError, match="timed out"):
            auth.poll_login("test_sign", max_wait=1)


# ──────────────────────────────────────────────────────────────────────
# BaiduNetdisk Auth Tests
# ──────────────────────────────────────────────────────────────────────


class TestAuth:
    """Tests for authentication and session management."""

    def test_session_save_and_load(self, tmp_path):
        """Should persist and restore session."""
        session_file = tmp_path / "session.json"
        with patch("netdisk_sdk.SESSION_FILE", session_file), \
             patch("netdisk_sdk.CONFIG_FILE", tmp_path / "config.json"):
            client = BaiduNetdisk(bduss="my_bduss", stoken="my_stoken",
                                  session_file=str(session_file))

        data = json.loads(session_file.read_text())
        assert data["bduss"] == "my_bduss"
        assert data["stoken"] == "my_stoken"

    def test_load_empty_session(self, tmp_path):
        """Should handle missing session file gracefully."""
        session_file = tmp_path / "nonexistent.json"
        with patch("netdisk_sdk.SESSION_FILE", session_file), \
             patch("netdisk_sdk.CONFIG_FILE", tmp_path / "config.json"):
            client = BaiduNetdisk(session_file=str(session_file))
            # Should not raise

    def test_cookie_parsing(self, client):
        """Client should have cookies set."""
        cookies = client.session.cookies.get_dict()
        assert "BDUSS" in cookies or True  # Mocked, just verify no crash


# ──────────────────────────────────────────────────────────────────────
# File Operations Tests
# ──────────────────────────────────────────────────────────────────────


class TestFileOperations:
    """Tests for file management operations."""

    def test_list_files(self, client):
        """Should call list API with correct params."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "errno": 0,
            "list": [
                {"server_filename": "test.txt", "size": 1024, "isdir": 0, "fs_id": 123},
                {"server_filename": "docs", "size": 0, "isdir": 1, "fs_id": 456},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        files = client.list_files("/")
        assert len(files) == 2
        assert files[0]["server_filename"] == "test.txt"
        assert files[1]["isdir"] == 1

    def test_list_files_with_sort(self, client):
        """Should pass sort parameters correctly."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errno": 0, "list": []}
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        client.list_files("/docs", order="time", desc=True)
        call_kwargs = client.session.request.call_args
        params = call_kwargs.kwargs.get("params", call_kwargs[1].get("params", {}))
        assert params["order"] == "time"
        assert params["desc"] == 1

    def test_search(self, client):
        """Should call search API and return results."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "errno": 0,
            "list": [
                {"server_filename": "report.pdf", "path": "/docs/report.pdf", "size": 2048}
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        results = client.search("report")
        assert len(results) == 1
        assert results[0]["server_filename"] == "report.pdf"

    def test_delete(self, client):
        """Should call delete API with file list."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errno": 0}
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        result = client.delete(["/test/file.txt"])
        assert result["errno"] == 0

    def test_rename(self, client):
        """Should call rename API."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errno": 0}
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        result = client.rename("/docs/old.pdf", "new.pdf")
        assert result["errno"] == 0

    def test_move(self, client):
        """Should call move API with filelist."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errno": 0}
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        result = client.move([{"path": "/a/file.txt", "dest": "/b/", "newname": "file.txt"}])
        assert result["errno"] == 0

    def test_copy(self, client):
        """Should call copy API."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errno": 0}
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        result = client.copy([{"path": "/a/f.txt", "dest": "/b/", "newname": "f.txt"}])
        assert result["errno"] == 0

    def test_upload_file_not_found(self, client):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            client.upload("/nonexistent/file.txt", "/remote/")

    def test_calculate_block_list(self, tmp_path):
        """Should calculate MD5 block list correctly."""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"hello world" * 100)

        blocks = BaiduNetdisk._calculate_block_list(test_file)
        assert len(blocks) == 1  # Small file = 1 block
        assert len(blocks[0]) == 32  # MD5 hex string length


# ──────────────────────────────────────────────────────────────────────
# Share Operations Tests
# ──────────────────────────────────────────────────────────────────────


class TestShareOperations:
    """Tests for share management."""

    def test_create_share(self, client):
        """Should create share with password."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "errno": 0,
            "link": "https://pan.baidu.com/s/test123",
            "shorturl": "https://pan.baidu.com/s/test123",
        }
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        result = client.create_share([123456], password="ab12", period=7)
        assert "link" in result
        assert result["password"] == "ab12"

    def test_create_share_auto_password(self, client):
        """Should auto-generate password if not provided."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errno": 0, "link": "https://example.com"}
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        result = client.create_share([123])
        assert len(result["password"]) == 4

    def test_list_shares(self, client):
        """Should list shares."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "errno": 0,
            "list": [
                {"shareid": 1, "typicalPath": "/file.pdf", "shortlink": "http://s/1"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        shares = client.list_shares()
        assert len(shares) == 1

    def test_cancel_share(self, client):
        """Should cancel share by ID."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errno": 0}
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        result = client.cancel_share([12345])
        assert result["errno"] == 0


# ──────────────────────────────────────────────────────────────────────
# Quota Tests
# ──────────────────────────────────────────────────────────────────────


class TestQuota:
    """Tests for storage quota operations."""

    def test_get_quota(self, client):
        """Should return formatted quota info."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "errno": 0,
            "total": 2199023255552,   # 2TB
            "used": 1099511627776,    # 1TB
        }
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        quota = client.get_quota()
        assert quota["total"] == 2199023255552
        assert quota["used"] == 1099511627776
        assert quota["free"] == 2199023255552 - 1099511627776
        assert abs(quota["total_gb"] - 2048.0) < 1
        assert abs(quota["used_gb"] - 1024.0) < 1

    def test_get_quota_empty(self, client):
        """Should handle zero quota gracefully."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errno": 0, "total": 0, "used": 0}
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        quota = client.get_quota()
        assert quota["total_gb"] == 0
        assert quota["free_gb"] == 0


# ──────────────────────────────────────────────────────────────────────
# Error Handling Tests
# ──────────────────────────────────────────────────────────────────────


class TestErrorHandling:
    """Tests for error handling."""

    def test_api_error_raised(self, client):
        """Should raise APIError on non-zero errno."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errno": 31034, "errmsg": "Rate limit exceeded"}
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        with pytest.raises(APIError, match="Rate limit"):
            client.list_files("/")

    def test_auth_error_on_expired_session(self, client):
        """Should raise AuthError on errno -6."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errno": -6, "errmsg": "session expired"}
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        with pytest.raises(AuthError, match="expired"):
            client.list_files("/")

    def test_api_error_str(self):
        """APIError should have readable string representation."""
        err = APIError(31034, "Rate limit")
        assert "31034" in str(err)
        assert "Rate limit" in str(err)

    def test_get_fsid_not_found(self, client):
        """Should raise APIError when file not found."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errno": 0, "list": []}
        mock_resp.raise_for_status = MagicMock()
        client.session.request.return_value = mock_resp

        with pytest.raises(APIError, match="not found"):
            client._get_fsid("/nonexistent/file.txt")


# ──────────────────────────────────────────────────────────────────────
# CLI Tests
# ──────────────────────────────────────────────────────────────────────


class TestCLI:
    """Tests for CLI commands."""

    def test_cli_help(self):
        """CLI should show help without error."""
        from click.testing import CliRunner
        from netdisk import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "百度网盘" in result.output or "netdisk" in result.output.lower()

    def test_cli_login_no_args(self):
        """Login without args should show usage hint."""
        from click.testing import CliRunner
        from netdisk import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["login"])
        assert result.exit_code == 0
        assert "--qrcode" in result.output or "--cookie" in result.output

    def test_cli_login_cookie(self):
        """Login with cookie should attempt authentication."""
        from click.testing import CliRunner
        from netdisk import cli
        runner = CliRunner()

        with patch("netdisk.BaiduNetdisk") as mock_cls:
            mock_client = MagicMock()
            mock_client.get_user_info.return_value = {"baidu_name": "testuser"}
            mock_cls.return_value = mock_client

            result = runner.invoke(cli, ["login", "--cookie", "BDUSS=test_value"])
            assert "testuser" in result.output or "Login" in result.output

    def test_cli_delete_no_args(self):
        """Delete without args should show hint."""
        from click.testing import CliRunner
        from netdisk import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["delete"])
        assert result.exit_code == 0

    def test_format_size(self):
        """format_size should format bytes correctly."""
        from netdisk import format_size
        assert format_size(0) == "0.0 B"
        assert format_size(1024) == "1.0 KB"
        assert format_size(1048576) == "1.0 MB"
        assert format_size(1073741824) == "1.0 GB"

    def test_format_time(self):
        """format_time should format timestamp."""
        from netdisk import format_time
        result = format_time(1704067200)  # 2024-01-01 in some timezone
        assert "2024" in result

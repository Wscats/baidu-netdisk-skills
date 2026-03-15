"""
Baidu Netdisk SDK - Core module for interacting with Baidu Netdisk API.
Supports QR code login and cookie-based authentication.
"""

import json
import os
import time
import hashlib
import requests
from pathlib import Path
from typing import Optional, List, Dict, Any


# Baidu API endpoints
BAIDU_PASSPORT_URL = "https://passport.baidu.com"
BAIDU_PAN_URL = "https://pan.baidu.com"
BAIDU_PCS_URL = "https://pcs.baidu.com"

# Default config path
CONFIG_DIR = Path.home() / ".netdisk"
SESSION_FILE = CONFIG_DIR / "session.json"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Default configuration
DEFAULT_CONFIG = {
    "download_dir": str(Path.home() / "Downloads" / "netdisk"),
    "chunk_size": 4 * 1024 * 1024,  # 4MB
    "max_retries": 3,
    "timeout": 30,
    "auto_rename": True,
}


class AuthError(Exception):
    """Raised when authentication fails."""
    pass


class APIError(Exception):
    """Raised when API returns an error."""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"API Error [{code}]: {message}")


class QRCodeAuth:
    """Handle QR code based authentication for Baidu Netdisk."""

    QRCODE_GENERATE_URL = f"{BAIDU_PASSPORT_URL}/v2/api/getqrcode"
    QRCODE_POLL_URL = f"{BAIDU_PASSPORT_URL}/v2/api/unicast"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })

    def generate_qrcode(self) -> Dict[str, str]:
        """Generate a QR code for login.

        Returns:
            dict with 'sign', 'image_url' keys.
        """
        params = {
            "lp": "pc",
            "qrloginfrom": "pc",
            "gid": self._generate_gid(),
            "callback": "tangram_guid_callback",
            "apiver": "v3",
            "tt": int(time.time() * 1000),
            "tpl": "netdisk",
        }
        resp = self.session.get(self.QRCODE_GENERATE_URL, params=params, timeout=10)
        data = self._parse_callback(resp.text)
        return {
            "sign": data.get("sign", ""),
            "image_url": data.get("imgurl", ""),
        }

    def poll_login(self, sign: str, max_wait: int = 120) -> Dict[str, str]:
        """Poll for QR code scan result.

        Args:
            sign: QR code sign from generate_qrcode.
            max_wait: Maximum wait time in seconds.

        Returns:
            dict with 'bduss' and 'stoken' on success.

        Raises:
            AuthError: If login times out or fails.
        """
        start_time = time.time()
        while time.time() - start_time < max_wait:
            params = {
                "channel_id": sign,
                "tpl": "netdisk",
                "apiver": "v3",
                "tt": int(time.time() * 1000),
                "callback": "tangram_guid_callback",
            }
            resp = self.session.get(self.QRCODE_POLL_URL, params=params, timeout=10)
            data = self._parse_callback(resp.text)

            channel_v = data.get("channel_v", "")
            if channel_v:
                v_data = json.loads(channel_v)
                status = v_data.get("status", -1)
                if status == 0:
                    # Successfully scanned and confirmed
                    return self._extract_credentials(v_data)

            time.sleep(3)

        raise AuthError("QR code login timed out. Please try again.")

    def _extract_credentials(self, data: Dict) -> Dict[str, str]:
        """Extract BDUSS and STOKEN from login response."""
        v3_url = data.get("v", "")
        if not v3_url:
            raise AuthError("Failed to get login redirect URL.")

        resp = self.session.get(v3_url, allow_redirects=True, timeout=10)
        cookies = self.session.cookies.get_dict()

        bduss = cookies.get("BDUSS", "")
        stoken = cookies.get("STOKEN", "")

        if not bduss:
            raise AuthError("Failed to extract BDUSS from cookies.")

        return {"bduss": bduss, "stoken": stoken}

    @staticmethod
    def _generate_gid() -> str:
        """Generate a random GID."""
        import random
        chars = "ABCDEF0123456789"
        return "".join(random.choice(chars) for _ in range(32))

    @staticmethod
    def _parse_callback(text: str) -> Dict:
        """Parse JSONP callback response."""
        try:
            start = text.index("(") + 1
            end = text.rindex(")")
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            return {}


class BaiduNetdisk:
    """Main client for Baidu Netdisk operations."""

    def __init__(
        self,
        bduss: Optional[str] = None,
        stoken: Optional[str] = None,
        session_file: Optional[str] = None,
    ):
        """Initialize BaiduNetdisk client.

        Args:
            bduss: BDUSS cookie value.
            stoken: STOKEN cookie value.
            session_file: Path to session file for persistence.
        """
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })

        self._session_file = Path(session_file) if session_file else SESSION_FILE
        self._config = self._load_config()

        if bduss:
            self._set_credentials(bduss, stoken or "")
        else:
            self._load_session()

    # ─── Authentication ──────────────────────────────────────────────

    def _set_credentials(self, bduss: str, stoken: str):
        """Set authentication cookies."""
        self.session.cookies.set("BDUSS", bduss, domain=".baidu.com")
        if stoken:
            self.session.cookies.set("STOKEN", stoken, domain=".baidu.com")
        self._save_session(bduss, stoken)

    def _save_session(self, bduss: str, stoken: str):
        """Persist session to disk."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "bduss": bduss,
            "stoken": stoken,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._session_file.write_text(json.dumps(data, indent=2))

    def _load_session(self):
        """Load session from disk."""
        if not self._session_file.exists():
            return
        try:
            data = json.loads(self._session_file.read_text())
            bduss = data.get("bduss", "")
            stoken = data.get("stoken", "")
            if bduss:
                self.session.cookies.set("BDUSS", bduss, domain=".baidu.com")
            if stoken:
                self.session.cookies.set("STOKEN", stoken, domain=".baidu.com")
        except (json.JSONDecodeError, KeyError):
            pass

    def _load_config(self) -> Dict:
        """Load configuration from disk."""
        if CONFIG_FILE.exists():
            try:
                return {**DEFAULT_CONFIG, **json.loads(CONFIG_FILE.read_text())}
            except (json.JSONDecodeError, KeyError):
                pass
        return DEFAULT_CONFIG.copy()

    def is_logged_in(self) -> bool:
        """Check if current session is valid."""
        try:
            info = self.get_user_info()
            return info.get("baidu_name", "") != ""
        except Exception:
            return False

    def get_user_info(self) -> Dict[str, Any]:
        """Get current user information.

        Returns:
            dict with user info including 'baidu_name', 'netdisk_name', 'vip_type', etc.
        """
        url = f"{BAIDU_PAN_URL}/rest/2.0/xpan/nas"
        params = {"method": "uinfo"}
        resp = self._request("GET", url, params=params)
        return resp

    # ─── File Operations ─────────────────────────────────────────────

    def list_files(
        self,
        dir_path: str = "/",
        order: str = "name",
        desc: bool = False,
        start: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List files in a directory.

        Args:
            dir_path: Directory path on netdisk.
            order: Sort field ('name', 'time', 'size').
            desc: Sort descending if True.
            start: Start index for pagination.
            limit: Max number of files to return.

        Returns:
            List of file info dicts.
        """
        url = f"{BAIDU_PAN_URL}/rest/2.0/xpan/file"
        params = {
            "method": "list",
            "dir": dir_path,
            "order": order,
            "desc": 1 if desc else 0,
            "start": start,
            "limit": limit,
            "web": "web",
        }
        resp = self._request("GET", url, params=params)
        return resp.get("list", [])

    def search(
        self,
        keyword: str,
        dir_path: str = "/",
        recursion: bool = True,
        page: int = 1,
        num: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search files by keyword.

        Args:
            keyword: Search keyword.
            dir_path: Directory to search in.
            recursion: Search subdirectories.
            page: Page number.
            num: Results per page.

        Returns:
            List of matching file info dicts.
        """
        url = f"{BAIDU_PAN_URL}/rest/2.0/xpan/file"
        params = {
            "method": "search",
            "key": keyword,
            "dir": dir_path,
            "recursion": 1 if recursion else 0,
            "page": page,
            "num": num,
            "web": "web",
        }
        resp = self._request("GET", url, params=params)
        return resp.get("list", [])

    def upload(
        self,
        local_path: str,
        remote_dir: str,
        rename_policy: int = 1,
    ) -> Dict[str, Any]:
        """Upload a file to netdisk.

        Args:
            local_path: Local file path.
            remote_dir: Remote directory path.
            rename_policy: 0=no rename, 1=auto rename, 2=overwrite.

        Returns:
            Upload result dict.
        """
        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(f"Local file not found: {local_path}")

        file_size = local_path.stat().st_size
        file_name = local_path.name
        remote_path = f"{remote_dir.rstrip('/')}/{file_name}"

        # Step 1: Pre-create
        block_list = self._calculate_block_list(local_path)
        precreate_data = {
            "path": remote_path,
            "size": file_size,
            "isdir": 0,
            "autoinit": 1,
            "rtype": rename_policy,
            "block_list": json.dumps(block_list),
        }
        url = f"{BAIDU_PAN_URL}/rest/2.0/xpan/file"
        precreate_resp = self._request(
            "POST", url, params={"method": "precreate"}, data=precreate_data
        )
        upload_id = precreate_resp.get("uploadid", "")

        # Step 2: Upload chunks
        chunk_size = self._config["chunk_size"]
        with open(local_path, "rb") as f:
            part_seq = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                upload_url = f"{BAIDU_PCS_URL}/rest/2.0/pcs/superfile2"
                params = {
                    "method": "upload",
                    "type": "tmpfile",
                    "path": remote_path,
                    "uploadid": upload_id,
                    "partseq": part_seq,
                }
                self._request(
                    "POST",
                    upload_url,
                    params=params,
                    files={"file": chunk},
                )
                part_seq += 1

        # Step 3: Create file (merge)
        create_data = {
            "path": remote_path,
            "size": file_size,
            "isdir": 0,
            "uploadid": upload_id,
            "rtype": rename_policy,
            "block_list": json.dumps(block_list),
        }
        result = self._request(
            "POST", url, params={"method": "create"}, data=create_data
        )
        return result

    def download(
        self,
        remote_path: str,
        local_dir: Optional[str] = None,
    ) -> str:
        """Download a file from netdisk.

        Args:
            remote_path: Remote file path.
            local_dir: Local directory to save to.

        Returns:
            Local file path of downloaded file.
        """
        if local_dir is None:
            local_dir = self._config["download_dir"]
        os.makedirs(local_dir, exist_ok=True)

        # Get file meta to find dlink
        url = f"{BAIDU_PAN_URL}/rest/2.0/xpan/multimedia"
        params = {"method": "filemetas", "fsids": json.dumps([self._get_fsid(remote_path)]), "dlink": 1}
        resp = self._request("GET", url, params=params)

        file_list = resp.get("list", [])
        if not file_list:
            raise APIError(-1, f"File not found: {remote_path}")

        dlink = file_list[0].get("dlink", "")
        file_name = file_list[0].get("server_filename", "downloaded_file")
        local_path = os.path.join(local_dir, file_name)

        # Download with streaming
        resp = self.session.get(
            dlink,
            params={"access_token": ""},
            stream=True,
            timeout=self._config["timeout"],
        )
        resp.raise_for_status()

        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=self._config["chunk_size"]):
                if chunk:
                    f.write(chunk)

        return local_path

    def delete(self, file_paths: List[str]) -> Dict[str, Any]:
        """Delete files from netdisk.

        Args:
            file_paths: List of remote file paths to delete.

        Returns:
            API response dict.
        """
        url = f"{BAIDU_PAN_URL}/rest/2.0/xpan/file"
        params = {"method": "filemanager", "opera": "delete"}
        data = {"async": 0, "filelist": json.dumps(file_paths)}
        return self._request("POST", url, params=params, data=data)

    def move(
        self, file_paths: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Move files on netdisk.

        Args:
            file_paths: List of dicts with 'path', 'dest', 'newname' keys.
                Example: [{"path": "/a/file.txt", "dest": "/b/", "newname": "file.txt"}]

        Returns:
            API response dict.
        """
        url = f"{BAIDU_PAN_URL}/rest/2.0/xpan/file"
        params = {"method": "filemanager", "opera": "move"}
        data = {"async": 0, "filelist": json.dumps(file_paths)}
        return self._request("POST", url, params=params, data=data)

    def rename(self, file_path: str, new_name: str) -> Dict[str, Any]:
        """Rename a file on netdisk.

        Args:
            file_path: Current file path.
            new_name: New file name.

        Returns:
            API response dict.
        """
        url = f"{BAIDU_PAN_URL}/rest/2.0/xpan/file"
        params = {"method": "filemanager", "opera": "rename"}
        data = {
            "async": 0,
            "filelist": json.dumps([{"path": file_path, "newname": new_name}]),
        }
        return self._request("POST", url, params=params, data=data)

    def copy(
        self, file_paths: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Copy files on netdisk.

        Args:
            file_paths: List of dicts with 'path', 'dest', 'newname' keys.

        Returns:
            API response dict.
        """
        url = f"{BAIDU_PAN_URL}/rest/2.0/xpan/file"
        params = {"method": "filemanager", "opera": "copy"}
        data = {"async": 0, "filelist": json.dumps(file_paths)}
        return self._request("POST", url, params=params, data=data)

    # ─── Share Operations ────────────────────────────────────────────

    def create_share(
        self,
        fs_ids: List[int],
        password: Optional[str] = None,
        period: int = 0,
    ) -> Dict[str, Any]:
        """Create a share link.

        Args:
            fs_ids: List of file/folder IDs to share.
            password: Share password (4 chars). Auto-generated if not provided.
            period: Validity period in days (0=permanent, 1, 7, 30).

        Returns:
            dict with 'link', 'password', 'shorturl', etc.
        """
        if password is None:
            import random
            import string
            password = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))

        url = f"{BAIDU_PAN_URL}/rest/2.0/xpan/share"
        params = {"method": "set"}
        data = {
            "fid_list": json.dumps(fs_ids),
            "schannel": 4,
            "channel_list": "[]",
            "period": period,
            "pwd": password,
        }
        resp = self._request("POST", url, params=params, data=data)
        resp["password"] = password
        return resp

    def list_shares(self, start: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """List current shares.

        Args:
            start: Start index.
            limit: Max results.

        Returns:
            List of share info dicts.
        """
        url = f"{BAIDU_PAN_URL}/rest/2.0/xpan/share"
        params = {"method": "list", "start": start, "limit": limit}
        resp = self._request("GET", url, params=params)
        return resp.get("list", [])

    def cancel_share(self, share_ids: List[int]) -> Dict[str, Any]:
        """Cancel shares.

        Args:
            share_ids: List of share IDs to cancel.

        Returns:
            API response dict.
        """
        url = f"{BAIDU_PAN_URL}/rest/2.0/xpan/share"
        params = {"method": "cancel"}
        data = {"shareid_list": json.dumps(share_ids)}
        return self._request("POST", url, params=params, data=data)

    # ─── Quota / Space Info ──────────────────────────────────────────

    def get_quota(self) -> Dict[str, Any]:
        """Get storage quota information.

        Returns:
            dict with 'total', 'used', 'free' in bytes and _gb variants.
        """
        url = f"{BAIDU_PAN_URL}/api/quota"
        params = {"checkfree": 1, "checkexpire": 1}
        resp = self._request("GET", url, params=params)

        total = resp.get("total", 0)
        used = resp.get("used", 0)
        free = total - used

        return {
            "total": total,
            "used": used,
            "free": free,
            "total_gb": total / (1024 ** 3),
            "used_gb": used / (1024 ** 3),
            "free_gb": free / (1024 ** 3),
        }

    # ─── Internal Helpers ────────────────────────────────────────────

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated request to Baidu API.

        Raises:
            AuthError: If not authenticated.
            APIError: If API returns an error.
        """
        retries = self._config["max_retries"]
        timeout = self._config["timeout"]

        for attempt in range(retries):
            try:
                resp = self.session.request(
                    method, url, params=params, data=data, files=files, timeout=timeout
                )
                resp.raise_for_status()
                result = resp.json()

                errno = result.get("errno", 0)
                if errno == -6:
                    raise AuthError("Session expired. Please login again.")
                if errno != 0:
                    raise APIError(errno, result.get("errmsg", "Unknown error"))

                return result
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    raise APIError(-1, f"Request failed after {retries} retries: {e}")
                time.sleep(1 * (attempt + 1))

        return {}

    def _get_fsid(self, remote_path: str) -> int:
        """Get file system ID for a given path."""
        dir_path = "/".join(remote_path.rstrip("/").split("/")[:-1]) or "/"
        file_name = remote_path.rstrip("/").split("/")[-1]
        files = self.list_files(dir_path)
        for f in files:
            if f.get("server_filename") == file_name:
                return f["fs_id"]
        raise APIError(-1, f"File not found: {remote_path}")

    @staticmethod
    def _calculate_block_list(file_path: Path) -> List[str]:
        """Calculate MD5 block list for upload pre-create."""
        block_list = []
        chunk_size = 4 * 1024 * 1024  # 4MB
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                md5_hash = hashlib.md5(chunk).hexdigest()
                block_list.append(md5_hash)
        return block_list

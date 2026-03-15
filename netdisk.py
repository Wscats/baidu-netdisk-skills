#!/usr/bin/env python3
"""
Baidu Netdisk Manager - Command line interface.

Usage:
    python netdisk.py login                        # QR code login (default)
    python netdisk.py login --qrcode               # QR code login (explicit)
    python netdisk.py login --cookie "BDUSS=xxx"   # Cookie login
    python netdisk.py whoami                       # Check login status
    python netdisk.py list /                       # List files
    python netdisk.py search "keyword"             # Search files
    python netdisk.py upload ./file.pdf /remote/   # Upload file
    python netdisk.py download /remote/file.pdf    # Download file
    python netdisk.py delete /remote/file.pdf      # Delete file
    python netdisk.py move /old/f.txt /new/        # Move file
    python netdisk.py rename /path/old.txt new.txt # Rename file
    python netdisk.py copy /src/f.txt /dest/       # Copy file
    python netdisk.py share /path/file.pdf         # Share file
    python netdisk.py shares                       # List shares
    python netdisk.py unshare <share_id>           # Cancel share
    python netdisk.py info                         # Storage info
    python netdisk.py info --analyze               # Space analysis
"""

import sys
import io
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from netdisk_sdk import BaiduNetdisk, QRCodeAuth, AuthError, APIError

console = Console()


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def format_time(timestamp: int) -> str:
    """Format unix timestamp to readable string."""
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def get_client() -> BaiduNetdisk:
    """Get an authenticated BaiduNetdisk client."""
    client = BaiduNetdisk()
    return client


@click.group()
def cli():
    """百度网盘管理助手 - Baidu Netdisk Manager CLI"""
    pass


# ─── Login Commands ──────────────────────────────────────────────────


@cli.command()
@click.option("--qrcode", is_flag=True, default=False, help="Login via QR code scan (default if no option given)")
@click.option("--cookie", default=None, help='Login via cookie, e.g. "BDUSS=xxx" or "BDUSS=xxx;STOKEN=yyy"')
def login(qrcode, cookie):
    """Login to Baidu Netdisk. Default: QR code login."""
    if cookie:
        _login_cookie(cookie)
    else:
        # Default to QR code login when no option is specified
        _login_qrcode()


def _login_qrcode():
    """Handle QR code login flow."""
    console.print("[bold cyan]Generating QR code...[/bold cyan]")

    auth = QRCodeAuth()
    qr_info = auth.generate_qrcode()
    image_url = qr_info["image_url"]
    sign = qr_info["sign"]

    # Display QR code in terminal
    try:
        import qrcode as qr_lib
        qr = qr_lib.QRCode(version=1, box_size=1, border=1)
        qr.add_data(image_url)
        qr.make(fit=True)

        # Print to terminal
        f = io.StringIO()
        qr.print_ascii(out=f, invert=True)
        console.print(Panel(f.getvalue(), title="[bold]Scan with Baidu Netdisk App[/bold]"))
    except ImportError:
        console.print(f"[yellow]QR Code URL: {image_url}[/yellow]")
        console.print("[yellow]Open this URL in browser to see QR code[/yellow]")

    console.print("[bold green]Waiting for scan...[/bold green] (timeout: 120s)")

    try:
        credentials = auth.poll_login(sign, max_wait=120)
        # Save session
        client = BaiduNetdisk(
            bduss=credentials["bduss"], stoken=credentials["stoken"]
        )
        user = client.get_user_info()
        console.print(
            f"[bold green]✅ Login successful![/bold green] "
            f"Welcome, {user.get('baidu_name', 'User')}"
        )
    except AuthError as e:
        console.print(f"[bold red]❌ Login failed: {e}[/bold red]")


def _login_cookie(cookie_str: str):
    """Handle cookie-based login."""
    parts = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key.strip()] = value.strip()

    bduss = parts.get("BDUSS", "")
    stoken = parts.get("STOKEN", "")

    if not bduss:
        console.print("[bold red]❌ BDUSS not found in cookie string.[/bold red]")
        console.print('[yellow]Usage: python netdisk.py login --cookie "BDUSS=your_value"[/yellow]')
        return

    try:
        client = BaiduNetdisk(bduss=bduss, stoken=stoken)
        user = client.get_user_info()
        console.print(
            f"[bold green]✅ Login successful![/bold green] "
            f"Welcome, {user.get('baidu_name', 'User')}"
        )
    except (AuthError, APIError) as e:
        console.print(f"[bold red]❌ Login failed: {e}[/bold red]")


@cli.command()
def whoami():
    """Check current login status."""
    client = get_client()
    try:
        user = client.get_user_info()
        table = Table(title="User Info", box=box.ROUNDED)
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Baidu Name", user.get("baidu_name", "N/A"))
        table.add_row("Netdisk Name", user.get("netdisk_name", "N/A"))
        table.add_row("VIP Type", str(user.get("vip_type", 0)))
        table.add_row("Avatar URL", user.get("avatar_url", "N/A"))
        console.print(table)
    except AuthError:
        console.print("[bold red]❌ Not logged in. Use 'login' command first.[/bold red]")
    except APIError as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")


# ─── File Commands ───────────────────────────────────────────────────


@cli.command(name="list")
@click.argument("path", default="/")
@click.option("--sort", default="name", type=click.Choice(["name", "time", "size"]))
@click.option("--order", default="asc", type=click.Choice(["asc", "desc"]))
def list_files(path, sort, order):
    """List files in a directory."""
    client = get_client()
    try:
        files = client.list_files(path, order=sort, desc=(order == "desc"))

        table = Table(title=f"Files in: {path}", box=box.ROUNDED)
        table.add_column("#", style="dim", width=4)
        table.add_column("Name", style="cyan", min_width=20)
        table.add_column("Size", justify="right", style="green")
        table.add_column("Modified", style="yellow")
        table.add_column("Type", style="magenta")

        for i, f in enumerate(files, 1):
            is_dir = f.get("isdir", 0) == 1
            name = f.get("server_filename", "")
            size = format_size(f.get("size", 0)) if not is_dir else "-"
            mtime = format_time(f.get("server_mtime", 0))
            ftype = "📁 Folder" if is_dir else "📄 File"
            table.add_row(str(i), name, size, mtime, ftype)

        console.print(table)
        console.print(f"[dim]Total: {len(files)} items[/dim]")
    except (AuthError, APIError) as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")


@cli.command()
@click.argument("keyword")
@click.option("--dir", "dir_path", default="/", help="Directory to search in")
def search(keyword, dir_path):
    """Search files by keyword."""
    client = get_client()
    try:
        results = client.search(keyword, dir_path=dir_path)

        table = Table(title=f"Search: '{keyword}'", box=box.ROUNDED)
        table.add_column("#", style="dim", width=4)
        table.add_column("Name", style="cyan", min_width=20)
        table.add_column("Path", style="blue")
        table.add_column("Size", justify="right", style="green")

        for i, f in enumerate(results, 1):
            table.add_row(
                str(i),
                f.get("server_filename", ""),
                f.get("path", ""),
                format_size(f.get("size", 0)),
            )

        console.print(table)
        console.print(f"[dim]Found: {len(results)} items[/dim]")
    except (AuthError, APIError) as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")


@cli.command()
@click.argument("local_path")
@click.argument("remote_dir")
@click.option("--recursive", is_flag=True, help="Upload directory recursively")
def upload(local_path, remote_dir, recursive):
    """Upload file to netdisk."""
    import os
    client = get_client()

    if os.path.isdir(local_path) and recursive:
        for root, dirs, files in os.walk(local_path):
            for fname in files:
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(root, local_path)
                rdir = f"{remote_dir.rstrip('/')}/{rel}" if rel != "." else remote_dir
                console.print(f"[cyan]Uploading: {fpath} → {rdir}[/cyan]")
                try:
                    client.upload(fpath, rdir)
                    console.print(f"[green]  ✅ Done[/green]")
                except (AuthError, APIError) as e:
                    console.print(f"[red]  ❌ Failed: {e}[/red]")
    else:
        console.print(f"[cyan]Uploading: {local_path} → {remote_dir}[/cyan]")
        try:
            result = client.upload(local_path, remote_dir)
            console.print(f"[bold green]✅ Upload successful![/bold green]")
            console.print(f"  Path: {result.get('path', '')}")
            console.print(f"  Size: {format_size(result.get('size', 0))}")
        except (AuthError, APIError) as e:
            console.print(f"[bold red]❌ Upload failed: {e}[/bold red]")


@cli.command()
@click.argument("remote_path")
@click.option("--output", "-o", default=None, help="Local output directory")
def download(remote_path, output):
    """Download file from netdisk."""
    client = get_client()
    console.print(f"[cyan]Downloading: {remote_path}[/cyan]")
    try:
        local_path = client.download(remote_path, local_dir=output)
        console.print(f"[bold green]✅ Downloaded to: {local_path}[/bold green]")
    except (AuthError, APIError) as e:
        console.print(f"[bold red]❌ Download failed: {e}[/bold red]")


@cli.command()
@click.argument("paths", nargs=-1)
def delete(paths):
    """Delete files from netdisk."""
    if not paths:
        console.print("[yellow]Please specify file paths to delete.[/yellow]")
        return

    client = get_client()
    console.print(f"[cyan]Deleting {len(paths)} file(s)...[/cyan]")
    try:
        client.delete(list(paths))
        console.print(f"[bold green]✅ Deleted successfully![/bold green]")
    except (AuthError, APIError) as e:
        console.print(f"[bold red]❌ Delete failed: {e}[/bold red]")


@cli.command()
@click.argument("source")
@click.argument("dest")
def move(source, dest):
    """Move file to another directory."""
    client = get_client()
    file_name = source.rstrip("/").split("/")[-1]
    try:
        client.move([{"path": source, "dest": dest, "newname": file_name}])
        console.print(f"[bold green]✅ Moved: {source} → {dest}{file_name}[/bold green]")
    except (AuthError, APIError) as e:
        console.print(f"[bold red]❌ Move failed: {e}[/bold red]")


@cli.command()
@click.argument("file_path")
@click.argument("new_name")
def rename(file_path, new_name):
    """Rename a file."""
    client = get_client()
    try:
        client.rename(file_path, new_name)
        console.print(f"[bold green]✅ Renamed to: {new_name}[/bold green]")
    except (AuthError, APIError) as e:
        console.print(f"[bold red]❌ Rename failed: {e}[/bold red]")


@cli.command()
@click.argument("source")
@click.argument("dest")
def copy(source, dest):
    """Copy file to another directory."""
    client = get_client()
    file_name = source.rstrip("/").split("/")[-1]
    try:
        client.copy([{"path": source, "dest": dest, "newname": file_name}])
        console.print(f"[bold green]✅ Copied: {source} → {dest}{file_name}[/bold green]")
    except (AuthError, APIError) as e:
        console.print(f"[bold red]❌ Copy failed: {e}[/bold red]")


# ─── Share Commands ──────────────────────────────────────────────────


@cli.command()
@click.argument("file_path")
@click.option("--days", default=0, help="Validity period in days (0=permanent)")
@click.option("--password", default=None, help="Share password (4 chars)")
def share(file_path, days, password):
    """Create a share link for a file."""
    client = get_client()
    try:
        # Get fsid first
        fsid = client._get_fsid(file_path)
        result = client.create_share([fsid], password=password, period=days)
        console.print(Panel(
            f"Link: {result.get('link', result.get('shorturl', 'N/A'))}\n"
            f"Password: {result.get('password', 'N/A')}",
            title="[bold green]Share Created[/bold green]",
            border_style="green",
        ))
    except (AuthError, APIError) as e:
        console.print(f"[bold red]❌ Share failed: {e}[/bold red]")


@cli.command()
def shares():
    """List all shares."""
    client = get_client()
    try:
        share_list = client.list_shares()
        table = Table(title="My Shares", box=box.ROUNDED)
        table.add_column("ID", style="dim")
        table.add_column("Name", style="cyan")
        table.add_column("Link", style="blue")
        table.add_column("Status", style="green")

        for s in share_list:
            table.add_row(
                str(s.get("shareid", "")),
                s.get("typicalPath", ""),
                s.get("shortlink", ""),
                "Active" if s.get("status", 0) == 0 else "Expired",
            )
        console.print(table)
    except (AuthError, APIError) as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")


@cli.command()
@click.argument("share_id", type=int)
def unshare(share_id):
    """Cancel a share."""
    client = get_client()
    try:
        client.cancel_share([share_id])
        console.print(f"[bold green]✅ Share {share_id} cancelled.[/bold green]")
    except (AuthError, APIError) as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")


# ─── Space Info Commands ─────────────────────────────────────────────


@cli.command()
@click.option("--analyze", is_flag=True, help="Analyze space by file type")
def info(analyze):
    """Show storage info."""
    client = get_client()
    try:
        quota = client.get_quota()

        # Build usage bar
        used_pct = (quota["used"] / quota["total"] * 100) if quota["total"] > 0 else 0
        bar_len = 30
        filled = int(bar_len * used_pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)

        color = "green" if used_pct < 60 else ("yellow" if used_pct < 85 else "red")

        console.print(Panel(
            f"Total:  {quota['total_gb']:.1f} GB\n"
            f"Used:   {quota['used_gb']:.1f} GB\n"
            f"Free:   {quota['free_gb']:.1f} GB\n\n"
            f"[{color}]{bar} {used_pct:.1f}%[/{color}]",
            title="[bold]Storage Info[/bold]",
            border_style="blue",
        ))

        if analyze:
            _analyze_space(client)

    except (AuthError, APIError) as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")


def _analyze_space(client: BaiduNetdisk):
    """Analyze space usage by file type."""
    console.print("[cyan]Analyzing space usage...[/cyan]")

    categories = {
        "Documents": ["doc", "docx", "pdf", "txt", "ppt", "pptx", "xls", "xlsx", "csv"],
        "Images": ["jpg", "jpeg", "png", "gif", "bmp", "svg", "webp", "heic"],
        "Videos": ["mp4", "avi", "mkv", "mov", "wmv", "flv", "m4v"],
        "Audio": ["mp3", "flac", "wav", "aac", "ogg", "m4a", "wma"],
        "Archives": ["zip", "rar", "7z", "tar", "gz", "bz2"],
        "Other": [],
    }

    stats = {cat: {"count": 0, "size": 0} for cat in categories}

    # Scan root recursively (limited depth)
    _scan_dir(client, "/", categories, stats, depth=0, max_depth=2)

    table = Table(title="Space Analysis by Type", box=box.ROUNDED)
    table.add_column("Category", style="cyan")
    table.add_column("Files", justify="right", style="yellow")
    table.add_column("Size", justify="right", style="green")

    for cat, data in stats.items():
        if data["count"] > 0 or cat != "Other":
            table.add_row(cat, str(data["count"]), format_size(data["size"]))

    console.print(table)


def _scan_dir(client, path, categories, stats, depth, max_depth):
    """Recursively scan directory for space analysis."""
    if depth > max_depth:
        return
    try:
        files = client.list_files(path, limit=1000)
        for f in files:
            if f.get("isdir", 0) == 1:
                sub_path = f.get("path", "")
                _scan_dir(client, sub_path, categories, stats, depth + 1, max_depth)
            else:
                size = f.get("size", 0)
                name = f.get("server_filename", "")
                ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""

                categorized = False
                for cat, exts in categories.items():
                    if ext in exts:
                        stats[cat]["count"] += 1
                        stats[cat]["size"] += size
                        categorized = True
                        break
                if not categorized:
                    stats["Other"]["count"] += 1
                    stats["Other"]["size"] += size
    except Exception:
        pass


if __name__ == "__main__":
    cli()

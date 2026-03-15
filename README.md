# 百度网盘管理助手 (Baidu Netdisk Manager)

## 🚀 快速使用

```bash
# 1. 克隆项目
git clone https://github.com/your-username/baidu-netdisk-skills.git
cd baidu-netdisk-skills

# 2. 安装依赖
pip install -r requirements.txt

# 3. 登录（二选一）

# 方式一：扫码登录（推荐）
python netdisk.py login --qrcode

# 方式二：Cookie 登录（从浏览器复制 BDUSS）
python netdisk.py login --cookie "BDUSS=your_bduss_value"

# 4. 开始使用
python netdisk.py list /                    # 列出根目录文件
python netdisk.py search "期末考试"          # 搜索文件
python netdisk.py upload ./local.pdf /docs/ # 上传文件
python netdisk.py download /docs/file.pdf   # 下载文件
python netdisk.py info                      # 查看空间信息
```

---

## 📖 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [安装方式](#安装方式)
- [认证登录](#认证登录)
- [命令详解](#命令详解)
- [Python API 调用](#python-api-调用)
- [配置说明](#配置说明)
- [常见问题](#常见问题)
- [许可证](#许可证)

---

## 项目简介

百度网盘管理助手是一个基于 Python 的命令行工具，提供对百度网盘的完整管理功能。支持 **扫码登录** 和 **Cookie 导入** 两种认证方式，涵盖文件的增删改查、分享、空间分析等核心操作。

## 功能特性

| 模块     | 功能                                       |
| -------- | ------------------------------------------ |
| 🔐 认证  | 扫码登录、Cookie 登录、会话持久化、自动续期 |
| 📂 文件  | 列表、搜索、上传、下载、删除、移动、重命名、复制 |
| 🔗 分享  | 创建分享（带密码/有效期）、查看分享、取消分享 |
| 💾 空间  | 容量查看、文件类型统计分析                 |

## 安装方式

### 环境要求

- Python 3.9+
- pip 包管理器

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/your-username/baidu-netdisk-skills.git
cd baidu-netdisk-skills

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt
```

## 认证登录

### 方式一：扫码登录（推荐）

```bash
python netdisk.py login --qrcode
```

执行后终端会显示二维码，使用百度网盘 App 扫码即可完成登录。登录凭证会自动保存到 `~/.netdisk/session.json`。

### 方式二：Cookie 登录

1. 在浏览器中登录 [百度网盘](https://pan.baidu.com)
2. 按 `F12` 打开开发者工具 → Application → Cookies
3. 复制 `BDUSS` 的值（可选：同时复制 `STOKEN`）

```bash
# 仅使用 BDUSS
python netdisk.py login --cookie "BDUSS=your_bduss_value"

# 使用 BDUSS + STOKEN（功能更完整）
python netdisk.py login --cookie "BDUSS=xxx;STOKEN=yyy"
```

### 验证登录状态

```bash
python netdisk.py whoami
```

## 命令详解

### 文件列表

```bash
# 列出根目录
python netdisk.py list /

# 列出指定目录
python netdisk.py list /我的文档

# 按时间排序
python netdisk.py list / --sort time --order desc
```

### 文件搜索

```bash
# 按关键词搜索
python netdisk.py search "论文"

# 指定搜索目录
python netdisk.py search "照片" --dir /我的相册
```

### 文件上传

```bash
# 上传单个文件
python netdisk.py upload ./report.pdf /工作文档/

# 上传整个目录
python netdisk.py upload ./photos/ /我的相册/ --recursive
```

### 文件下载

```bash
# 下载文件到当前目录
python netdisk.py download /工作文档/report.pdf

# 指定下载位置
python netdisk.py download /工作文档/report.pdf --output ~/Downloads/
```

### 文件删除

```bash
# 删除单个文件
python netdisk.py delete /临时文件/test.txt

# 批量删除（支持通配符）
python netdisk.py delete "/临时文件/*.tmp"
```

### 文件移动/重命名

```bash
# 移动文件
python netdisk.py move /旧目录/file.txt /新目录/

# 重命名
python netdisk.py rename /文档/old_name.pdf new_name.pdf
```

### 文件复制

```bash
python netdisk.py copy /文档/file.txt /备份/
```

### 创建分享

```bash
# 创建分享（默认永久有效、随机密码）
python netdisk.py share /文档/file.pdf

# 设置有效期（天数）和自定义密码
python netdisk.py share /文档/file.pdf --days 7 --password abc1
```

### 查看/取消分享

```bash
# 列出所有分享
python netdisk.py shares

# 取消分享
python netdisk.py unshare <share_id>
```

### 空间信息

```bash
# 查看空间使用情况
python netdisk.py info

# 按类型分析空间占用
python netdisk.py info --analyze
```

## Python API 调用

除命令行外，也可以在 Python 代码中直接调用：

```python
from netdisk_sdk import BaiduNetdisk

# 使用 Cookie 初始化
nd = BaiduNetdisk(bduss="your_bduss", stoken="your_stoken")

# 列出文件
files = nd.list_files("/我的文档")
for f in files:
    print(f"{f['server_filename']}  {f['size']} bytes")

# 搜索文件
results = nd.search("合同")

# 上传文件
nd.upload("./local_file.pdf", "/网盘目录/")

# 下载文件
nd.download("/网盘目录/file.pdf", "./local_path/")

# 获取空间信息
quota = nd.get_quota()
print(f"已用: {quota['used_gb']:.1f} GB / 总计: {quota['total_gb']:.1f} GB")

# 创建分享
share = nd.create_share("/文档/file.pdf", password="ab12", days=7)
print(f"分享链接: {share['link']}  密码: {share['password']}")
```

## 配置说明

配置文件位于 `~/.netdisk/config.json`：

```json
{
  "download_dir": "~/Downloads/netdisk",
  "chunk_size": 4194304,
  "max_retries": 3,
  "timeout": 30,
  "auto_rename": true
}
```

| 配置项       | 说明                   | 默认值               |
| ------------ | ---------------------- | -------------------- |
| download_dir | 默认下载目录           | `~/Downloads/netdisk`|
| chunk_size   | 分片上传大小 (bytes)   | `4194304` (4MB)      |
| max_retries  | 请求失败重试次数       | `3`                  |
| timeout      | 请求超时时间 (秒)      | `30`                 |
| auto_rename  | 同名文件自动重命名     | `true`               |

## 常见问题

**Q: 扫码登录后提示"会话已过期"？**
A: 百度网盘登录凭证有效期约30天，过期后重新执行 `python netdisk.py login --qrcode` 登录。

**Q: Cookie 登录应该复制哪些值？**
A: 必须复制 `BDUSS`，建议同时复制 `STOKEN` 以获得完整功能。

**Q: 上传大文件失败？**
A: 工具使用分片上传，默认分片 4MB。如果网络不稳定，可减小 `chunk_size` 配置。

**Q: 下载速度慢？**
A: 非 SVIP 用户下载速度受百度限制，建议开通 SVIP 获得极速下载。

## 许可证

MIT License - 详见 [LICENSE](./LICENSE)

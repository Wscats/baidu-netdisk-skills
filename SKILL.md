---
name: baidu-netdisk-manager
license: MIT
description: >
  This skill manages Baidu Netdisk (百度网盘) files and storage via Python scripts.
  It supports QR code login and cookie-based authentication. Core features include
  file listing, uploading, downloading, searching, deleting, moving, renaming,
  sharing, and storage quota analysis. Trigger phrases include "list my files",
  "upload file", "download file", "search netdisk", "share file", "delete file",
  "storage info", "netdisk login", "百度网盘", "网盘登录", "扫码登录",
  "文件列表", "上传文件", "下载文件", "搜索文件", "分享文件",
  "删除文件", "网盘空间", "文件管理".
---

# 百度网盘管理 Skill

## 技能概述

| 属性       | 值                            |
| ---------- | ----------------------------- |
| 技能 ID    | `baidu-netdisk-manager`       |
| 版本       | `1.0.0`                       |
| 协议       | MIT                           |
| 运行环境   | Python 3.9+                   |
| 认证方式   | 扫码登录 / Cookie 导入        |

## 功能清单

### 1. 认证登录
| 功能         | 说明                                          |
| ------------ | --------------------------------------------- |
| 扫码登录     | 生成二维码，使用百度网盘 App 扫码完成登录     |
| Cookie 登录  | 从浏览器复制 Cookie（BDUSS/STOKEN）直接导入   |
| 会话持久化   | 登录凭证保存到本地，支持自动续期              |

### 2. 文件管理
| 功能         | 说明                                          |
| ------------ | --------------------------------------------- |
| 文件列表     | 列出指定目录下的文件和文件夹                  |
| 文件搜索     | 按关键词搜索网盘中的文件                      |
| 文件上传     | 上传本地文件到网盘指定目录                    |
| 文件下载     | 从网盘下载文件到本地                          |
| 文件删除     | 删除网盘中的文件或文件夹                      |
| 文件移动     | 移动文件到其他目录                            |
| 文件重命名   | 重命名网盘中的文件                            |
| 文件复制     | 复制文件到其他目录                            |

### 3. 分享管理
| 功能         | 说明                                          |
| ------------ | --------------------------------------------- |
| 创建分享     | 创建文件分享链接（支持设置密码和有效期）      |
| 查看分享     | 列出当前已创建的所有分享                      |
| 取消分享     | 取消已创建的分享链接                          |

### 4. 空间管理
| 功能         | 说明                                          |
| ------------ | --------------------------------------------- |
| 空间信息     | 查看网盘总容量、已用空间、剩余空间            |
| 空间分析     | 按文件类型统计空间占用                        |

## 技能触发词

**英文**: `list files`, `upload file`, `download file`, `search netdisk`,
`share file`, `delete file`, `storage info`, `netdisk login`

**中文**: `百度网盘`, `网盘登录`, `扫码登录`, `文件列表`, `上传文件`,
`下载文件`, `搜索文件`, `分享文件`, `删除文件`, `网盘空间`, `文件管理`

## 权限要求

- 百度网盘账号（普通用户或 SVIP）
- 网络访问权限（访问百度网盘 API）
- 本地文件读写权限（用于上传/下载）

## 输出格式

所有接口返回统一 JSON 格式：

```json
{
  "code": 0,
  "message": "success",
  "data": { }
}
```

错误时返回：

```json
{
  "code": -1,
  "message": "error description",
  "data": null
}
```

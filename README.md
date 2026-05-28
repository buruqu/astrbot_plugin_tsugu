# Tsugu Bang Dream! 游戏助手

> AstrBot 插件：BanG Dream! 少女乐团派对 全能游戏助手，基于 tsugu-api-python

---

## 🎮 功能特性

- **查曲** / **查卡** / **查卡面** / **查角色** / **查活动** / **查卡池**
- **抽卡模拟** / **查谱面** / **分数表** / **查试炼**
- **档线查询**（ycx / ycxall / lsycx）
- **车牌系统**（车牌列表 / 车牌转发 / 智能识别）
- **玩家绑定**（多服务器 / 多账号切换）
- **随机曲目** / **主服务器设置** / **显示服务器配置**

---

## 📦 安装方法

### 1. 下载插件

将本插件放入 AstrBot 插件目录：

```bash
# 方式一：从 Releases 下载
# 解压后放入 AstrBot data/plugins/ 目录

# 方式二：克隆仓库
cd ~/.astrbot/data/plugins/
git clone https://github.com/buruqu/astrbot_plugin_tsugu.git
```

### 2. 安装依赖

```bash
pip install tsugu-api-python
```

### 3. 重启 AstrBot

```bash
astrbot restart
```

---

## ⚙️ 配置说明

在 AstrBot Dashboard 中配置插件：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `backend_url` | Tsugu 后端地址 | `http://tsugubot.com:8080` |
| `userdata_backend_url` | 用户数据后端地址 | `http://tsugubot.com:8080` |
| `proxy` | 代理地址（留空则不使用） | 空 |
| `use_easy_bg` | 使用简易背景 | `true` |
| `compress` | 压缩图片 | `true` |
| `bandori_station_token` | Bandori Station API 令牌 | 空 |
| `whitelist_enabled` | 启用白名单模式 | `false` |
| `whitelist_groups` | 白名单群组列表 | `[]` |
| `at_wake_enabled` | @唤醒功能 | `true` |
| `at_sender_enabled` | 回复时 @发送人 | `false` |
| `quote_reply_enabled` | 引用原消息 | `false` |
| `wake_prefix` | 自定义唤醒前缀 | 空 |
| `command_aliases` | 命令别名映射（JSON） | `{}` |

---

## 📋 命令列表

### 曲目相关
| 命令 | 说明 | 示例 |
|------|------|------|
| `查曲 <关键词>` | 查询曲目信息 | `查曲 光る星` |
| `查谱面 <曲目ID> <难度>` | 查询谱面 | `查谱面 114 4` |
| `分数表 <服务器> <曲目ID>` | 查询分数表 | `分数表 jp 114` |
| `随机曲目` | 随机一首曲目 | `随机曲目` |

### 卡牌相关
| 命令 | 说明 | 示例 |
|------|------|------|
| `查卡 <关键词>` | 查询卡牌信息 | `查卡 2222` |
| `查卡面 <卡牌ID>` | 查询卡面插画 | `查卡面 2222` |

### 角色/活动/卡池
| 命令 | 说明 |
|------|------|
| `查角色 <关键词>` | 查询角色信息 |
| `查活动 <关键词>` | 查询活动信息 |
| `查卡池 <关键词>` | 查询卡池信息 |
| `查试炼` | 查询当前活动试炼 |

### 档线查询
| 命令 | 说明 | 示例 |
|------|------|------|
| `ycx <档位> <服务器>` | 查询预测线 | `ycx 200 jp` |
| `ycxall <服务器>` | 查询所有档位 | `ycxall jp` |
| `lsycx <档位> <服务器>` | 查询历史档线 | `lsycx 200 jp` |

### 车牌系统
| 命令 | 说明 |
|------|------|
| `车牌列表` / `ycm` / `有车吗` | 查询当前车牌 |
| `开启车牌转发` | 开启车牌自动转发 |
| `关闭车牌转发` | 关闭车牌自动转发 |
| `（直接发送车牌号）` | 提交车牌（智能识别） |

> 💡 无车牌时自动发送提示图片

### 玩家绑定
| 命令 | 说明 | 示例 |
|------|------|------|
| `玩家绑定 <服务器>` | 开始绑定流程 | `玩家绑定 jp` |
| `绑定<验证码>` | 发送验证码完成绑定 | `绑定123456` |
| `解除绑定` | 解除绑定 | `解除绑定` |
| `玩家状态` | 查询绑定状态（支持序号） | `玩家状态` / `玩家状态 1` |
| `绑定列表` | 查看所有绑定 | `绑定列表` |
| `选择绑定 <index>` | 切换默认绑定 | `选择绑定 2` |

### 服务器设置
| 命令 | 说明 | 示例 |
|------|------|------|
| `主服务器 <服务器>` | 设置主服务器 | `主服务器 jp` |
| `显示服务器 <服务器...>` | 设置显示服务器 | `显示服务器 jp cn` |

---

## 🆕 v1.4.0 更新日志

### ✨ 新增功能
- 车牌无结果时发送提示图片（`assets/no_car.jpg`）
- 新增快捷命令：`有车吗` → 车牌列表
- 支持 `bandori_station_token` 配置项
- 支持 `玩家状态1`/`玩家状态2` 查询绑定列表指定账号（同服多账号支持）

### 🐛 问题修复
- 修复 `station_submit_room_number()` 缺少 `user_id` 和 `user_name` 参数导致的报错
- 修复车牌识别正则过于宽泛，导致其他用户发送数字时也触发报错
- 修复 `@register` 装饰器 `github_url` 与 `metadata.yaml` 不一致

### ⚡ 优化改进
- 车牌识别改用智能判断（参考 Ars1027 的 `looks_like_car()` 思路）
- 绑定会话增加 10 分钟超时机制，防止内存泄漏
- 定期清理过期绑定会话
- 命令别名系统支持动态注入

---

## 🙏 致谢

本插件的优化思路部分参考了 [Ars1027/astrbot_plugin_tsugu_bangdream](https://github.com/Ars1027/astrbot_plugin_tsugu_bangdream) 的实现，包括：

- **车牌智能识别算法**（`looks_like_car()` 思路）
- **Fake 关键词过滤机制**（`FAKE_CAR_KEYWORDS` 设计）
- **玩家绑定流程优化建议**

感谢 Ars1027 的开源贡献！

---

## 📖 技术栈

- **框架**：AstrBot Star 插件系统
- **API**：tsugu-api-python (异步版)
- **消息组件**：AstrBot MessageChain (Plain / Image / At / Reply)

---

## 🔗 相关链接

- **插件仓库**：https://github.com/buruqu/astrbot_plugin_tsugu
- **Tsugu API**：https://github.com/TSGuu/tsugu-api-python
- **AstrBot 框架**：https://github.com/AstrBotDevs/AstrBot

---

## 📄 许可证

MIT License

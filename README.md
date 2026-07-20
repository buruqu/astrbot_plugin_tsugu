# Tsugu Bang Dream! 游戏助手

> AstrBot 插件：BanG Dream! 少女乐团派对 全能游戏助手，基于 tsugu-api-python

---

## 🎮 功能特性

- **查曲** / **查卡** / **查卡面** / **查角色** / **查活动** / **查卡池**
- **抽卡模拟** / **查谱面** / **分数表** / **查试炼**
- **档线查询**（ycx / ycxall / lsycx）
- **车牌系统**（车牌列表 / 车牌转发 / 智能识别 + 关键词过滤）
- **玩家绑定**（多服务器 / 多账号切换）
- **随机曲目** / **主服务器设置** / **显示服务器配置**
- **服务器名模糊搜索**（自动匹配模糊输入的服务器名）
- **30+ 默认命令别名**（ycm / 查卡牌 / 单抽 / 十连 / 查stage 等）
- **车牌关键词外置配置**（car_keyword.json，41 car + 34 fake 关键词）

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
| `at_wake_enabled` | @唤醒功能（不影响车牌被动转发） | `true` |
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

## 🆕 v2.0.1 更新日志

### 🐛 问题修复
- 修复普通群消息因 `at_wake_enabled` 被拦截，必须 @机器人后才会收集车牌的问题
- 修复 `tsugu-api-python 1.5.10` 使用秒级时间戳，导致后端将刚提交的车牌立即判定为过期的问题
- 严格识别消息开头的 5 或 6 位 ASCII 房间号，不再截取 7 位及以上数字

### ⚡ 优化改进
- 被动车牌监听改用 AstrBot 全消息事件，不再伪装成通配正则命令
- QQ 平台映射新增 OneBot、LLOneBot、NapCat、Chronocat 兼容
- 用户数据缺少 `shareRoomNumber` 字段时沿用上游默认开启行为
- 车牌提交恢复为上游一致的静默模式，成功与失败信息写入 AstrBot 日志
- 保留并完善 `抽卡`、`单抽`、`十连`、`新手十连` 别名

---

## 🆕 v2.0.0 更新日志

### ✨ 新增功能
- 车牌关键词外置配置（`car_keyword.json`），从原版移植 41 个 car 关键词 + 34 个 fake 关键词，替代硬编码
- 车牌识别改用 `checkLeftDigits` 左侧数字检测逻辑（先检测消息开头5-6位数字，再匹配 car/fake 关键词），大幅减少误触发
- 车牌列表支持关键词过滤（`车牌列表 <关键词>` / `ycm <关键词>`）
- 服务器名模糊搜索（调用 `tsugu_api_async.fuzzy_search`，支持模糊输入服务器名）
- 默认命令别名（从原版 `.alias()` / `.shortcut()` 移植）：
  - 车牌列表：ycm / 有车吗 / 车来
  - 查卡：查卡牌
  - 查卡面：查卡插画 / 查插画
  - 查玩家：查询玩家
  - 主服务器：服务器模式 / 切换服务器
  - 显示服务器：设置默认服务器 / 默认服务器
  - 绑定列表：玩家列表 / 玩家信息列表
  - 选择绑定：默认玩家ID / 默认玩家 / 玩家ID
  - 分数表：查询分数表 / 查分数表 / 查询分数榜 / 查分数榜
  - 查试炼：查stage / 查舞台 / 查festival / 查5v5
  - ycxall：myycx
  - 随机曲目：随机
  - 解除绑定：解绑玩家

### 🐛 问题修复
- 修复车牌识别过于宽泛导致非车牌消息误触发提交（如"平铺"等）
- 修复缺少 `car_keyword.json` 文件时回退到硬编码少量关键词（10+5）的问题
- 修复车牌提交后 `'module' object is not callable` 错误

### ⚡ 优化改进
- 车牌识别算法从 `_looks_like_car`（整体匹配）改为 `check_left_digits`（左侧数字检测），更精准
- 车牌提交后回复提交结果（成功/失败），便于用户确认
- 初始化日志输出更详细：白名单状态、@唤醒、唤醒前缀、别名数、关键词数

---

> 📜 历史版本更新日志（v1.0.0 ~ v1.4.0）请查看 [CHANGELOG_ARCHIVE.md](./CHANGELOG_ARCHIVE.md)

---

## 🙏 致谢

本插件在开发过程中参考和使用了以下项目和资源，在此表示感谢：

### 项目参考
- **[Yamamoto-2/tsugu-bangdream-bot](https://github.com/Yamamoto-2/tsugu-bangdream-bot)** — 原版 Tsugu Bang Dream! Bot，本插件的核心功能参考了其行为逻辑和实现思路
- **[Ars1027/astrbot_plugin_tsugu_bangdream](https://github.com/Ars1027/astrbot_plugin_tsugu_bangdream)** — AstrBot 版本的实现参考，包括：
  - 车牌智能识别算法（`looks_like_car()` 思路）
  - Fake 关键词过滤机制（`FAKE_CAR_KEYWORDS` 设计）
  - 玩家绑定流程优化建议

### 数据来源
- **[bestdori.com](https://bestdori.com/)** — BanG Dream! 综合数据网站，提供曲目、卡牌、活动、卡池等游戏数据查询

### 技术依赖
- **[Tsugu API](http://tsugubot.com:8080)** — 提供 BanG Dream! 游戏数据查询接口
- **[tsugu-api-python](https://github.com/TSGuu/tsugu-api-python)** — Tsugu API 的 Python 异步客户端库
- **[AstrBot](https://github.com/AstrBotDevs/AstrBot)** — 多功能 QQ 机器人框架

---

## 📖 参考文档与链接

| 资源 | 链接 | 用途 |
|------|------|------|
| Tsugu API 文档 | http://tsugubot.com:8080/docs | API 接口文档 |
| tsugu-api-python | https://github.com/TSGuu/tsugu-api-python | Python 客户端库 |
| bestdori.com | https://bestdori.com/ | 游戏数据参考 |
| Yamamoto-2 原版 Bot | https://github.com/Yamamoto-2/tsugu-bangdream-bot | 功能逻辑参考 |
| AstrBot 文档 | https://github.com/AstrBotDevs/AstrBot | 框架文档 |
| BanG Dream! 官网 | https://bang-dream.com/ | 游戏官方资料 |

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

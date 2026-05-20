<p align="center">
  <img src="https://img.shields.io/badge/version-1.3.0-blue?style=flat-square" alt="version">
  <img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python" alt="python">
  <img src="https://img.shields.io/badge/platform-AstrBot-7c3aed?style=flat-square" alt="platform">
  <img src="https://img.shields.io/badge/game-BanG%20Dream!-ff69b4?style=flat-square" alt="game">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="license">
</p>

<h1 align="center">🎸 astrbot_plugin_tsugu</h1>
<p align="center"><strong>BanG Dream! 少女乐团派对 · 全能游戏助手</strong></p>
<p align="center">为 <a href="https://github.com/Soulter/AstrBot">AstrBot</a> 平台打造的 Tsugu 插件，支持 <b>26 个命令</b>，覆盖曲目查询、卡牌图鉴、活动档线、玩家绑定、车牌管理等全部功能</p>

---

## 📖 简介

`astrbot_plugin_tsugu` 是将 [TsuguBanGDreamBot](https://github.com/Yamamoto-2/tsugu-bangdream-bot) 的全部功能移植到 [AstrBot](https://github.com/Soulter/AstrBot) 平台的插件，基于 [tsugu-api-python](https://github.com/WindowsSov8forUs/tsugu-api-python) 与 Tsugu 后端通信。

无论你是想查卡面、追活动档线、绑定游戏账号还是找车牌，一条消息就能搞定。

> **当前版本**: `v1.3.0` | **命令数**: 26 | **状态**: 🟢 维护中

---

## ✨ 功能一览

### 🎵 曲目查询
| 命令 | 说明 |
|------|------|
| `查曲` | 根据关键词或曲目 ID 查询曲目详情 |
| `查谱面` | 查询曲目谱面（可指定难度） |
| `分数表` | 查询歌曲分数排行榜 |
| `随机曲目` | 随机推荐一首曲目 |

### 🃏 卡牌 & 角色
| 命令 | 说明 |
|------|------|
| `查卡` | 根据关键词或卡牌 ID 查询卡片信息 |
| `查卡面` | 查询卡牌插画 / 原画 |
| `查角色` | 根据关键词或角色 ID 查询角色详情 |
| `抽卡模拟` | 模拟抽卡，试试手气 |

### 🏆 活动 & 档线
| 命令 | 说明 |
|------|------|
| `查活动` | 查询活动信息 |
| `查卡池` | 查询卡池详情 |
| `查试炼` | 查询活动试炼舞台信息 |
| `ycx` | 查询指定档位预测线 |
| `ycxall` | 查询所有档位预测线 |
| `lsycx` | 查询历史档线数据 |

### 🚗 车牌管理
| 命令 | 说明 |
|------|------|
| `车牌列表` | 获取所有车牌 |
| `开启车牌转发` | 开启后，发送的车牌自动提交到公共频道 |
| `关闭车牌转发` | 关闭车牌转发功能 |

### 👤 玩家数据
| 命令 | 说明 |
|------|------|
| `玩家绑定` | 开始玩家数据绑定流程 |
| `绑定` | 发送 `绑定<玩家ID>` 完成验证 |
| `取消绑定` | 取消正在进行的绑定流程 |
| `解除绑定` | 解除玩家绑定 |
| `玩家状态` | 查询自己的玩家状态 |
| `绑定列表` | 查看已绑定玩家列表 |
| `查玩家` | 查询其他玩家的信息 |
| `选择绑定` | 切换默认使用的绑定玩家 |
| `主服务器` | 设置主服务器 |
| `显示服务器` | 设置默认显示的服务器列表 |

---

## 📥 安装

### 方式一：AstrBot 插件市场

在 AstrBot Dashboard → 插件管理 → 搜索 `astrbot_plugin_tsugu` → 一键安装

### 方式二：手动安装

```bash
# 1. 克隆到插件目录
cd AstrBot/data/plugins/
git clone https://github.com/buruqu/astrbot_plugin_tsugu.git

# 2. 安装依赖
pip install tsugu-api-python httpx

# 3. 重启 AstrBot
# 或在 Dashboard 中重新加载插件
```

---

## 🚀 使用示例

### 曲目 & 卡牌查询
```
查曲 1                    查曲 ag lv27
查卡 1399                 查卡 绿 tsugu
查卡面 1399               查角色 10
查谱面 1                  查谱面 1 expert
分数表                    分数表 cn
随机曲目                  随机曲目 27
```

### 活动 & 档线
```
查活动 177                查卡池 922
查试炼                    查试炼 157 -m
ycx 1000                  ycx 1000 177 jp
ycxall                    lsycx 1000
抽卡模拟                  抽卡模拟 300 922
```

### 车牌管理
```
车牌列表
开启车牌转发              关闭车牌转发
```

### 玩家绑定 & 数据
```
玩家绑定                  玩家绑定 cn
绑定 10000000             取消绑定
解除绑定                  解除绑定 jp
玩家状态                  玩家状态 jp
绑定列表                  查玩家 40474621 jp
主服务器 日服              主服务器 cn
显示服务器 国服 日服        显示服务器
选择绑定 1
```

---

## ⚙️ 配置项

所有配置在 AstrBot Dashboard 插件面板中操作，无需编辑配置文件：

### 基础配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| Tsugu 后端地址 | API 服务器地址 | `http://tsugubot.com:8080` |
| 用户数据后端地址 | 用户数据服务器 | — |
| 代理地址 | HTTP 代理（内网用） | — |
| 简易背景 | 压缩图片加速响应 | 关 |
| 压缩返回数据 | 减少传输数据量 | 关 |

### v1.3.0 新增

| 配置项 | 说明 |
|--------|------|
| 📋 白名单模式 | 仅白名单群号可用（私聊不受限） |
| 📋 白名单群号 | WebUI 标签列表，直接添加/删除群号 |
| 🔤 命令别名 | JSON 格式，如 `{"ycm":"车牌列表"}` |
| 📣 @唤醒开关 | 开启后需 @bot 或带前缀才回复 |
| ⌨️ 唤醒前缀 | 自定义前缀，如 `/` 或 `!` |
| 👤 回复@发送人 | 在回复中 @ 触发用户 |
| 💬 回复引用原消息 | 引用发送人的原始消息 |

---

## 🏗️ 技术架构

```
┌──────────────┐     AstrBot Event      ┌─────────────────────┐
│  QQ / 微信    │ ──────────────────────▶│  @filter.regex()    │
│  / 其他平台   │                        │  正则匹配 26 条命令   │
└──────────────┘                        └──────────┬──────────┘
                                                   │
                                          ┌────────▼──────────┐
                                          │   _precheck()     │
                                          │   白名单 / @唤醒   │
                                          └────────┬──────────┘
                                                   │
┌──────────────────┐                       ┌───────▼──────────┐
│  Tsugu Backend   │◀──── tsugu_api_async ─│  Command Handler │
│  (bestdori.com)  │──── 返回 JSON ────────▶│  数据转换 & 回复  │
└──────────────────┘                       └──────────────────┘
```

### 核心设计

| 特性 | 实现方式 |
|------|----------|
| **全 Regex 方案** | 所有命令统一使用 `@filter.regex()`，非 `@filter.command()` |
| **@唤醒统一控制** | 在 `_precheck()` 中集中检查，对全部命令生效 |
| **命令别名注入** | `initialize()` 中动态修改 `RegexFilter.pattern` |
| **唤醒前缀注入** | 可选前缀 `(?:前缀)?` 注入到所有 regex pattern |
| **车牌自动转发** | Regex 拦截纯数字+星级消息，调用 `station_submit_room_number` |
| **配置 fallback** | 用户配置为空时自动使用内置默认值 |

### API 调用链

```
用户消息
   │
   ├─ 正则匹配 (@filter.regex)
   │    └─ command_alias 动态注入
   │
   ├─ 前置检查 (_precheck)
   │    ├─ 白名单检查
   │    ├─ @唤醒检查 (可选)
   │    └─ 前缀检查 (自定义前缀)
   │
   ├─ 参数解析 (基于 AstrBot event.message_str)
   │    └─ _cmd_args() 去掉命令名，获取纯参数
   │
   ├─ API 调用 (tsugu_api_async)
   │    ├─ search_song / search_card / search_event ...
   │    ├─ bind_player / change_user_data ...
   │    └─ station_submit_room_number
   │
   └─ 响应转换 (Tsugu _Response → AstrBot MessageChain)
        ├─ type=string → Plain
        └─ type=base64  → Image
```

---

## 🌍 服务器支持

| 服务器 | 中文名 | 简称 | ID |
|--------|--------|------|----|
| JP | 日服 | `jp` | 0 |
| EN | 国际服 | `en` | 1 |
| TW | 台服 | `tw` | 2 |
| CN | 国服 | `cn` | 3 |
| KR | 韩服 | `kr` | 4 |

命令中可通过中文名、简称或 ID 指定服务器，不指定则使用默认服务器。

---

## 📦 依赖

| 包名 | 版本 | 说明 |
|------|------|------|
| [tsugu-api-python](https://pypi.org/project/tsugu-api-python/) | >= 1.5.0 | Tsugu API 异步调用库 |
| [httpx](https://pypi.org/project/httpx/) | * | HTTP 客户端 |
| AstrBot | v4+ | AstrBot 机器人框架 |

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

---

## 🙏 致谢

本项目的实现离不开以下开源项目：

| 项目 | 作者 | 说明 |
|------|------|------|
| 🎸 [TsuguBanGDreamBot](https://github.com/Yamamoto-2/tsugu-bangdream-bot) | Yamamoto-2 | 原版 Bot（TypeScript），一切功能的源头 |
| 🔌 [nonebot-plugin-tsugu-bangdream-bot](https://github.com/WindowsSov8forUs/nonebot-plugin-tsugu-bangdream-bot) | WindowsSov8forUs | NoneBot2 适配版，本插件的直接参考 |
| 📚 [tsugu-api-python](https://github.com/WindowsSov8forUs/tsugu-api-python) | WindowsSov8forUs | Python API 库，封装所有 Tsugu 后端调用 |
| 🤖 [AstrBot](https://github.com/Soulter/AstrBot) | Soulter | 模块化 LLM 机器人框架 |
| 🎵 [Bestdori](https://bestdori.com) | — | BanG Dream! 数据来源 |
| 🎸 [BanG Dream!](https://bang-dream.bushiroad.co.jp/) | Bushiroad / Craft Egg | 少女乐团派对！|

---

<p align="center">
  <sub>Made with ❤️ by <a href="https://github.com/buruqu">buruqu</a> · Powered by <a href="https://github.com/Soulter/AstrBot">AstrBot</a></sub>
</p>

---

<div align="center">

**⭐ 如果这个插件对你有帮助，点颗 Star 吧！**

[![Star History Chart](https://api.star-history.com/svg?repos=buruqu/astrbot_plugin_tsugu&type=date)](https://star-history.com/#buruqu/astrbot_plugin_tsugu&date)

</div>

# astrbot_plugin_tsugu

BanG Dream! 游戏助手插件，基于 [tsugu-api-python](https://github.com/WindowsSov8forUs/tsugu-api-python)，为 AstrBot 提供 BanG Dream! 少女乐团派对 游戏查询功能。

## 功能一览

| 命令 | 说明 |
|------|------|
| 查曲 | 根据关键词或曲目ID查询曲目信息 |
| 查卡 | 根据关键词或卡牌ID查询卡片信息 |
| 查卡面 | 根据卡片ID查询卡片插画 |
| 查角色 | 根据关键词或角色ID查询角色信息 |
| 查活动 | 根据关键词或活动ID查询活动信息 |
| 查卡池 | 根据卡池ID查询卡池信息 |
| 抽卡模拟 | 模拟抽卡（默认10次） |
| 查谱面 | 查询曲目谱面信息（可指定难度） |
| 分数表 | 查询指定服务器的歌曲分数表 |
| 查试炼 | 查询当前活动试炼信息 |
| ycx | 查询指定档位预测线 |
| ycxall | 查询所有档位预测线 |
| lsycx | 查询历史档线数据 |
| 车牌列表 | 获取所有车牌 |
| 开启车牌转发 | 开启后发送的车牌会被提交到公共频道 |
| 关闭车牌转发 | 关闭车牌转发功能 |
| 查玩家 | 查询指定玩家信息 |
| 玩家绑定 | 绑定游戏玩家数据 |
| 绑定 | 完成绑定验证（绑定流程中发送 绑定<玩家ID>） |
| 取消绑定 | 取消正在进行的绑定流程 |
| 解除绑定 | 解除玩家绑定 |
| 玩家状态 | 查询自己的玩家状态 |
| 绑定列表 | 查看已绑定玩家列表 |
| 主服务器 | 设置主服务器 |
| 显示服务器 | 设置默认显示的服务器列表 |
| 选择绑定 | 切换默认使用的绑定玩家 |
| 随机曲目 | 随机一首曲目 |

## 使用示例

### 车牌转发
```
车牌列表
开启车牌转发
关闭车牌转发
```

### 查询功能
```
查曲 1
查曲 ag lv27
查卡 1399
查卡 绿 tsugu
查卡面 1399
查角色 10
查活动 177
查卡池 922
抽卡模拟
抽卡模拟 300 922
查谱面 1
查谱面 1 expert
分数表
分数表 cn
查试炼
查试炼 157 -m
ycx 1000
ycx 1000 177 jp
ycxall
lsycx 1000
车牌列表
查玩家 10000000
查玩家 40474621 jp
随机曲目
随机曲目 27
```

### 玩家绑定
```
玩家绑定
玩家绑定 cn
绑定 10000000        <- 在绑定流程中发送，完成验证
取消绑定             <- 取消当前绑定流程
解除绑定
解除绑定 jp
```

### 数据设置
```
绑定列表
玩家状态
玩家状态 jp
主服务器 日服
主服务器 cn
显示服务器 国服 日服
显示服务器            <- 查看当前设置
选择绑定 1
```

## 服务器名称

支持以下格式指定服务器：

| 服务器 | 简称 | ID |
|--------|------|----|
| 日服 | jp | 0 |
| 国际服 | en | 1 |
| 台服 | tw | 2 |
| 国服 | cn | 3 |
| 韩服 | kr | 4 |

## 配置项

在 AstrBot Dashboard 插件配置页面可设置：

### 基础配置
- **Tsugu 后端地址**: Tsugu API 后端服务器地址（默认官方后端 http://tsugubot.com:8080）
- **用户数据后端地址**: 用户数据后端地址
- **代理地址**: HTTP 代理（留空不使用）
- **简易背景**: 降低图片质量加快响应
- **压缩返回数据**: 减少传输数据量

### v1.3.0 新增配置
- **白名单模式** (`whitelist_enabled`): 启用后仅白名单群可使用插件，私聊不受限制。默认关闭。
- **白名单群号** (`whitelist_groups`): WebUI 标签列表形式，直接添加/删除群号。旧版逗号分隔字符串配置仍兼容。
- **命令别名** (`command_aliases`): JSON 格式的别名映射，如 `{"ycm":"车牌列表"}`（键为别名，值为原命令名）。插件初始化时会将别名动态注入到对应命令的 RegexFilter 正则表达式中。
- **@唤醒开关** (`at_wake_enabled`): 启用时需 @bot 或使用唤醒前缀才回复（默认启用）。关闭时不需 @bot 即可触发命令。
- **唤醒前缀** (`wake_prefix`): 自定义唤醒前缀，如 `/` 或 `!`。配置后发送 `前缀+命令名` 即可触发命令。留空则只使用 AstrBot 全局唤醒前缀。
- **回复@发送人** (`at_sender_enabled`): 启用时回复消息会 @发送人。默认关闭。
- **回复引用原消息** (`quote_reply_enabled`): 启用时回复消息会引用发送人的原始消息。默认关闭。

### 技术实现说明
- 所有命令使用 `@filter.regex()` 实现（非 `@filter.command()`），使 @唤醒开关能统一控制所有命令
- 命令别名通过动态修改 `RegexFilter.pattern` 实现，支持多个命令名/别名共享同一个 handler
- 白名单 `whitelist_groups` 配置项类型为 `list`（WebUI 标签列表），同时兼容旧版逗号分隔字符串

## 依赖

- `tsugu-api-python` >= 1.5.0
- `httpx`

## 安装

1. 将 `astrbot_plugin_tsugu` 文件夹放入 AstrBot 的 `data/plugins/` 目录
2. 在 AstrBot Dashboard 中启用插件
3. 安装依赖（如未自动安装）：
   ```
   pip install tsugu-api-python httpx
   ```
4. 在插件配置页面设置后端地址（可选）

## 致谢

- [tsugu-api-python](https://github.com/WindowsSov8forUs/tsugu-api-python) - Tsugu BanG Dream API Python 库
- [nonebot-plugin-tsugu-bangdream-bot](https://github.com/WindowsSov8forUs/nonebot-plugin-tsugu-bangdream-bot) - Nonebot 版本参考
- [TsuguBanGDreamBot](https://github.com/Yamamoto-2/tsugu-bangdream-bot) - Tsugu 后端

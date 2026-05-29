# 更新日志归档

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

## 🆕 v1.3.0 更新日志

### ✨ 新增功能
- 车牌转发功能（`开启车牌转发` / `关闭车牌转发`）
- `@唤醒开关` 配置项（控制是否需要 @bot 才回复）
- 回复@发送人开关（配置项 `at_sender_enabled`）
- 回复引用原消息开关（配置项 `quote_reply_enabled`）
- 唤醒前缀配置（配置项 `wake_prefix`，支持自定义前缀触发）

### 🐛 问题修复
- 修复 `CommandFilter.filter()` 不修改 `event.message_str` 导致参数解析错误
- 修复 `MessageChain` 访问方式（`chain` 属性，不是 `message_chain`）
- 修复 `RegexFilter.filter()` 不设置 `parsed_params` 导致正则参数无法传递

### ⚡ 优化改进
- 新增 `_cmd_args()` 辅助方法，自动去掉命令名获取纯参数
- 命令别名支持运行时动态修改（`_set_filter_aliases()`）
- 完善 `response_to_chain()` 支持 `base64` 类型图片响应

---

## 🆕 v1.2.0 更新日志

### ✨ 新增功能
- 抽卡模拟功能（`抽卡 <卡池名>`）
- 随机曲目推荐（`随机曲目`）
- 主服务器设置（`主服务器 <服务器>`）
- 显示服务器配置（`显示服务器 <服务器...>`）

### 🐛 问题修复
- 修复 `server_name_to_id()` 大小写敏感问题
- 修复 `userPlayerIndex` 索引越界问题

### ⚡ 优化改进
- 优化 `response_to_chain()` 对 Tsugu API 多类型响应的处理
- 完善错误提示信息

---

## 🆕 v1.1.0 更新日志

### ✨ 新增功能
- 玩家绑定功能（`玩家绑定` / `解除绑定` / `绑定列表` / `玩家状态`）
- 白名单模式（`whitelist_enabled` / `whitelist_groups`）
- 多服务器支持（jp / en / tw / cn / kr）

### 🐛 问题修复
- 修复绑定流程验证码校验逻辑
- 修复 `_get_user_player()` 服务器匹配问题

### ⚡ 优化改进
- 重构 `TsuguClient` 为直接调用 `tsugu_api_async` 函数
- 优化错误消息展示

---

## 🆕 v1.0.0 初始版本

### ✨ 核心功能
- 查曲 / 查卡 / 查卡面 / 查角色 / 查活动 / 查卡池
- 查谱面 / 分数表 / 查试炼
- 档线查询（ycx / ycxall / lsycx）
- 车牌系统（车牌列表 / 智能识别）
- 基于 AstrBot Star 框架
- 基于 tsugu-api-python 异步库

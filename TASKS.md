# Trace 任务板 (TASKS.md)

状态：`[ ]` 待办 · `[~]` 进行中 · `[?]` 待审 · `[x]` 完成。开工前改 `[~]`；`python -m pytest -q` 和 `cd web && npm run build` 都过了才改 `[?]`。

| 编号 | 任务 | 负责 | 状态 | 说明 |
| --- | --- | --- | --- | --- |
| T-01 | 安全检查 + 首次推 GitHub，看 CRACI 跑 | Diletta | [ ] | 全部历史已扫过，无 key（AIza / nvapi- / sk-） |
| T-02 | 视觉/复核 API 磁盘缓存 | Claude | [?] | `agent/vision.py` `cached_call`：图片 SHA256 + prompt + model；存 `cache/vision/`；结果带 `cached` |
| T-03 | 模块 1：全构件识别编号 | Claude | [?] | 工具 `scan_drawing_inventory` + `GET /inventory`；无 key 时返回 `mock/inventory.json` 并标 MOCK DATA |
| T-04 | 缓存/清单/契约单测 | Claude（代 Codex） | [?] | `tests/test_inventory_and_cache.py`，共 23 个测试全过；CI 文件未改 |
| T-05 | 模块 2：分层目录树 | Claude | [?] | `web/src/components/SpaceTree.tsx` |
| T-06 | 模块 3&4：房间状态 + Room Board | Claude | [?] | `web/src/components/RoomCollabPanel.tsx`；改动只闪烁该房间的框 |
| T-07 | 数据源署名 + IFC 实测 | Claude / Diletta | [~] | `LicenseBadge.tsx` 只写来源名，许可证文字要按数据集 LICENSE 补；真实 IFC 加载需在本机测 |
| T-08 | 后端 collab 接口 + 角色 | Claude | [?] | `agent/collab.py`，`/collab*`；角色加 plumber、owner |
| T-09 | 前端总装 + Nemotron 徽章 | Claude | [?] | `App.tsx`、`DrawingViewer.tsx`、`VerifyBadge.tsx`；`npm run build` 通过 |
| T-10 | 接 Xinran 的 engine.tools | Diletta + Xinran | [ ] | `agent/tools.py` 已按 `engine.tools` 自动切换 |
| T-11 | Verda 批处理 + Dockerfile + 部署 | Codex / Diletta | [?] | 预热脚本完成；pytest 23 passed，前端 build 通过；Verda 部署仍待确认 |
| T-12 | README 各 Tech Challenge + verda-log | Codex | [?] | 文档完成；pytest 23 passed，前端 build 通过 |
| T-13 | Codex 真实提交（Codex 挑战证据） | Codex | [ ] | 上面的 T-04 是 Claude 写的，Codex 挑战需要 Codex 自己做 T-11/T-12 |

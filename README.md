# 古今人物锐评｜规范与新电脑接续

本仓库只保存PRD、项目方向、接续说明和通用资产，当前 **PRD V7.4**。选题调研、论点、口播、分镜、单集制作记录和成品全部存本地，不因定稿而上传，不为普通改稿创建Git提交。

## 先选择执行入口

- **老电脑继续制作（默认）**：只读取本地PRD、相关spec、本期定稿与制作记录，复用已有素材。不访问GitHub，不clone／fetch／pull，不检查远端版本或登录。新会话、新选题、新集数不触发同步；缺件先查本地并继续独立工作，见PRD 13.1.1。
- **新电脑首次初始化**：才执行下面的克隆／同步步骤，完成一次后切换本地续作。已有完整可用本地资料时不重复初始化。
- **规范更新**：用户明确要求同步或调整规范／接续时，独立执行PRD 13.1.2；普通单集制作不附带此任务。

## 新电脑首次初始化

```powershell
git clone https://github.com/KAtOReNA7/tiktok.git
cd tiktok
```

仅在首次初始化或明确的规范更新任务中，已有克隆先核对remote、分支和工作区；干净main可运行 `git pull --ff-only origin main`。有改动时按PRD第13.1节保留，不强制覆盖。

读取AGENTS.md、CHAT_HANDOFF.md、START_HERE.md、PRD_V7.md和PROJECT_STATE.md，然后按用户当前任务执行。武松已完成，不重做；待确认文案不自动生图。

## 仓库内容

| 文件／目录 | 用途 |
| --- | --- |
| CHAT_HANDOFF.md、START_HERE.md、AGENTS.md | 分开的首次初始化与老电脑续作入口 |
| PRD_V7.md | 唯一现行主规范V7.4 |
| PROJECT_STATE.md、CHANGELOG.md | 必要状态摘要、规范与方向变化 |
| spec/ | 通用模板、字幕与存放参数 |
| assets/、refs/ | 固定底板、身份原图和可复用参考 |
| episode/ | 空白制作模板，填写后的副本必须放本地 |
| tools/、manifest.json | 接续文件校验 |

本地工作根默认放在仓库旁的 `tiktok-local/`：`episodes/` 保存选题内容，`交付/` 保存用户使用的最终文件。已有用户指定目录则沿用。这里的本地文件不会随clone迁到新机器；仅在任务需要时补充，不能说仓库已备份。

2026-09-18已将原episodes/与旧archive/共14个文件完整保留到本地后，从main的当前文件树移除。普通删除提交保留Git历史，不重写历史。

## 规范更新

仅在用户明确的规范、项目方向或接续更新任务中维护仓库；不因为换对话或换集数检查更新。实际修改后运行：

```powershell
python tools/validate_handoff.py --refresh
python tools/validate_handoff.py
```

检查diff和文件清单，只提交规范／接续范围，正常推送并读回远端后报告提交号。不另制作接续压缩包。

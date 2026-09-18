# 古今人物锐评｜规范与新电脑接续

本仓库只保存PRD、项目方向、接续说明和通用资产，当前 **PRD V7.3**。选题调研、论点、口播、分镜、单集制作记录和成品全部存本地，不因定稿而上传，不为普通改稿创建Git提交。

## 新电脑开始

```powershell
git clone https://github.com/KAtOReNA7/tiktok.git
cd tiktok
```

已有克隆先核对remote、分支和工作区；干净main可运行 `git pull --ff-only origin main`。有改动时按PRD第13.1节保留，不强制覆盖。

读取AGENTS.md、CHAT_HANDOFF.md、START_HERE.md、PRD_V7.md和PROJECT_STATE.md，然后按用户当前任务执行。武松已完成，不重做；待确认文案不自动生图。

## 仓库内容

| 文件／目录 | 用途 |
| --- | --- |
| CHAT_HANDOFF.md、START_HERE.md、AGENTS.md | 新对话与新机器开工说明 |
| PRD_V7.md | 唯一现行主规范V7.3 |
| PROJECT_STATE.md、CHANGELOG.md | 必要状态摘要、规范与方向变化 |
| spec/ | 通用模板、字幕与存放参数 |
| assets/、refs/ | 固定底板、身份原图和可复用参考 |
| episode/ | 空白制作模板，填写后的副本必须放本地 |
| tools/、manifest.json | 接续文件校验 |

本地工作根默认放在仓库旁的 `tiktok-local/`：`episodes/` 保存选题内容，`交付/` 保存用户使用的最终文件。已有用户指定目录则沿用。这里的本地文件不会随clone迁到新机器；仅在任务需要时补充，不能说仓库已备份。

2026-09-18已将原episodes/与旧archive/共14个文件完整保留到本地后，从main的当前文件树移除。普通删除提交保留Git历史，不重写历史。

## 规范更新

仅规范、项目方向或必要接续摘要变化时更新仓库。运行：

```powershell
python tools/validate_handoff.py --refresh
python tools/validate_handoff.py
```

检查diff和文件清单，只提交规范／接续范围，正常推送并读回远端后报告提交号。不另制作接续压缩包。

# 从这里开始｜古今人物锐评 V7.2

新对话的沟通背景和可粘贴指令见 [CHAT_HANDOFF.md](CHAT_HANDOFF.md)。

当前唯一主PRD是PRD_V7.md，内部版本7.2；本次接续规则更新日期：2026-09-18。唯一接续仓库：https://github.com/KAtOReNA7/tiktok ，主分支main。以后直接更新仓库，不生成新的接续压缩包。

## 新电脑先同步

尚无仓库时执行 `git clone https://github.com/KAtOReNA7/tiktok.git`，用Codex打开生成的tiktok目录。已有仓库先检查remote、分支和工作区；干净main执行 `git pull --ff-only origin main`。有本地改动不强制覆盖，按PRD第13.1节保留并处理。

同步后读AGENTS.md、PRD_V7.md与PROJECT_STATE.md；记录提交号。可用 `python tools/validate_handoff.py` 校验模板和参考文件。武松已完成，商鞅仅为待确认提案，不自动启动。

## 本轮已经确定的交付规则

1. 不制作或提供音效、配乐、轻动效，包括相关建议和落点表。
2. 字幕默认实际黑底白字MP4，不能只交SRT。默认776×128、30fps、无音轨，对齐1080×1920模板x96/y1408黑框；具体见spec/caption_style.json。
3. 每集默认含片头片尾不超过40秒。分集默认独立开头和结尾；优秀且适用全部分集的片头可按选题共用，结尾仍逐集提供。
4. 每集一张同视频模板的1080×1920封面，漫画构图有张力，并提供一句话简介。
5. 最终素材统一放项目根交付/选题ID_短名/下，按集号分目录、按用途和版本命名，不压缩。
6. 素材映射表严格只有“插图编号、对应口播”两列，按口播顺序写完整定稿原文。图片文件名带同一编号。不要增加时间、文件路径、状态、备注等列，也不预留空列；配音完成后仍保持两列，字幕时码单独处理。

## 开始执行

读取PRD_V7.md、spec/template.json、spec/caption_style.json；实际查看refs/identity/doro_primary_user.png、refs/layout/和refs/comic_language/。参考的用途见refs/README.md。

已有定稿就直接准备分镜与实际素材；只有选题先做40秒内分集稿；还无选题则先提约6个候选。不要自动继续秦始皇旧补修，不重跑A/B或GUI整片流程。用户负责剪映配音和装配，Codex负责素材、字幕、封面和简介。

episode/提供空白brief、分集清单和CSV字段；scene_map.csv固定只有“插图编号、对应口播”两列。按实际本期填写，未收到最终人声不能编字幕时码。共用片头时在brief和分集表记录共同文件，避免重复制作。

## 资产位置

- assets/template/：固定底板，放漫画下方。
- assets/hosts_qin_reference/：已有秦装边缘角色与透明叠加层；新题按本期cos替换。
- refs/identity/：Doro用户原图；refs/layout/只参考版式；refs/comic_language/只参考漫画表现。
- spec/：当前布局、黑底字幕和文件夹交付参数。
- archive/：原始归档记录，不作为现行任务。

本仓库含现有接续资产、武松定稿与审核记录、商鞅待确认提案；不含用户最新剪映工程、最终独立人声、成片或下一选题新素材。需要时由用户补充，先完成可独立推进的部分。

Figma资产页：https://www.figma.com/design/gc9VEwuG01X8ZsMTHg7HsQ?node-id=50-2 。母版50:60，制作副本50:4；本轮未改远端Figma。


## 做完之后

已确认的规范修改直接回写PRD和关联spec／模板，当前任务进度更新PROJECT_STATE.md，通用变化记CHANGELOG.md。刷新manifest并校验后，只提交本轮相关文件并正常push；远端读回成功再报告提交号。详细流程见PRD第13.1.1节。不要另建长期生效的接续补丁包。

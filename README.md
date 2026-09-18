# 古今人物锐评｜制作与新电脑接续

这里是本项目的统一接续仓库。当前 **PRD V7.2**，保留V7.1制作规范，新增GitHub同步流程。后续直接维护这里，不再逐次发送接续压缩包。

## 新电脑开始

在希望保存项目的父目录运行：

```powershell
git clone https://github.com/KAtOReNA7/tiktok.git
cd tiktok
```

然后用Codex打开这个目录，发送：

```text
先安全同步本仓库main分支，读取AGENTS.md、START_HERE.md、PRD_V7.md和PROJECT_STATE.md，检查已有模板和角色参考图。按我本次明确任务执行。不要重跑已完成的武松，也不要把商鞅待确认提案当成制作定稿。后续已确认的规范和接续更新直接提交到这个仓库，给我提交号，不再另做接续压缩包。
```

已有克隆的电脑先检查 `git status --short` 和当前分支。工作区干净且位于main时执行 `git pull --ff-only origin main`。存在本地改动时按PRD第13.1节保留并处理，不强制覆盖。

## 从哪里读

| 文件／目录 | 用途 |
| --- | --- |
| [START_HERE.md](START_HERE.md) | 开工顺序及当前交付规则 |
| [PRD_V7.md](PRD_V7.md) | 唯一现行主PRD，内部版本V7.2 |
| [PROJECT_STATE.md](PROJECT_STATE.md) | 已完成事项、待确认选题、下一步 |
| [CHANGELOG.md](CHANGELOG.md) | 规范与接续更新记录 |
| [spec/](spec/) | 模板、黑底字幕、交付字段 |
| [assets/](assets/) | 实际底板和已有透明角色图 |
| [refs/](refs/) | Doro身份原图、版式和漫画参考 |
| [episode/](episode/) | 新一期的空白制作模板 |
| [episodes/](episodes/) | 各选题文稿、两列映射和审片记录 |

图像资产随Git一起取得，无需找回聊天附件。仓库没有用户最新剪映工程、武松成片或最终独立配音。新生成素材默认交到本地 `交付/` 文件夹，该目录不自动进入Git。

## 校验与后续更新

克隆后可运行 `python tools/validate_handoff.py`；Windows也可运行 `py -3 tools/validate_handoff.py`。它检查清单哈希、PNG和两列素材映射模板。

规范更新后，刷新并核对清单：

```powershell
python tools/validate_handoff.py --refresh
python tools/validate_handoff.py
```

检查改动、只暂存本次文件、正常提交并推送。协作冲突和分支保护按PRD第13.1.1节处理。每次交付回报提交号，不能把“本地已改”当成“远端已同步”。


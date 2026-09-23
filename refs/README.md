# 参考图的职责

## 身份
- identity/doro_primary_user.png：用户原图，身份第一依据，每次含Doro生图实际输入。
- identity/doro_expression_user.png：只看右下角粉发Doro；领奖台上三位不是本项目Doro参考。
- 咕咕嘎嘎、曼波目前可用的身份／动作图在assets/hosts_qin_reference。未附不存在的更原始角色图。

现行三位身份清单见 `spec/character_identity.json`：咕咕嘎嘎用 `assets/hosts_qin_reference/gugu_qin_edge.png`，曼波用 `assets/hosts_qin_reference/mambo_qin_edge.png`，Doro用上述用户原图。每次生图／编辑必须实际输入每位出镜演员对应的图，文件名或文字描述不能代替真实参考。

三位本人都保持Q版脸与身体演故事。秦装参考用来锁定演员特征、脸型和Q版观感，不要求新题沿用秦装，也不把裁切的边缘图冒称完整全身原设定。咕咕嘎嘎保留黑发、大灰黑眼、企鹅兜帽与黄色喙；曼波保留栗棕发、蓝花、马耳、琥珀大眼与圆脸；Doro保留粉发紫眼及白色短肢团状身体。具体判定仍须查看实际图片，不以文本清单代替。

角色长袍／武器／古风画风不能改变其骨架或使其成年男性化；问题图不能作为身份母图。角色分配、内部定妆检查与逐图验收按PRD第6节执行，不要求用户单独确认角色形象。

## 版式
- layout/V1_1_layout_only.png：已归档白底单格模板。仅参考布局，内含旧湘山Doro，不能作为脸型母图。
- layout/EP01_V5_human_edit.png：用户第五版第1.1集的实际帧，参考边缘角色与字幕呈现。它是截图，不是可编辑模板，不能直接抹字当新题底板。

## 漫画语言
四张均为第五版视频的整帧截图，不是独立原始插画：
- meteor_closeup_reference.png：第1.1集约8秒；石刻特写，文字进入材质。
- axe_action_reference.png：第1.2集约9.4秒；斜向动作、近景斧头、拟声词。
- weilio_reaction_reference.png：第1.1集约35.9秒；前景回望与远处虎狼投影、内心气泡。
- liuzongyuan_writing_reference.png：第1.3集约46.4秒；执笔落字近景，与文人托腮图区别。

这些图只用于镜头、动作和材质学习；其中旧章节号、字幕、题目不搬入新选题。特别是1.3截图的角色外层存在已知裁切问题，只参考漫画画窗。最终身份仍以用户原图为准。

当前包不包含这些镜头全部独立重绘原图，不把从视频截出的参考帧冒称可直接替换的生成素材。

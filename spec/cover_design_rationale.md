# 双比例发布封面 V3：纸白母版与使用边界

生效：2026-10-10。当前 `COVER_DUAL_RATIO_FIXED_V3`，修订 `3.0.0`。

用户已要求封面配色与视频正文一致。新封面使用纸白 #FAFAFA、墨黑标题 #161616、荧光黄强调 #F2FA00。V2 黑底白字只能由对比度说明可读性，不能证明有更好的抖音传播。V3 是一致性、缩略图识读与具体事件清晰度的设计选择，不能承诺提高流量。

Figma 源：文件 gc9VEwuG01X8ZsMTHg7HsQ，组件集 147:261，页面 132:2，复核板 148:193。3:4：master 147:262、base 147:263、hosts 147:281、blank 147:311、title 147:271、art 147:270；4:3：master 147:285、base 147:286、hosts 147:301、blank 147:323、title 147:294、art 147:293。

四份 PNG 是本次 Figma 实际导出的精确分层文件。SVG 为这些真实导出层加固定图窗及可编辑标题节点的本地装配母版，不能冒称已取得原生 Figma SVG。准确标题仍由 cover_job.json 和固定字体经 render_cover.py 合成。

几何、字体、92px/104px、144px 三位固定装饰、朱印和双比例尺寸保持；只更换批准的本集故事图、标题无损换行与一至两个强调行。核心被评价人物继续由原Q版 Doro 实际出演；固定页边 Doro 不能代替故事主角。常规制作直接复用本地发布包，不每集访问 Figma。

一张封面表达一件事，人物、动作、受影响对象在实际180/360px缩略图中清楚；两比例可以使用同集不同构图。保留现行 contain 投影面积85%试行复核提示，这不是平台／科学阈值，不能替代实际审片。宫廷占位图只用于版式测试，不纳入新单集交付。

依据仅支持可读性与设计取舍：
- W3C：https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum
- Dobres 等，Displays 41 (2016)，DOI 10.1016/j.displa.2015.12.001：https://jdobr.es/pdf/Dobres-etal-2016-Displays.pdf
- 抖音创建视频接口：https://developer.open-douyin.com/docs/resource/zh-CN/dop/develop/openapi/video-management/douyin/create-video/video-create

上述研究不能证明某种底色提高抖音点击；此前账号样本观察不能充当因果实验。封面效果应按主页／搜索等相同选择入口核实曝光与点击；没有曝光分母不编CTR，不把推荐流完播直接归因封面配色。

旧V2规范及资产保留历史兼容，已完成作品不重做；正文RYP_STORY_MAIN_V3_2／3.2.1、STATIC_CAPTION_PAGES_V1、40秒、1.25倍速、两列保真CSV及独立运营授权边界继续生效。

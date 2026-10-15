# 按当前项目找能用的参考

先从服务端读取当前能力与覆盖：`find_references.py --options`。下面的路径都位于 Skill 的 `scripts/`，使用安装配置里的 Python。新页级索引只覆盖已提取的文字、描述、页图与编辑参考单元；目录可查不等于正文和视觉已读完。

## 1. 形成有出处的需求单

阅读成员指定项目目录中的标书、产品资料、甲方要求、定位及其他必要附件，逐文件记录已读范围、读取失败及图表缺口。沿用 `prepare_project.py` 清单与分块，再由当前智能体完成理解；提取成功不是阅读完成。

需求单记录：项目事实与产品证据、当前业务阻力、希望改变的认知/行为、目标人群的原文描述、此次交付物、品牌与视觉要求、预算排期、硬性限制、可选偏好、缺失和冲突。每项保留原文件与页/条款。当前项目是住宅并不自动要求所有方法参考都来自住宅；但用户显式选择的业态、客群等筛选条件必须保留。

## 2. 按用途分开检索

| 目的 | material_roles / --role |
|---|---|
| 找真实项目的提案思路 | project_proposal |
| 学习方法、课程与知识点 | learning_material |
| 找能填写或执行的流程/表格 | execution_tool |
| 找海报、风格与视觉表达 | visual_reference；方案内画面可同时选project_proposal |
| 查AI生产工具与技能 | tool_guide |
| 查集锦或合集 | reference_collection |

同一维度多个值是OR，不同维度是AND。用途来自已复核单元、明确标题或既有分类，返回的 `classification_basis` 会说明依据。一个资料可以有多个用途；课程里的案例保持教学上下文。历史提案与执行效果分别判断。

对每个业务问题生成2—4个短查询，并逐个执行。空格分开的词必须同时出现，句子过长通常会漏检。查询由当前智能体理解问题后拟定，NAS不会自动推理Brief。

示例：

```sh
python scripts/find_references.py --role project_proposal --query '区域 认知' --limit 5
python scripts/find_references.py --role learning_material --query '销售 培训' --limit 5
python scripts/find_references.py --role project_proposal --role visual_reference --query '园林 生活' --require-image --limit 5
python scripts/find_references.py --role execution_tool --collection livestreams --query '线索' --limit 5
```

这里的python只是示意，实际使用安装配置中已验证的解释器。不要把示例查询当作全库固定标签。零结果时先检查查询词与用途；不得静默删除用户的硬筛选。需要跨行业方法迁移时单列，并明确与原筛选的关系。

新页级索引没命中时，可以用旧脚本 `query_cases.py` 搜原素材目录。目录结果是补查线索，引用前需要读取原件；它不能证明内部文字、画面或方法已经提取。

## 3. 回读原文与原图

从 `evidence_units` 取原页码/原段号：

```sh
python scripts/find_references.py --case-id <返回的资产ID> --page <命中编号> --radius 1
```

返回命中单元及前后单元、原文、图片URL和原件URL。章节或段编号不等于排版页。视觉参考必须通过宿主看图能力实际打开图片；只能读取文字时，明确尚未完成视觉判断。没有图像就不能从目录名补写色彩、构图或视觉方法。

分别核对原图文字、可见画面与传播解释。原生文字也可能存在字体编码问题；`unreviewed`/`unproofread` OCR必须回看。图里写了“中心”不证明实际区位中心，“轻奢”不证明改善客群；大字不自动等于文字图形化。一个画面没有活动流程与机制，不能据此当作完整活动策划。

全文分数只衡量字词命中，不是适配概率；`ranking_truncated`为true表示候选排序扫描有上限，拆分查询或收窄范围后继续，不能声称穷尽全库。

## 4. 形成可判断的参考包

围绕需求组织3—5项候选：需求及出处、原资料面对的问题、能借鉴的方法或画面、原页证据、当前项目条件差异、待确认事项。合并同项目近似版本，保留不同文件来源。原资料没有执行或效果证据就不写成功、有效或已落地。

用已有 `fetch_references.py` 获取选定原件和页图，返回当前会话。能否显示图片/附件以客户端实际结果为准；无法显示时给内网链接和文件位置。仅读取与当前任务相关的资料，不把整库下载或批量发送到额外外部服务。

## HTTP / MCP 入口

更新后的MCP提供 `search_references` 和 `read_reference_context`。没有MCP时使用上述脚本。需要直接调用时：

- `GET /api/reference-options`：当前用途、覆盖和服务端流程。
- `POST /api/references/search`：`query`、`material_roles`、现有业态/客群/出品等维度、`collection`、`require_image`、`limit`、`offset`。只读，不上传Brief。
- `POST /api/references/read`：`asset_id`、`page`、`radius`。只读，不修改原件。

新接口保持公司内网的访问边界。后端索引更新后下次请求即可读取；新增文件尚未处理时不会自动获得正文与图像理解。

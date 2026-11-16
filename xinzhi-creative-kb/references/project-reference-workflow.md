# 按当前项目找能用的参考（v1.5 主流程）

主流程：**读 Brief → 填需求单（先对应难题和阶段，再拟短查询）→ 一次调用 → 读命中页 → 给 3–5 个候选**。

先从服务端读取当前枚举、一句释义与覆盖统计：`python scripts/find_by_brief.py --options`。下面的路径均位于 Skill 的 `scripts/`，使用安装配置里的 Python。页级索引覆盖已提取的文字、描述、页图与编辑参考单元；NAS 不运行大模型，由当前智能体理解 Brief 并判断适配性。

## 1. 读 Brief 并整理有出处的需求单

阅读成员指定项目目录中的标书、产品资料、甲方要求、定位及其他必要附件（可用 `prepare_project.py` 形成逐文件清单与全文分块），逐文件记录已读范围与图表缺口。

从 Brief 提取并区分两类条件：
- **业务命题（填入 `needs` 数组）**：每项需求先对应服务端的 `problems`（业务难题枚举）和目标 `page_types`（页面类型枚举），声明 `task`（`strategy` 策略破局 / `positioning` 定位与案名 / `campaign` 节点传播与活动 / `visual` 主画面与海报视觉），再拟定 `1–4` 个短查询 `queries`（每个查询 2–4 个核心词，空格分隔）。
- **软偏好 vs 硬条件**：项目自身的业态、阶段、客群、偏向近期默认填入 `prefer`（只用于加分并在结果 `preference_notes` 标明“相同/不同”，不过滤）；只有用户明确要求“只看某业态/某城市/某年份之后/某客群”时，才填入顶层硬条件 `industry`、`cities`、`stages`、`year_from`、`audience`。

需求单 JSON 示例（可保存为工作目录下的 `brief_request.json`）：

```json
{
  "needs": [
    {
      "label": "新兴片区首开区域认知破局策略",
      "task": "strategy",
      "problems": ["区域认知弱", "首开蓄客"],
      "queries": ["区域 认知 首开", "新兴 片区 占位", "板块 价值 破局"],
      "page_types": ["市场、区域与政策", "客群研究"]
    },
    {
      "label": "湖景改善项目主画面KV参考",
      "task": "visual",
      "queries": ["湖景 主画面", "滨水 雅致 海报"],
      "page_types": ["视觉表达"],
      "require_image": true
    }
  ],
  "prefer": {
    "industry": "住宅",
    "stages": ["首开"],
    "audience": ["改善"],
    "recent": true
  },
  "collection": "cases",
  "limit_per_need": 5
}
```

## 2. 一次调用检索（及同项目拓展）

提交结构化需求单，一次调用完成多路召回、同项目与同版本族合并去重，整体返回控制在精简范围（≤ 30KB）：

```sh
python scripts/find_by_brief.py --brief-file <本次目录/brief_request.json>
```

单项快速检索也可直接用命令行参数构造需求单：

```sh
python scripts/find_by_brief.py --label '区域认知破局' --task strategy --problem 区域认知弱 --query '区域 认知' --query '板块 价值' --prefer-industry 住宅 --prefer-stage 首开 --prefer-recent
```

查看返回中每条候选的说明字段：
- `matched_need`、`matched_by`：命中了哪项需求、靠哪个短查询或标签召回；
- `evidence_units`：命中的具体页码、页面类型、原文摘录与预览图 URL；
- `preference_diff`：与软偏好的异同（如 `"同为住宅；同为首开；客群不同：高端"`）；
- `project_id` 与 `project_siblings_summary`：若显示“同项目还有：策略案 2、主画面 3、楼书 1”，可进一步调取同项目的全套物料：

```sh
python scripts/find_by_brief.py --project-id <project_id>
```

零结果的需求会如实返回空列表并附 `relax_suggestions`（可放宽建议），不得静默删除用户的硬筛选。单点补充查询或翻页可使用 `scripts/find_references.py`（默认 `--detail brief`；需完整章节与全量标签时加 `--detail full`），全源目录补查可继续用 `scripts/query_cases.py`。

## 3. 读命中页与核实原图

从候选结果的 `evidence_units` 取原页码/原段号，回读命中页与相邻上下文：

```sh
python scripts/find_references.py --case-id <资产ID> --page <命中页码> --radius 1
```

- 视觉参考必须通过宿主看图能力实际查看页面图片；若结果含 `visual_candidate_notice`（“画面标签为候选，需看原图”），说明命中依赖候选视觉标签，未看原图前不得当作正式视觉结论。
- 分别核对原图文字、可见画面与传播解释：`unreviewed`/`unproofread` OCR 必须回看原图；规则/阅读推断标签（`source: rule / agent_read`）与历史提案目标不代表实际落地成效。

## 4. 给出 3–5 个可判断的候选

围绕需求组织 3–5 个推荐候选，逐项写明：
1. 对应哪项 Brief 需求及出处；
2. 靠哪个查询或标签命中、证据在第几页；
3. 原资料解决的业务问题与可借鉴的方法/画面；
4. 与当前项目的异同（引用 `preference_notes` 标明业态、阶段、客群或条件差异）；
5. 同项目是否还有可联看的策略案、主画面、楼书或 VI。

选定后用 `scripts/fetch_references.py --case-id <ID> --page <ID:页码> --out <本次参考包目录>` 从 NAS 取回页图与原件。

## HTTP / MCP 入口对照

更新后的 MCP 提供 `search_references_by_brief`、`get_project_card`、`search_references`、`read_reference_context`。直接调用只读 HTTP 接口时：
- `GET /api/reference-options`：用途、难题/阶段/页型释义、覆盖统计与 `brief_example`。
- `POST /api/references/brief`：提交结构化需求单 `needs` + 硬条件 + `prefer`，一次返回融合去重后的精简候选（≤ 30,000 字节）。
- `GET /api/projects/{project_id}`：返回项目卡及同项目策略案、主画面、楼书、VI 资料清单。
- `POST /api/references/search`：单路页级检索（支持 `detail=brief|full`、长句自动拆词、城市别名归一、`year_from`/`year_to`、`sort=recent`）。
- `POST /api/references/read`：按 `asset_id`、`page`、`radius` 读取命中页及前后页。

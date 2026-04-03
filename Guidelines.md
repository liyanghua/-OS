# 经营操盘系统 · 界面与交互指南

本文档与 `AGENTS.md`、根目录各 source-of-truth 文档并列；实现时以代码中 CSS 变量（`globals.css` 的 `:root`）为单一事实来源。整体交互细化与范式说明见根目录 **`PROJECT_INTERACTION_DESIGN_PRINCIPLES.md`**（脉冲驱动、异常优先、经营大脑可视化等）；落地时以**不扩展数据模型**为前提做 UI 映射。

## 通用原则

- 布局默认使用 **flex / grid**，避免无必要的绝对定位。
- 管理向界面：**信息密度适中**，段落与卡片留白一致，避免「纯数据表格感」。
- 默认 **简体中文** 业务化文案；不在未要求时把已有中文改回英文。

## 字体与排版（Typography）

- **基准字号**：`14px`（`body`），正文 `line-height` 约 `1.55`。
- **字体栈**：`Noto Sans SC`（标题与正文主字体，由 `layout.tsx` 注入）+ 系统中文回退（苹方、微软雅黑等）。
- **标题层级**：页面主标题约 `1.25rem`～`1.5rem`、字重 `600`；面板标题（`ManagementPanel`）使用 `text-sm` + `font-semibold`，描述行 `text-xs` + `--muted`。

## 颜色与主题（深色管理台）

- 背景分层：`--background`（主底）、`--surface` / `--surface-elevated`（卡片与顶栏）、`--strip-bg`（上下文条）。
- 文本：`--foreground` 主文、`--muted` / `--muted-2` 次要与标签。
- **主操作色** `--accent`：链接、当前导航、主按钮；hover 使用 `--accent-hover`。
- 边框：`--border`；强调轮廓可用半透明白边（见卡片 `ring`）。
- **系统气质（实现参考）**：整体偏 **Enterprise 数据台**（层次清晰、点阵主工作区、等宽字体用于 ID/指标）+ **Linear 式**排版（略紧字距、轻阴影、150ms 级过渡）+ **AI-native** 极轻环境光与卡片顶栏 `panel-top-sheen`（暗示智能层协同，不抢正文）。

## 卡片与容器（Cards）

- **标准管理面板**（`ManagementPanel`）：大圆角、轻阴影、顶栏内阴影，形成「可扫读的区块」。
- **列表内条目**（动作行、例外行等）：保持 `rounded-md`、边框略浅于面板，背景可略提亮以分层。
- 同一页面内卡片间距统一为 `space-y-6`～`space-y-8`（已由各页 `space-y-*` 控制，新增区块勿随意缩小）。

## 按钮与交互（Button）

遵循三级强度（每屏主行动作不宜过多）：

| 级别 | 用途 | 视觉 |
|------|------|------|
| **Primary** | 区块内最主要操作 | 填充 `--accent`，白字 |
| **Secondary** | 并列次要操作 | 描边 `accent/35`，透明底，hover 轻微铺底 |
| **Tertiary** | 低强调（如切换、文字链） | 无语义底色，hover 仅变色 |

角色切换、筛选类控件使用 **Secondary/Tertiary**，避免满屏实心按钮。

## 侧边导航

- 当前路由：浅色底 + 左侧强调条 + 主色文字（或 `accent` 文字）。
- 非当前：muted 文字，hover 提亮背景与字色。

## 可访问性

- 交互元素保留 `:focus-visible` 轮廓（主题内 `--ring-focus`）。
- 不单独用颜色传达状态；辅以文案或图标（现有风险等级、审批状态标签保持）。

## 人机协作徽章（`OperatingLayerBadge`）

- 四层文案统一为：**人为发起**、**经营建议**、**智能体**、**自动化**（与领域 `triggeredBy` 等映射一致）。
- **对比度**：本产品是深色底为主，徽章字色须用浅色（如 `text-violet-100`），背景用半透明色带 + 细内高光；**禁止**依赖 `dark:` 切换而默认使用 `*-950` 字色，以免在深色卡片上不可读。
- 说明行（hint）优先用 `text-[var(--foreground)]` 的透明渐变（如 `/85`），避免仅靠 `--muted` 贴在本色底上过淡。

---

*修订时请同步检查 `src/app/globals.css` 与 `ManagementPanel`、壳层组件是否一致。*

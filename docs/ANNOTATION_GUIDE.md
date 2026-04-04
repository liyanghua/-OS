# 桌布主图策略模板 - 标注指南

## 标注目标

为小红书桌布笔记标注四层标签，用于构建主图策略模板库，支撑弱监督训练、特征与聚类、模板编译与 Agent 消费。

## 标注对象

每条小红书桌布笔记，包括：**封面图**、**图组**、**标题**、**正文**、**话题标签**、**评论**、**互动数据**（点赞/收藏等作为辅助，不单独作为一层标签）。

---

## 四层标签体系

### L1 任务标签

#### 封面任务（单选主标签 + 可多选次标签）

主标签：选择**最符合封面首要任务**的一条；次标签：若封面同时承担其他任务，可补充，但不宜过多（建议次标签 ≤ 3）。

| ID | 名称 | 定义 | 正例要点 | 反例要点 |
|----|------|------|----------|----------|
| hook_click | 强停留强点击 | 首图以视觉冲击或强钩子文案优先换取点击与停留 | 标题/封面有「必看」「绝了」类强钩子，画面抓眼 | 纯产品白底、无文案弱标题 |
| scene_seed | 场景种草 | 通过完整生活场景让用户想拥有这种生活方式 | 餐桌整体氛围、仪式感、居家/周末场景清晰 | 纯特写无场景、只堆参数 |
| style_anchor | 风格定锚 | 首图明确传达法式/奶油/中古等风格归属与审美标签 | 风格词与画面一致，空间气质统一 | 风格词与画面冲突、泛化「好看」 |
| texture_detail | 材质细节打动 | 以纹理、工艺、垂坠、花边等细节建立质感与价值感 | 纹理/刺绣/垂坠清晰可见 | 只有远景无细节、细节糊 |
| feature_explain | 卖点解释 | 首图或文案承担防水防油易打理等功能卖点的可读解释 | 功能点可读、与品类相关 | 纯氛围无功能、功能仅小字 |
| price_value | 平价性价比 | 突出平价、替代、性价比与低成本获得感 | 百元/平价/学生党等与画面一致 | 标平价但无任何价格带线索 |
| gift_event | 节庆礼赠 | 绑定节日、纪念日、生日、礼赠与聚餐节点情绪 | 节点元素与文案一致 | 无节点却写大促、礼赠无对象 |
| set_combo | 桌搭套装方案 | 呈现桌布与餐具花器蜡烛等组合成套的可抄作业方案 | 多道具组合逻辑清晰 | 仅单品无搭配线索 |
| before_after | 改造前后对比 | 通过前后对比或气质反差强化变化与改造价值 | 有参照系、变化可信 | 单张无对比、过度修图 |
| shopping_guide | 选购指导 | 首图或文案引导尺寸、选购、避坑、对比款等决策信息 | 攻略/怎么选/尺寸可见 | 纯情绪标题无任何决策信息 |

#### 图组任务（可多选，描述整组分工）

| ID | 名称 | 定义 | 正例要点 | 反例要点 |
|----|------|------|----------|----------|
| cover_hook | 封面负责点击 | 图组第一张承担钩子与进店任务，与其他张分工明确 | 首图强钩子，后图展开不同任务 | 首图说明书式参数图 |
| style_expand | 风格展开 | 后续图补足整体风格、空间气质与搭配一致性 | 同风格多角度/空间 | 风格突变无过渡 |
| texture_expand | 材质细节展开 | 补充纹理、边缘、厚薄、工艺等近景证据 | 近景可辨识纹理工艺 | 特写仍看不清纹理 |
| usage_expand | 使用场景展开 | 展示真实上桌、不同场景或用法以强化代入 | 早餐/下午茶/聚餐等延展 | 全程棚拍无使用情境 |
| guide_expand | 选购引导展开 | 图组后部给出尺寸、对比、清单或轻购买建议 | 末尾信息图/对比/清单 | 最后一张仍纯氛围无增量 |

---

### L2 视觉结构标签（多选）

按组勾选；同一组内可多选（若画面同时具备多种特征）。

**景别 shot（4）**

| ID | 名称 | 定义 |
|----|------|------|
| shot_topdown | 俯拍 | 近似垂直向下，桌面几何透视收缩明显 |
| shot_angled | 斜侧拍 | 可见桌面顶面与立面，透视斜向 |
| shot_closeup | 近景特写 | 布面或工艺占画幅主体 |
| shot_wide_scene | 全景桌面/空间 | 完整餐桌或含环境的全景 |

**构图 composition（5）**

| ID | 名称 | 定义 |
|----|------|------|
| composition_centered | 中心构图 | 视觉重心集中于画面中心轴线 |
| composition_diagonal | 对角线构图 | 引导线或桌沿沿对角线分布 |
| composition_layered | 层次构图 | 前中后景分层，空间深度清晰 |
| composition_dense | 饱满构图 | 道具与食器较多、留白少 |
| composition_minimal | 极简构图 | 元素少、留白显著、背景干净 |

**主体/元素 subject（10）**

| ID | 名称 | 定义 |
|----|------|------|
| has_tablecloth_main | 桌布为主体 | 桌布视觉权重显著最高 |
| has_tableware | 有餐具 | 盘碗杯筷等可见 |
| has_food | 有食物 | 可识别食物强化用餐场景 |
| has_flower_vase | 有花器花艺 | 花、花瓶或绿植作氛围陪体 |
| has_candle | 有蜡烛烛光 | 烛台、蜡烛或烛光光斑 |
| has_hand_only | 仅手部入镜 | 手与桌面互动，无完整人像 |
| has_people | 有人物 | 面部或完整人体可辨 |
| has_chair_or_room_bg | 椅背或房间背景 | 椅背、墙角、柜体等空间信息 |
| has_gift_box | 有礼盒 | 礼盒、礼袋等礼赠符号 |
| has_festival_props | 节庆道具 | 圣诞/新年/生日帽等可识别节点符号 |

**桌布露出 cloth_exposure（6）**

| ID | 名称 | 定义 |
|----|------|------|
| cloth_full_spread | 桌布大面积铺展 | 整面或大面积平铺 |
| cloth_partial_visible | 桌布部分可见 | 局部或被遮挡较多 |
| cloth_texture_emphasis | 强调纹理 | 织纹、提花、麻感等被强调 |
| cloth_pattern_emphasis | 强调花型图案 | 印花/格纹/条纹等为视觉重点 |
| cloth_edge_emphasis | 强调边缘工艺 | 流苏、蕾丝边、包边等为构图重点 |
| cloth_with_other_products | 与其他商品同框 | 多 SKU 或组合呈现 |

**文案叠层 text_overlay（8）**

| ID | 名称 | 定义 |
|----|------|------|
| text_none | 无文案覆盖 | 无显著叠加标题或贴纸字 |
| text_light | 轻文案 | 少量小字或单一短标签 |
| text_medium | 中文案 | 明显标题条或多行说明 |
| text_heavy | 重文案 | 大字、多贴纸、接近海报或电商风 |
| text_style_label | 风格标签字 | 封面字以风格形容词为核心 |
| text_price_label | 价格带标签 | 数字价或价格带显著 |
| text_transformation_claim | 改造主张字 | 焕新、改造、前后变化等 |
| text_scene_claim | 场景主张字 | 早餐、下午茶、聚餐等场景命题在封面主标题 |

**色板 palette（7）**

| ID | 名称 | 定义 |
|----|------|------|
| palette_warm | 暖色调 | 红橙黄等暖色温主导 |
| palette_cool | 冷色调 | 蓝绿灰等冷色温主导 |
| palette_neutral | 中性色调 | 黑白灰米棕低饱和为主 |
| palette_cream | 奶油色系 | 米白、奶黄、浅杏等 |
| palette_french_vintage | 法式复古色 | 复古绿、做旧金、深木等组合 |
| palette_mori | 森系/自然色系 | 木色、麻色、绿植、自然光感 |
| palette_festival_red_green | 节庆红绿 | 典型节日红绿金等 |

**光线 lighting（3）**

| ID | 名称 | 定义 |
|----|------|------|
| lighting_soft | 柔和光 | 漫反射、弱阴影 |
| lighting_natural | 自然光 | 窗光、日光感 |
| lighting_dramatic | 戏剧光 | 强对比、烛光氛围等 |

---

### L3 经营语义标签（多选）

| ID | 名称 | 定义 |
|----|------|------|
| mood_daily_healing | 日常治愈 | 温馨、舒服、温柔等日常居家情绪 |
| mood_refined_life | 精致生活 | 精致感、品位、高级感、仪式感 |
| mood_brunch_afternoontea | 早餐下午茶仪式 | 早午餐、下午茶、咖啡角 |
| mood_friends_gathering | 朋友聚餐 | 聚会、多人餐桌、家宴 |
| mood_festival_setup | 节庆布置 | 节日氛围与节点装饰 |
| mood_anniversary | 纪念日生日 | 生日、周年、情侣晚餐等私人节点 |
| mood_low_cost_upgrade | 低成本改造 | 百元、平价改造、省钱 |
| mood_small_space_upgrade | 小户型提气质 | 租房、出租屋、小餐厅 |
| mood_photo_friendly | 出片感 | 好拍、上镜、拍照好看 |
| mood_style_identity | 风格身份认同 | 我的家、本命风格等自我表达 |
| mood_giftable | 适合作礼物 | 送礼、礼物、送妈妈/女友等 |
| mood_practical_value | 实用耐脏易打理 | 耐脏、好洗、防水防油等 |

---

### L4 风险标签（多选）

| ID | 名称 | 定义 |
|----|------|------|
| risk_too_generic | 内容过于通用 | 缺乏桌布品类特异性，可套任意家居图 |
| risk_no_product_focus | 商品焦点不足 | 氛围强但桌布识别弱 |
| risk_overstyled_low_sellability | 过度风格化难卖货 | 像博主作品，购买路径弱 |
| risk_text_too_ad_like | 文案过像硬广 | 秒杀、限时、全网最低等促销语气 |
| risk_scene_not_reproducible | 场景难以复现 | 豪华布景、用户难复制 |
| risk_holiday_only | 强节点难泛化 | 仅适合特定节日，日常迁移差 |
| risk_style_too_niche | 风格过窄 | 人群覆盖过窄 |
| risk_cloth_not_visible_enough | 桌布可见度不足 | 封面占比过低或纹理不可辨 |

---

## 标注规则

1. 每条笔记至少分配 **1 个 L1 封面任务**（主标签）；需要时增加次标签。
2. **L2–L4** 按画面与文案实际观察**多选**；不确定宁可少选并在置信度上反映。
3. 若无法确定，将对应 `LabelResult` 的 **confidence 标为小于 0.5**，并在证据中说明依据不足。
4. **证据片段**：截取标题/正文中的关键短语（或说明「来自封面视觉」），便于质检与模型对齐。

## 标注质量要求

- 标注者间一致率 **大于 0.7**（Cohen's Kappa，主标签层优先统计）。
- 每条笔记标注时间建议 **少于 2 分钟**（复杂图组可适当延长并标记复查）。
- 疑难样本设置 **human_override=True**，进入待复查队列。

## 常见问题与标注要点

**Q1：封面既是「场景种草」又像「风格定锚」，怎么选主标签？**  
A：若用户第一眼更易被「生活方式/餐桌整体氛围」打动，主标 `scene_seed`；若标题与画面核心是「法式/奶油」等风格词且空间气质为首要信息，主标 `style_anchor`。另一条作次标签。

**Q2：图只有手没有脸，算「有人物」吗？**  
A：不算。手部-only 用 `has_hand_only`，不要同时选 `has_people`。

**Q3：桌布被食物盖住大半，L2 怎么标？**  
A：优先 `cloth_partial_visible`；若纹理完全不可辨，考虑 L4 `risk_cloth_not_visible_enough` 或 `risk_no_product_focus`。

**Q4：封面没有任何字，但正文很长，text_overlay 选什么？**  
A：L2 文案叠层**以封面画面为准**，通常选 `text_none`；不要在 L2 用正文代替封面观测。

**Q5：「平价」只在正文出现，封面没有价格字，能标 `text_price_label` 吗？**  
A：不能。`text_price_label` 要求封面侧价格带显著；可在 L3 用 `mood_low_cost_upgrade` 等与正文一致的语义。

**Q6：节庆道具很多但桌布看不清，如何平衡 L2 与 L4？**  
A：L2 可标 `has_festival_props`；L4 务必考虑 `risk_cloth_not_visible_enough` 或 `risk_no_product_focus`。

**Q7：图组只有 3 张，还要标齐 5 个图组任务吗？**  
A：不必。只标**实际承担的分工**；若多张任务重复，不强行拆出 `style_expand` / `texture_expand`。

**Q8：不确定是俯拍还是斜侧拍怎么办？**  
A：选更接近的一项，并将 `confidence` 设为小于 0.5；或只选确定的其他 L2 项，避免两个互斥景别都标满置信度。

---

与自动化规则标注的对照见 `config/template_extraction/label_taxonomy.yaml`（`trigger_keywords`、`counter_examples`、`trigger_conditions`）。项目流水线说明见 [TEMPLATE_EXTRACTION.md](./TEMPLATE_EXTRACTION.md)。

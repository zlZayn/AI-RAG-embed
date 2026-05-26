// ============ 样式配置（高密度学术风格） ============

// 页面整体设置
#set page(
  paper: "a4",
  margin: (top: 0.25in, bottom: 0.25in, left: 0.3in, right: 0.3in),
  numbering: none,
)

// 正文默认字体、字号、颜色、语言
#set text(
  font: "Microsoft YaHei",
  size: 8.5pt,
  fill: rgb("#1a1a1a"),
  lang: "zh",
)

// 段落格式
#set par(
  leading: 4.25pt, // 原 0.5em → 8.5pt × 0.5 = 4.25pt
  justify: false,
)

// 有序列表和无序列表的间距、缩进
#set enum(spacing: 3pt, indent: 12pt)
#set list(spacing: 3pt, indent: 12pt)
#set block(spacing: 8.5pt)    // 原 1em → 8.5pt

// 段落间距
#show par: it => { it + v(5pt) }

// ---------------------- 标题样式 ----------------------

// 一级标题（章标题）
#show heading.where(level: 1): it => {
  set text(font: "Microsoft YaHei", size: 13pt, weight: "bold", fill: rgb("#0a7a7a"))
  set align(center)
  let blk = block(breakable: false, spacing: 0pt)[
    #it.body
    #v(1pt)
    #line(length: 100%, stroke: 1.2pt + rgb("#0a7a7a"))
  ]
  blk
}

// 二级标题（节标题）
#show heading.where(level: 2): it => {
  set text(font: "Microsoft YaHei", size: 10pt, weight: "bold", fill: rgb("#b8860b"))
  let blk = block(breakable: false, spacing: 0pt, inset: (left: 5pt), stroke: (left: 2.5pt + rgb("#d4a017")))[#it.body]
  blk + v(6pt)
}

// 三级标题（小节标题）
#show heading.where(level: 3): it => {
  set text(font: "Microsoft YaHei", size: 9pt, weight: "bold", fill: rgb("#4a6fa5"))
  let blk = block(breakable: false, spacing: 0pt)[#it.body]
  blk + v(4pt)
}

// 四级标题（更低层次）
#show heading.where(level: 4): it => {
  set text(font: "Microsoft YaHei", size: 8.5pt, weight: "bold", fill: rgb("#6b8db5"))
  let blk = block(breakable: false, spacing: 0pt)[#it.body]
  blk + v(3pt)
}

// ---------------------- 表格样式 ----------------------

#set table(
  inset: (x: 5pt, y: 3pt),
  stroke: 0.5pt + rgb("#d5d0c8"),
)

// 表头行
#show table.cell.where(y: 0): it => {
  set text(size: 7.5pt, weight: "bold", fill: rgb("#0a7a7a"))
  set align(left)
  rect(
    fill: rgb("#dff0f0"),
    stroke: (
      top: 0.8pt + rgb("#0a7a7a"),
      bottom: 0.8pt + rgb("#3a9a9a"),
      left: none,
      right: none,
    ),
    width: 100%,
    inset: (x: 2pt, y: 2pt),
  )[#it]
}

// 普通单元格
#show table.cell: it => {
  set text(size: 7.5pt)
  set align(left)
  it
}

// ---------------------- 引用块样式 ----------------------

#show quote: it => {
  let blk = block(
    width: 100%,
    inset: (left: 4pt, right: 4pt, top: 1pt, bottom: 1pt),
    stroke: (left: 1.5pt + rgb("#d4a017")),
    fill: rgb("#fdf5e6"),
  )[
    #set text(size: 8pt)
    #it.body
  ]
  blk + v(2pt)
}

// 加粗文字
#show strong: it => {
  set text(fill: rgb("#1a1a1a"))
  it
}

// 块级数学公式
#show math.equation.where(block: true): it => {
  v(1pt) + align(center, it) + v(1pt)
}

// 自定义水平分隔线
#let hr = {
  v(1pt)
  line(length: 100%, stroke: 0.3pt + rgb("#c8c2b8"))
  v(1pt)
}

// ============ 正文内容 ============

= 时间序列分析 - 考试重点

#hr

== 简答题（5道）

=== 1. ARIMA/SARIMA模型预测的关键步骤

*题目*：ARIMA模型如何结合实际案例进行预测？数据预处理的关键步骤有哪些？

*完整步骤*：

+ *获取数据*：收集至少几年的数据量
+ *统一时间频率*：统一为月/周/天（天的数据信息量更大）
+ *STL分解*：识别异常值（如疫情期数据变化）
+ *季节性差分*：传染病数据做 *12阶季节性差分*，消除周期性高峰（需要季节性差分时应使用 *SARIMA* 模型）
+ *平稳性检验*：结合ADF检验确保差分后序列平稳
+ *干预变量*：引入政策变量（如口罩政策）
+ *建模*：优先选择SARIMA模型
+ *参数优化*：通过AIC/BIC准则优化参数
+ *残差检验*：验证残差是否为白噪声
+ *预测*

#hr

=== 2. 加法模型vs乘法模型应用场景

*模型形式*：

- *加法模型*：序列值 = 趋势值 + 季节值 + 随机值
- *乘法模型*：序列值 = 趋势值 × 季节值 × 随机值

*应用场景*：

- *加法模型*：各成分之间相互独立的情况
- *乘法模型*：季节效应与其他效应存在乘法关系，或季节性波动幅度随时间趋势增长的情况

#hr

=== 3. 预测值+95%置信区间的原因

*核心要点*：

- 未来结果受随机波动、模型参数设定、外部环境变化等多种因素影响
- 预测值是基于样本数据和模型得到的 *估计结果*，不是未来一定会发生的真实值
- 只报告点预测值会让使用者误认为未来一定按此值发生，*低估预测不确定性*
- *预测区间*：在一定置信水平下，未来真实值可能落入的范围
- 点预测值+预测区间结合，才能更好服务于公共卫生决策和医疗资源配置

#hr

=== 4. 差分阶数d如何影响预测结果

#quote(block: true)[
  注：本课程中用大写D表示普通差分阶数，与标准符号中小写d一致。
]

*d的作用*：通过消除时间序列的非平稳性来影响预测结果

#figure(
  table(
    columns: (25%, 45%, 30%),
    align: (center, auto, auto),
    table.header([d值], [适用情况], [后果]),
    [*d=0*], [已平稳的序列], [预测值随预测步长增加收敛到无条件均值；若序列实际非平稳会导致 *伪回归*],
    [*d=1*], [含趋势但可通过一次差分平稳的序列], [消除单位根，保留短期记忆性（随机游走特征），适用于大多数实际情况],
    [*d=2*], [过度差分], [序列方差增大，损失真实信息，可能出现 *虚假的反向趋势*],
  ),
  kind: table,
)

*例子*：毕业后收入（第1年8000→第2年9000→第3年10000...）

- 一阶差分：后减前 = 1000, 1000, 1000...（变化幅度稳定）

#hr

=== 5. ARIMA vs ARIMAX模型区别（第7章）

#figure(
  table(
    columns: (34%, 30%, 36%),
    align: (center, auto, auto),
    table.header([对比项], [ARIMA], [ARIMAX]),
    [*建模依据*], [序列自身过去的变化规律], [序列自身历史 + 外部解释变量],
    [*刻画内容*],
    [内部趋势、差分平稳性、自相关、移动平均结构],
    [同时纳入外部因素（气温、空气污染、政策干预、人口结构等）],

    [*优势*], [简洁], [提高预测精准度，有助于解释数据变化原因],
  ),
  kind: table,
)

*案例*：体重预测

- *ARIMA*：仅用历史体重数据
- *ARIMAX*：增加外卖频率、菜系、运动习惯等外部变量 → 预测更准确

#hr

== 综合题

=== 一、疾病发病率特征识别（5分）

*题目形式*：给出一个疾病发病率的描述，呈现某种特征。

*核心概念：系统性模式 vs 噪声*

#figure(
  table(
    columns: (21%, 21%, 36%, 22%),
    align: (center, auto, auto, auto),
    table.header([类型], [性质], [可预测性], [例子]),
    [*系统性模式*], [有规律、可重复], [可预测、可建模], [趋势、季节性、节假日效应],
    [*噪声*], [随机、无规律], [不可预测], [随机误差、外部突发事件],
  ),
  kind: table,
)

*关键区分*：季节性是系统性模式（可预测），不是噪声。残差中包含随机噪声和外部事件。

*第1问（2分）：特征识别*

#figure(
  table(
    columns: 2,
    align: (auto, auto),
    table.header([特征], [如何识别]),
    [上升趋势], [从图中识别长期向上趋势],
    [季节性高峰], [从图中识别周期性重复的高峰],
  ),
  kind: table,
)

*第2问（3分）：STL分解法*

*问题1*：残差存在显著波动，反映了什么问题？

*答案*：外部事件干扰（如口罩政策、封城、防疫政策变化）会导致发病率爆发式变化，影响模型残差，降低预测精度。

*问题2*：为什么要先优先分离出季节性因素？

*答案*：

- 季节性是 *系统性模式*，不是噪声
- 但季节性会 *掩盖* 长期趋势
- 先分离季节性，才能看清真实趋势，提高模型泛化能力

#hr

=== 二、10分大题（模型选择+残差检验+外部因素）

*题目形式*：根据ACF/PACF特征选择模型，解释选择理由，进行残差检验并解读，分析外部因素影响，提出模型优化思路。

*考点分布*：

- 模型选择（ACF/PACF定阶）：~4分
- 残差检验解读：~3分
- 外部因素分析+优化思路：~3分

*答题要点*：

+ *模型选择*：根据ACF拖尾/截尾、PACF拖尾/截尾特征，确定p、d、q参数
+ *残差检验*：p\>0.05说明残差是白噪声，模型拟合良好；p\<0.05说明还有信息未被捕捉
+ *外部因素*：政策变化、突发事件等导致实际数据与模型预测出现差异
+ *优化思路*：引入干预变量、考虑ARIMAX模型纳入外部解释变量

#hr

== 选择题

=== 1. ARIMA模型初步识别

*判断标准*

#figure(
  table(
    columns: 3,
    align: (auto, auto, auto),
    table.header([ACF特征], [PACF特征], [初步考虑模型]),
    [q阶后截尾], [拖尾], [MA(q)模型],
    [拖尾], [p阶后截尾], [AR(p)模型],
    [拖尾], [拖尾], [ARMA(p,q)模型],
  ),
  kind: table,
)

*具体模型ACF/PACF模式*（PPT第3章第84页）

#figure(
  table(
    columns: 3,
    align: (auto, auto, auto),
    table.header([模型], [ACF], [PACF]),
    [AR(1)], [指数衰减拖尾], [1阶后截尾],
    [AR(2)], [振荡衰减拖尾], [2阶后截尾],
    [MA(1)], [1阶后截尾], [指数衰减拖尾],
    [MA(2)], [2阶后截尾], [缓慢衰减拖尾],
    [ARMA(1,1)], [拖尾], [拖尾],
    [ARMA(2,2)], [拖尾], [拖尾],
  ),
  kind: table,
)

*截尾 vs 拖尾判断*：

- *截尾（cuts off）*：在特定阶数后突然降至零，保持在置信区间内
- *拖尾（tails off）*：逐渐衰减（指数衰减或正弦衰减）

#hr

=== 2. ARIMA(p,d,q) 统一框架

ARIMA是 *统一框架*，AR、MA、ARMA都是其特例：

#figure(
  table(
    columns: (27%, 45%, 28%),
    align: (auto, auto, auto),
    table.header([情形], [模型形式], [说明]),
    [*d=0, q=0*], [ARIMA(p,0,0) = *AR(p)*], [纯自回归模型],
    [*d=0, p=0*], [ARIMA(0,0,q) = *MA(q)*], [纯移动平均模型],
    [*d=0*], [ARIMA(p,0,q) = *ARMA(p,q)*], [自回归移动平均模型],
    [*d\>0*], [ARIMA(p,d,q)], [先对原序列做d次差分，再对差分后序列建立ARMA(p,q)],
  ),
  kind: table,
)

#quote(block: true)[
  *核心关系*：*ARIMA = 差分 + ARMA*
]

*参数含义*：p=自回归项阶数，d=差分阶数，q=移动平均项阶数

#hr

=== 3. 模型拟合优度评估

#figure(
  table(
    columns: 3,
    align: (auto, auto, auto),
    table.header([指标], [解释], [判断标准]),
    [R²], [决定系数], [越高越好（但可能过拟合）],
    [AIC], [赤池信息准则], [越低越好（惩罚复杂度）],
    [BIC], [贝叶斯信息准则], [越低越好（比AIC更惩罚复杂度）],
  ),
  kind: table,
)

*AIC/BIC 公式*

$ upright("AIC") = -2 ln(L) + 2k $

$ upright("BIC") = -2 ln(L) + k ln(n) $

#hr

=== 4. 其他选择题考点

#figure(
  table(
    columns: (37%, 63%),
    align: (auto, auto),
    table.header([考点], [答案/要点]),
    [政策实施后时间序列均值暴增，模型应引入什么？], [*干预变量*],
    [ACF一阶截尾、PACF拖尾 → 选什么模型？], [*MA(1)*],
    [ACF拖尾、PACF一阶截尾 → 选什么模型？], [*AR(1)*],
    [漂移项drift的作用], [时间序列中的 *确定性线性趋势*],
    [平稳序列的特征], [*均值、方差、自协方差都是常数*],
    [X-11/X-12/X-13季节调节模型核心技术], [*移动平均方法*],
    [X-11三次移动平均方法], [①简单移动平均 ②亨德森加权移动平均 ③Musgrave非对称移动平均],
    [因素分解包含哪几个成分？], [趋势、季节、残差（+节假日）],
    [乘法模型适用情况], [季节性波动幅度随时间趋势增长],
    [一阶差分能否消除所有类型趋势？], [*不对*，只能消除线性趋势],
    [LB检验p\<0.05说明什么？], [残差 *不是* 白噪声（陷阱题：老师故意说反）],
    [随机游走模型方差随时间？], [*无限增大*],
    [协整检验用途], [检验响应序列与自变量序列具有 *长期稳定的均衡关系*],
    [干预分析用途], [评估 *政策变化* 的效果],
    [ARIMA初步识别的依据方法], [*ACF与PACF的截尾/拖尾特征*],
    [伪回归是什么？], [两个非平稳序列直接回归，即使无真实关系也可能出现"显著"结果（第7章第2节）],
    [格兰杰因果检验是什么？], [判断一个变量的历史信息是否有助于预测另一个变量（*不等于* 真正因果推断）],
  ),
  kind: table,
)

#hr

== 判断题

=== 1. 因素分解理论

*四种成分*：趋势（长期上升/下降）、季节（周期性重复）、节假日（特定日期效应）、残差（随机噪声+外部事件）

*判断要点*：

- 乘法模型适合季节性波动幅度随趋势增长的情况 → *对*
- X-11季节调节模型核心技术是移动平均 → *对*
- 所有序列波动可归纳为趋势+季节+循环+随机 → *对*（传统表述，本课程用"节假日"代替"循环"）
- 一阶差分可消除所有类型趋势 → *错*（只能消除线性趋势）
- LB检验p\<0.05说明残差是白噪声 → *错*（p\>0.05才是白噪声）
- 随机游走方差随时间无限增大 → *对*

#hr

=== 2. 模型诊断

*白噪声检验*

#figure(
  table(
    columns: 3,
    align: (center, left, center),
    table.header([p值], [结论], [预测可靠性]),
    [p\>0.05], [残差是白噪声，模型拟合良好], [可靠],
    [p\<0.05], [残差不是白噪声，还有信息未被捕捉], [受影响],
  ),
  kind: table,
)

#hr

=== 3. 其他判断题考点

#figure(
  table(
    columns: 2,
    align: (auto, center),
    table.header([考点], [判断]),
    [两个平稳序列直接回归不会出现伪回归], [对],
    [格兰杰因果检验=真正意义上的因果推断], [错（只是预测关系）],
    [协整检验用于检验长期均衡关系], [对],
    [ARIMA模型中drift表示确定性线性趋势], [对],
  ),
  kind: table,
)

#hr

== 名词解释（5个，不确定以下哪五个）

#figure(
  table(
    columns: (50%, 50%),
    align: (auto, auto),
    table.header([概念], [定义]),
    [*自相关函数(ACF)*], [衡量时间序列与自身不同滞后阶数的相关性],
    [*偏自相关函数(PACF)*], [控制中间滞后项影响后，序列与特定滞后阶数的净相关性],
    [*单位根检验(ADF)*], [检验时间序列是否存在单位根，即是否平稳],
    [*白噪声*], [均值为0、方差恒定且无自相关的随机误差序列，是时间序列建模的基础假设],
    [*季节性差分*], [用当前观测值减去一个季节周期之前的观测值（如今年5月减去年5月），消除序列中的季节性波动],
    [*信息准则(AIC/BIC)*], [在模型拟合优度和复杂度之间进行权衡，用于模型选择],
  ),
  kind: table,
)

#hr

== 核心概念对比

=== 系统性模式 vs 噪声

#figure(
  table(
    columns: 3,
    align: (auto, auto, auto),
    table.header([维度], [系统性模式], [噪声]),
    [*本质*], [有规律、可重复], [随机、无规律],
    [*可预测性*], [可预测、可建模], [不可预测],
    [*例子*], [趋势、季节性、节假日], [随机误差、突发外部事件],
  ),
  kind: table,
)

=== 差分类型对比

#figure(
  table(
    columns: 3,
    align: (auto, auto, auto),
    table.header([类型], [计算], [消除的模式]),
    [普通差分], [$X_t - X_(t-1)$], [线性趋势],
    [季节性差分], [$X_t - X_(t-s)$], [季节性模式（s=季节周期）],
  ),
  kind: table,
)

#hr

== 考试题型分值汇总

#figure(
  table(
    columns: 3,
    align: (auto, auto, auto),
    table.header([题型], [分值], [题数]),
    [选择题], [\~20分], [约10道],
    [判断题], [\~15分], [约15道],
    [简答题], [5道×5分], [25分],
    [综合题], [5分 + 10分], [15分],
    [名词解释], [5道×3分], [15分],
  ),
  kind: table,
)

*总计*：约90分

#hr

== 待补充内容清单

#figure(
  table(
    columns: 3,
    align: (center, auto, center),
    table.header([序号], [内容], [状态]),
    [1], [第7章协整与ECM模型细节], [待补充],
    [2], [干预分析具体方法], [待补充],
    [3], [伪回归详细解释], [待补充],
  ),
  kind: table,
)

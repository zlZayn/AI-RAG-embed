# 决策：探测脚本密钥去硬编码与目录跟踪策略（2026-08-28）

已实施：是

## 问题
tests/ 下探测脚本曾硬编码真实 API 凭据（含 token 前缀密钥），存在泄露面。
docs/superpowers/ 为本仓库规划材料，曾误入库。
tests/ 与 docs/ 曾被 .gitignore 整目录忽略，新增文件无法跟踪。

## 决策
- 探测脚本改名 thinking_probe.py（不以 test_ 开头，pytest 不收集）
- 凭据全部改环境变量读取（OPENAI_API_KEY 必填、OPENAI_BASE_URL/OPENAI_MODEL 可选），缺省打印提示退出不发请求
- .gitignore 删除 tests/ 与 docs/ 两行，放开跟踪；新增 docs/superpowers/ 一行保持规划材料忽略
- docs/superpowers/ 已入库内容用 git-filter-repo 全历史清除并强推（维护者拍板）
- 决策记录 .agents/notes/ 从 1 条增至 2 条：本记录 + 2026-08-24-architecture-move.md

## 替代方案（Alternatives considered，强制）
- 密钥留代码中：泄露面扩大，任何可读仓库的人即获凭据，不可接受
- 密钥只移出跟踪、不重写历史：凭据仍留在旧 commit 可恢复，泄露风险未闭合；维护者拍板彻底清除故用 filter-repo 强推
- docs/superpowers/ 保留跟踪：规划材料混入正式仓库，本轮出现误入库事故，明确排除

## 影响
- 收益：仓库无真实凭据残留；tests/ 与 docs/ 新增文件可正常跟踪；规划材料永不入库
- 代价：docs/superpowers/ 历史被改写需协作方强制同步（强推）；探测脚本运行前须配置环境变量（多一步）
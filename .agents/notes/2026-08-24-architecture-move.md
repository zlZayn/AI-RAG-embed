# 决策：架构文档移入 docs/ARCHITECTURE.md（2026-08-24）

已实施：是

## 问题
根目录 ARCHITECTURE.md 不符合 maintenance-flow 规范（架构文档统一放 docs/ARCHITECTURE.md，根目录只留指针）。

## 决策
ARCHITECTURE.md 用 git mv 移入 docs/ARCHITECTURE.md。
README.md / README_zh.md 的指向链接同步更新为 docs/ARCHITECTURE.md。
根 AGENTS.md 文档地图新增架构指针一行。

## 替代方案（Alternatives considered，强制）
- 保留在根目录：违反规范，根目录文档堆积，维护流程无法统一处理
- 移入 docs/superpowers/：该目录存规划与练习材料，架构文档不属于规划产物
- 删除并并入 README：架构面向开发者、README 面向用户，合并破坏职责分离

## 影响
- 收益：架构文档位置统一，根 AGENTS.md 指针两跳可达，链接可校验
- 代价：docs/ 已被 .gitignore 忽略，git mv 后该文件仍被跟踪（rename 已 staged），新增其他 docs 文件需显式 add
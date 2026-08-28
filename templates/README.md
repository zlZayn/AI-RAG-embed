# templates/ — 网页 UI 模板手册

- 职责：web.py 的 Flask render_template 模板目录
- index.html：单页 UI，被 [web.py](../web.py) 的 `/` 路由依赖
- 改动后刷新方式：改文件后重启 `uv run python web.py`，浏览器访问 http://localhost:5000 验证
- 使用约束与工作偏好 → 见 [AGENTS.md](AGENTS.md)
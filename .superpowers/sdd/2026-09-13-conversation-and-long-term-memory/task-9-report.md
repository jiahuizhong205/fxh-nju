# Task 9 Report: 我的记忆设置页

## Outcome

- 新增懒加载路由 `/settings/memory`，并在“数据与存储”中添加“我的记忆”入口。
- `apps/web/src/api/client.ts` 现在发布与 Task 8 JSON schema 对齐的 `MemoryCategory`、记忆页/偏好类型及列表、CRUD、偏好 GET/PUT 方法；列表请求安全编码 category 和 opaque cursor。
- 新页支持自动记忆开关、分类 chips、加载 skeleton、空/失败状态、相关位置的重试、游标“加载更多”、新增/编辑表单和原生确认删除。
- 所有 API 失败在本页都显示可恢复的中文通用提示，不显示服务端错误或用户记忆正文；保存、删除和偏好更新期间禁用关联控件并提供文字状态。
- 列表与偏好读取均使用请求序号，组件卸载时使未完成请求失效，避免旧响应覆盖新筛选或当前状态。

## TDD Evidence

### RED

首先新增前端 source-contract 测试后运行：

```powershell
python -m unittest tests.test_frontend_user_journey -v
```

预期 RED：`/settings/memory` 不存在，且 `MemorySettingsView.vue` 不存在。随后对两个补强项分别先得到 RED：自动记忆保存错误的重试恢复路径尚不存在；本页继承的返回按钮尚为 36px，未达到 44px 触控目标。

### GREEN

```powershell
python -m unittest tests.test_frontend_user_journey -v
# 7 tests passed

Set-Location apps/web
npm run build
# vue-tsc -b && vite build exit 0
```

## Verification

```powershell
python -m unittest tests.test_memory_api tests.test_acceptance_workflow tests.test_backend_contracts -v
# 140 tests passed

python -m unittest discover -s tests -p 'test_*.py'
# 316 tests passed

git diff --check
# exit 0
```

## Accessibility and UX Self-review

- 使用真实 button、visible form labels、`role="switch"` / `aria-checked`、chip 的 `aria-pressed`、加载区的 `aria-busy`，成功消息使用 `aria-live`，错误紧贴其操作且附重试入口。
- 所有本页可操作控件（包括局部放大的返回按钮）至少 44px；焦点态可见；危险删除采用原生确认和显式危险样式。
- 375px breakpoint 改为纵向标题/操作布局并降低侧边距；记忆正文以 `overflow-wrap:anywhere` 和 `white-space:pre-wrap` 安全换行，无横向滚动。
- 仅使用项目现有 CSS tokens、卡片、chips、toggle 和内联 SVG；skeleton 动效仅使用 opacity/transform，且 `prefers-reduced-motion` 下几乎立即结束。

## Remaining Risks

- 此任务验证了 source contracts、类型检查、打包和现有 API 契约；尚未在浏览器中连接真实认证会话执行端到端人工操作。
- 页面采用原生 `window.confirm`，符合删除确认与无额外依赖要求，但其文字样式由宿主浏览器控制。

## Commit

- Subject: `feat: add memory settings page`
- Hash: recorded after commit creation.

---

## Fix round 1

### Findings addressed

1. 自动记忆偏好采用 nullable 状态。首次 GET 失败时开关禁用且显示“状态未知”，只能重试读取；保存失败恢复已知服务端值。
2. 新增/编辑表单改为带 `role="dialog"`、`aria-modal`、Escape 关闭和焦点恢复的模态框。打开时聚焦首字段，删除成功后聚焦相邻记忆的编辑按钮或添加按钮。
3. 记忆客户端错误不再透传任意服务端 detail；`MemoryApiError` 仅发布 HTTP status 和固定 fallback。表单对 422 显示固定安全中文字段错误。
4. 记忆页局部改用深色已有 token，增强小字、边界、焦点、开关和保存按钮对比度；所有重试按钮最小 44px。
5. 列表初始错误与“加载更多”错误分离。分页失败保留已有卡片和 cursor，在页尾提供“重试加载更多”。
6. 新增 Node 直接执行的轻量运行时测试：验证真实客户端 URL/cursor 编码、POST body、偏好 wrapper、安全 status、旧请求失效、未知偏好状态和确认取消不触发删除。

### RED / GREEN evidence

初始运行时测试为 RED：客户端 422 返回 `private server body`，且 `memorySettingsState.ts` 不存在。后续焦点契约也先为 RED，证明原先 `focus()` 的 void 返回值会让 dialog 容器夺回首字段焦点。

GREEN：

```powershell
python -m unittest tests.test_memory_frontend_runtime tests.test_frontend_user_journey -v
# 10 tests passed

python -m unittest tests.test_memory_api tests.test_acceptance_workflow tests.test_backend_contracts -v
# 140 tests passed

Set-Location apps/web
npm run build
# vue-tsc -b && vite build exit 0

python -m unittest discover -s tests -p 'test_*.py'
# 319 tests passed
```

### Self-review and remaining risks

- 动效仍仅限 skeleton 的 opacity/transform（200ms），并保留 reduced-motion 分支；375px 下 dialog 和长文本无横向溢出。
- 无浏览器组件测试运行时，因此焦点和 dialog DOM 语义以 source contract、vue-tsc 与 Node 状态测试覆盖；真实认证会话中的键盘走查仍建议在合并前完成。

---

## Fix round 2

### Findings addressed

1. 表单使用原生 `<dialog>`、`showModal()` 和 `close()`；浏览器顶层模态机制会使背景不可交互。补上显式 Tab 首尾闭环、`cancel`/Escape/关闭/保存后的 close-event 焦点恢复，以及触发元素已移除时回退“添加记忆”按钮。
2. 保存成功直接把 create/update 返回的记忆同步进当前列表；若更新后的分类不再匹配筛选则移除该行，不再通过重新加载和 skeleton 卸载焦点目标。保存也会清除遗留的分页错误。
3. 非追加加载会清除分页错误；追加请求始终使用原 cursor，失败时保留现有卡片和 cursor，重试后只追加新页。
4. Node 运行时测试覆盖了焦点闭环、失效触发器回退、原 cursor、追加行、保存后的分页错误清理、本地新增/移除同步和原生 dialog 调用顺序；客户端契约也覆盖 PATCH、DELETE 与偏好 PUT body。

### Verification

```powershell
python -m unittest tests.test_memory_frontend_runtime tests.test_frontend_user_journey -v
# 13 tests passed

python -m unittest tests.test_memory_api tests.test_acceptance_workflow tests.test_backend_contracts -v
# 140 tests passed

Set-Location apps/web
npm run build
# vue-tsc -b && vite build exit 0

Set-Location ../..
python -m unittest discover -s tests -p 'test_*.py'
# 322 tests passed
```

### Self-review and remaining risk

- 未回退未知偏好、422 固定字段错误、高对比度、44px 控件、375px 布局、reduced-motion 或敏感信息不回显等既有保护。
- 自动化覆盖原生 dialog 的调用顺序和键盘边界；仍建议在目标浏览器的真实认证会话中进行一次最终人工键盘走查，以确认该浏览器的原生 top-layer 表现。

---

## Fix round 3

### Finding addressed

- 提取页面实际使用的 `createMemoryListCoordinator()`，统一列表请求版本、新增门禁和保存后的稳定状态。初始加载、筛选加载或初始错误时顶部“添加记忆”按钮具有原生 `disabled` 和 `aria-disabled`，错误态仅保留重试；首次成功列表后才可新增。
- 保存成功会先失效所有在途列表请求，再同步返回对象并把初始加载/初始错误/分页错误及加载更多状态归一化。列表的成功、失败和 finally 都只由当前 token 更新，迟到 GET 不能覆盖本地保存结果或重新遮住列表。
- 新增可执行的延迟 Promise 运行时回归测试：验证保存失效后旧 token 不可应用、错误态门禁关闭、成功态门禁开启和保存后的稳定状态；页面 source contract 同时证明顶部按钮与 submit 实际使用该协调器。

### Verification

```powershell
python -m unittest tests.test_memory_frontend_runtime tests.test_frontend_user_journey -v
# 15 tests passed

Set-Location apps/web
npm run build
# vue-tsc -b && vite build exit 0

Set-Location ../..
python -m unittest discover -s tests -p 'test_*.py'
# 324 tests passed
```

### Remaining risk

- 轻量测试不挂载 Vue 组件，但共享协调器的运行时断言与页面绑定契约同时覆盖关键时序；真实浏览器中的认证会话键盘走查仍是建议项。

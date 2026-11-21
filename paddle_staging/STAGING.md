# Paddle 集成候选版（默认关闭，未部署）

这一目录是供审阅和测试的候选代码。原项目已有未提交修改，生成器以当前文件为基准生成最小补丁，没有重置、覆盖或修改原项目。`candidate/` 是改动后的参考文件，不应直接覆盖未来版本。`source-fingerprints.json` 记录生成时的内容哈希；源文件变化后应重新生成并审阅补丁。

## 已准备

- FastAPI `/paddle/checkout`、`/paddle/access`、`/paddle/portal`、`/paddle/webhook` 与公开 `/checkout` 页面。
- 结账接口验证 Supabase 登录令牌和已验证邮箱；不接受浏览器提交的用户、客户、价格 ID。客户归属存入服务端绑定表。
- 原始请求验签；通知只保留权益字段，不保留邮箱、地址或付款卡信息。收到通知后先持久化入队，再回复成功。
- 独立 PostgreSQL 表和事务处理函数。支持去重、乱序保护、排队重试、退款与拒付处理、按已付款账期计算权益。
- `worker.py` 处理队列；`reconcile.py` 分页拉取最近事件补偿漏收，全部入队成功才推进检查点。
- 原有 LS 权益独立保留，Paddle 有效权益可通过关闭状态的开关叠加。iOS StoreKit 购买流程尚未调整。

## 测试依据

本地 `@electric-sql/pglite` 运行真实 PostgreSQL SQL/PLpgSQL，验证迁移、权益、退款、去重、乱序、重试和普通客户端角色无权访问。它不替代真实 Supabase 的迁移与 Auth 联调。

Python 接口测试通过项目已有虚拟环境执行：

```sh
/Users/megor/Developer/ai-chat-tool/.venv/bin/python -m unittest discover -s outputs/paddle-integration/tests -p 'test_*.py'
node outputs/paddle-integration/tests/database.mjs
```

Python 测试使用假 Auth/API 客户端；没有创建真实用户或扣款。旧 Sandbox 接收服务及其 SQLite 测试与本候选后端是不同服务，之前的模拟测试结果不能视为本后端已经在线验证。

## 部署到独立 staging 的顺序

1. 确认独立的 Supabase 测试项目及稳定 HTTPS 域名；不要把候选迁移直接应用到现有正式项目。
2. 在该测试项目先执行 `migrations/001_paddle.sql`，绑定测试 Auth 用户。表启用 RLS；所有表和 RPC 只允许服务端 service_role。
3. 将新模块复制到 staging 副本中，审阅 `integration.patch` 后合并。依赖沿用原项目的 requests、fastapi、supabase、uvicorn。SQL、worker 和 API 必须使用同一套 staging Supabase 凭据。
4. 按 `.env.example` 设置 Sandbox 环境，确认价格 ID 与 `paddle_prices` 表一致。Live 价格没有写入迁移，也没有创建。
5. 配置服务端 API key 权限：customer.read/write、transaction.read/write、customer_portal_session.write、notification.read。使用已有 Sandbox 密钥时需先补齐缺少的权限。通知验签本身不需要 API key 调用。
6. staging 中设置 `PADDLE_ENABLED=true`，保持 `PADDLE_ENV=sandbox`、`PADDLE_ALLOW_LIVE=false`。为 `/checkout` 设置匹配的公开 test_ client token。服务的请求访问日志不要记录 Authorization、门户 URL、完整查询字符串或通知正文。
7. Sandbox 默认结账地址指向稳定 `/checkout`，通知目标指向 `/paddle/webhook`。订阅 transaction.completed、transaction.payment_failed、subscription.created/updated/canceled/activated/paused/resumed/past_due、adjustment.created/updated。不要只用模拟数据的 ID 冒充真实用户绑定。
8. 每分钟运行 `python worker.py`；定期运行 `python reconcile.py`。第一次必须显式传 `--since` 起点，之后使用数据库检查点。超过 89 天或历史缺失需人工核对，不能视为自动补偿完成。
9. 确认 ingress/proxy 与 PostgREST 在 5 秒通知确认期限内工作；数据库不可用时返回 503 让 Paddle 重试。持续监测 inbox 的 pending、dead、最旧 received_at，以及 reconciliation 检查点。10 次失败的事件进入 dead，应处理根因后将 state 设回 pending、attempts 设为 0、available_at 设为 now()；不得删除事件或随意推进检查点。
10. 用真实 staging 登录会话测试本人结账、账户隔离、订阅开通、续费、取消、退款、拒付和服务中断后的补偿。然后再开启 staging 的 `PADDLE_MEMBERSHIP_ENABLED=true`。

## Streamlit 购买入口仍需联调

没有自动替换 `app.py` 的付款按钮：现有原生 iOS 入口有 StoreKit 处理，应保留；也不能在页面渲染时自动创建付款订单或发送用户邮箱。

网页版明确点击购买后，服务器调用 `session_action(supabase, user, 'checkout', 'premium')`（或 pass_30_day），再显示返回的 checkout URL。它将登录令牌放在后端 HTTPS Authorization 中，不放在 HTML 或 URL。调用必须发生在按钮点击后；不要放进每次 rerun 都执行的 URL getter。已有账号页面缓存应在付款返回或用户刷新时清除。

管理 Paddle 账单时明确点击按钮调用 `session_action(supabase,user,'portal')`，并直接打开新生成的 URL；不要复用 LS 的 get_customer_portal_url，也不要缓存 Paddle 门户链接。Paddle 权益可能与 LS 同时存在，两个账单入口须分别显示，防止用户误以为迁移已取消原订阅。

## 尚需确认的业务规则

- 本候选版不提供免费试用；past_due 不额外延长已付费账期。
- 全额退款或正式 chargeback 会剔除对应付款权益，独立有效的其他付款仍保留。
- 部分退款暂将对应交易的权益挂起，等待人工确定剩余权益；这是保守候选规则，上线前需确认。chargeback_reverse 不自动恢复旧权益，需人工核对。
- 退款不会自动取消后续订阅账单，取消订阅需在门户中处理；这样能防止把“退款一笔”误当作“取消所有未来续费”。
- 到期查询实时计算，不依赖定时任务来撤销已过期权益。Pass 叠加时长在退款后重新计算。
- 同一订阅同一时间戳的冲突状态和超出事件保留期的缺失数据需要人工核对／实体快照回补。本轮未实现完整历史账单迁移。

## 正式启用前

审批通过、正式域名和稳定后端部署、Live 专用商品价格／密钥／通知配置、独立 worker 与补偿调度、监测和告警、门户自助取消、真实小额付款验证、密钥轮换提醒都需要完成。只改 `PADDLE_ENV=live` 不足以安全上线。

回退：关闭购买入口与 `PADDLE_MEMBERSHIP_ENABLED`；不要删除账本，也不要停止已有付费订阅的通知和后台处理。审阅回退影响后再更改正式权益读取。

官方参考：[通知处理](https://developer.paddle.com/build/subscriptions/handle-webhooks)、[客户门户](https://developer.paddle.com/api-reference/customer-portals/create-customer-portal-session/)、[上线清单](https://developer.paddle.com/build/go-live-checklist/)。

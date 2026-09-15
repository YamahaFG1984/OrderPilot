# OrderPilot

面向中小跨境/外贸公司的轻量智能跟单工作台（MVP）。

当前版本打通了**采购单跟单主线**：主数据同步（模拟金蝶）→ 新建采购单 → 供应商门户确认交期 → 生产节点跟进 → 验货 → 出货确认，全程有延期预警、站内通知和操作记录。

架构设计见 [docs/architecture.md](docs/architecture.md)（或 GitHub Pages 页面）。

## 技术栈

Django 5.2 LTS · PostgreSQL 16 · Redis 7 · Celery 5（含 beat）· Django 模板 + htmx · uv

## 快速开始

```bash
# 1. 启动 PostgreSQL（5436）和 Redis（6381）
docker compose up -d --wait

# 2. 安装依赖、建表、导入演示数据
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo            # 账号使用随机密码，见 .demo-credentials
# 本地演示想用简单密码：seed_demo --simple-passwords（全部为 demo1234）
# 重建数据：seed_demo --reset

# 3. 启动 Web（终端 1）和 Celery worker + beat（终端 2）
uv run python manage.py runserver 8010
uv run celery -A config worker -B -Q default,sync,notify -c 1 -l info
```

打开 http://localhost:8010/ 。演示账号的密码是随机生成的，保存在项目根目录的 `.demo-credentials`（只有当前系统用户可读，用 `cat .demo-credentials` 查看）：

| 账号 | 角色 | 登录后看到 |
|---|---|---|
| `zhang` / `li` | 跟单员（内部） | 跟单看板、采购单、预警中心、ERP 同步 |
| `admin` | 管理员 | 同上，外加管理后台（主数据、预警规则阈值等） |
| `huamei` / `jiabao` / `yongxing` | 供应商 | 供应商门户：只看得到自己的采购单 |

> **公网访问时：** 保持 `ORDERPILOT_SHOW_DEMO_ACCOUNTS=false`（默认值，登录页不列出账号），并用 `uv run python manage.py rotate_demo_passwords` 定期更换密码，旧密码和已登录的会话会立即失效。只在本机演示时，可以在 `.env` 里把它设为 `true`，并用 `seed_demo --simple-passwords` 导入。

### 公网访问的安全设置

- 在 `.env` 里设置 `DJANGO_DEBUG=false`，把服务器 IP 或域名加入 `DJANGO_ALLOWED_HOSTS`，并使用随机的 `DJANGO_SECRET_KEY`。修改 `.env` 后要**完全重启**服务，开发服务器的自动重载不会重新读取 `.env`。
- 静态文件由 WhiteNoise 提供，关闭调试模式后样式照常加载，不需要 `--insecure`。
- 登录防暴力破解（django-axes）：同一用户名和 IP 连续失败 5 次，锁定 1 小时。可以用 `AXES_FAILURE_LIMIT`、`AXES_COOLOFF_HOURS` 调整；手动解锁：`uv run python manage.py axes_reset`。
- PostgreSQL 和 Redis 只监听 `127.0.0.1`。Docker 会绕过 ufw 防火墙，所以不能靠本机防火墙挡。
- 配好域名和 HTTPS 后设置 `DJANGO_HTTPS=true`，启用安全 Cookie、HTTPS 跳转和 HSTS。

## 演示脚本（约 10 分钟）

1. **跟单看板**（`zhang`）：顶部 KPI 显示跟进中、已逾期、未处理预警；看板卡片左边框颜色表示预警级别。
2. **逾期单**：打开红色边框的那张单，查看交期变更记录（供应商因"原料棉纱到货延迟"改过期）、超期的生产节点和操作时间线。
3. **新建并提交采购单**：新建 → 选供应商「南通华美家纺」→ 加商品 → 保存 → 提交给供应商。系统会通知供应商，并在后台把采购单推送到（模拟的）金蝶，详情页会显示 ERP 采购订单号。
4. **供应商确认**：换 `huamei` 登录门户 → 待确认交期 → 填写承诺交期确认；或"拒绝 / 要求改单"并写原因。之后可以更新生产节点、修改交期、上传资料。
5. **回到跟单员**：通知铃铛有新消息；预警中心可以"立即扫描"，也可以等后台每分钟自动扫描。
6. **客户扩展规则**：找到"待出货"的那张单，点"确认出货"，会被拦下，提示"本客户要求：出货前必须上传装箱单"。这条规则写在 `extensions/demo_jp/hooks.py` 里，没有修改核心代码。上传装箱单后即可出货。
7. **废番拦截**：草稿里有一张含旧款毛巾的单（金蝶中已禁用 → 同步为废番），提交时会被拦截。
8. **行级隔离**：用 `jiabao` 登录，看不到华美家纺的任何单据；直接改 URL 访问也会返回 404。

## 代码结构

```
config/                     Django 配置、Celery
orderpilot/platform/        平台基础（与业务无关）
  accounts/                 自定义 User、行级隔离 for_user()、权限谓词
  audit/                    操作日志（单据时间线）
  notifications/            站内信 + 邮件渠道（可注册新渠道）
  attachments/              附件，下载时校验权限
  integrations/             ERP 适配器接口、模拟金蝶适配器、同步任务、外部 ID 映射
  alerts/                   预警规则引擎（去重、自动解除、通知）
  workflow/                 状态机引擎、guard 扩展点、领域事件
  extensions/               扩展点注册表
orderpilot/trade/           跟单领域
  masterdata/               供应商、客户、商品（品番 / JAN / 废番）+ ERP 同步处理器
  purchasing/               采购单、状态机、生产节点、交期变更、预警规则、事件订阅
  shipping/                 出货记录
orderpilot/workbench/       内部工作台界面（+ seed_demo 命令）
orderpilot/portal/          供应商门户界面
extensions/demo_jp/         演示客户扩展（出货前必须上传装箱单）
tests/                      pytest
```

## 测试

```bash
docker compose up -d --wait     # 测试使用 PostgreSQL
uv run pytest
uv run ruff check .
```

## MVP 暂未包含

- 真实的金蝶云星空 WebAPI 适配器（接口已定义，需要测试账套）
- Excel 导入引擎、补货建议、发票/罚款结算
- 企业微信 / 钉钉通知渠道（渠道注册表已就绪）
- 日文界面翻译（i18n 已开启，模型字段已用 gettext 标注，模板尚未翻译）
- 生产部署配置（docker 镜像、nginx、备份）

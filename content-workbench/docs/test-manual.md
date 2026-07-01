# PenMoji 测试说明书

本文用于本地验收 PenMoji 工作台、同步服务和小程序采集端。当前版本用本地服务器模拟云端，可验证三端通路和主要业务流程；正式上云、正式授权、安装包升级不在本说明书范围内。

## 1. 测试范围

### 必测
- 桌面工作台启动、配置保存、服务状态显示。
- 本地云端同步服务启动。
- 桌面生成设备绑定码。
- 小程序输入或扫描设备码并绑定桌面。
- 小程序提交灵感后，桌面按设备拉取。
- 火花看板盲评、评分维度展示和排序。
- 演示样本链路：火花 -> 盲评分 -> 审核结果 -> 视频脚本 -> 发布文案。
- 素材标签进入对话框、标签删除、输入框自适应、左右栏折叠。
- 数据安全：小程序 project 配置不被改动，清理演示不删除普通历史。

### 不测
- 正式云端部署。
- 正式支付/授权服务。
- 微信线上域名白名单。
- 安装包、自动更新、生产数据库迁移。
- 真实抖音 API 或平台发布。

## 2. 测试环境

推荐环境：

- Windows 10/11
- Python 3.10+
- Node.js 18+
- 微信开发者工具
- 当前仓库路径：仓库根目录

默认端口：

- 桌面工作台：`http://127.0.0.1:7870`
- 本地同步服务：`http://127.0.0.1:8787`

如果端口被占用，可以换端口，但桌面设置和小程序设置里的同步地址必须保持一致。

## 3. 回滚点确认

测试前确认当前版本和回滚点：

```powershell
cd <repo-root>
git status --short --branch
git rev-parse --short HEAD
git tag --list before-penmoji-device-binding
```

期望：

- 工作区干净。
- 当前提交为设备绑定版本或其后续提交。
- 能看到 tag：`before-penmoji-device-binding`。

## 4. 自动检查

在仓库根目录运行：

```powershell
python -m py_compile content-workbench\main.py content-workbench\cloud_mock.py content-workbench\tools\mosmori_compliance_tests.py
node --check mobile-miniapp\pages\index\index.js
node -e "for (const f of ['mobile-miniapp/app.json','mobile-miniapp/pages/index/index.json','mobile-miniapp/project.config.json','mobile-miniapp/project.private.config.example.json']) { const s=require('fs').readFileSync(f,'utf8').replace(/^\uFEFF/,''); JSON.parse(s); } console.log('json ok')"
python content-workbench\tools\mosmori_compliance_tests.py
git diff --check -- mobile-miniapp content-workbench\cloud_mock.py content-workbench\main.py content-workbench\docs\mobile-cloud-contract.md content-workbench\static\index.html task_plan.md findings.md progress.md
git diff -- mobile-miniapp\project.config.json mobile-miniapp\project.private.config.example.json
```

期望：

- Python 编译无错误。
- 小程序 JS 无语法错误。
- JSON 检查输出 `json ok`。
- 合规测试输出 `status: pass`、`failed: []`。
- `git diff --check` 没有空白错误；Windows 换行 warning 可忽略。
- 小程序公开 project config 不包含个人 appid，private config 只保留 example 文件。

## 5. 启动本地同步服务

打开第一个 PowerShell：

```powershell
cd <repo-root>\content-workbench
python cloud_mock.py --host 127.0.0.1 --port 8787
```

期望终端出现：

```text
Content Workbench Cloud Mock 0.1.0 running at http://127.0.0.1:8787
```

浏览器访问：

```text
http://127.0.0.1:8787/api/status
```

期望返回 JSON，`status` 为 `ok`。

## 6. 启动桌面工作台

打开第二个 PowerShell：

```powershell
cd <repo-root>\content-workbench
python main.py --host 127.0.0.1 --port 7870
```

浏览器打开：

```text
http://127.0.0.1:7870
```

期望：

- 顶部显示产品名 `PenMoji`。
- 服务状态保持 `服务正常`。
- 布局为左侧火花、中间对话、右侧素材和产出。
- 设置入口在右上角齿轮。

## 7. 桌面端生成绑定码

步骤：

1. 打开右上角齿轮设置。
2. 在“手机同步地址”填写：

```text
http://127.0.0.1:8787
```

3. 保存配置。
4. 点击“生成绑定码”。

期望：

- 设置面板中出现 6 位设备码，例如 `A1B2C3`。
- 状态显示“等待小程序绑定”。
- 绑定链接显示 `/bind?code=...`。
- 顶部服务状态仍为 `服务正常`，不要被临时 toast 覆盖。

## 8. 小程序端绑定桌面

在微信开发者工具中导入：

```text
<repo-root>\mobile-miniapp
```

本地开发建议：

- 勾选“不校验合法域名、web-view 域名、TLS 版本以及 HTTPS 证书”。
- 如果用真机而不是开发者工具，`127.0.0.1` 指向手机自身，需改为电脑局域网 IP 或正式 HTTPS 地址。

步骤：

1. 打开小程序设置面板。
2. “开发同步地址”填写：

```text
http://127.0.0.1:8787
```

3. “电脑端设备码”输入桌面显示的 6 位设备码。
4. 点击“绑定电脑”。

期望：

- 小程序显示“已绑定电脑端：xxxxxxxx”。
- 桌面点击“检查绑定”后显示“已绑定小程序”。
- 错误码测试：
  - 输入不存在设备码，显示“设备码不存在，请检查后重试”。
  - 输入过期设备码，显示“设备码已过期，请在电脑端重新生成”。

## 9. 小程序提交灵感并同步到桌面

步骤：

1. 小程序选择内容类型，例如“文字灵感”或“链接”。
2. 输入一条测试灵感，例如：

```text
普通人做个人 IP 时，为什么总在前 7 天放弃？
```

3. 选择标签和处理意图，例如“评分”或“生成脚本”。
4. 点击“保存并同步”。
5. 回到桌面设置面板，点击“拉取手机灵感”。

期望：

- 小程序本地记录状态变为已同步或远端待处理。
- 桌面火花看板出现这条灵感。
- 灵感记录保留 `capture_intent`、`client_created_at` 和 `target_device_id`。
- 同一条灵感不会重复进入桌面 inbox。

## 10. 设备过滤验证

这个测试用于确认手机灵感只进入绑定的桌面。

简化验证方式：

1. 绑定一台桌面设备。
2. 用小程序提交灵感。
3. 桌面拉取，确认能看到。
4. 通过 API 提交一条带其他设备 ID 的灵感：

```powershell
$body = @{
  id = "wrong-device-test"
  content = "这条不应该被当前桌面拉到"
  target_device_id = "another-desktop"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8787/api/mobile/inspirations -ContentType "application/json" -Body $body
```

5. 当前桌面再次点击“拉取手机灵感”。

期望：

- 当前桌面不会拉到 `wrong-device-test`。
- 没有 `target_device_id` 的旧数据仍可被所有桌面看到，用作兼容旧版本手机端。

## 11. 火花看板和评分验证

步骤：

1. 在火花看板找到新同步的灵感。
2. 如果显示“待盲评”，点击盲评入口。
3. 等待评分完成。

期望：

- 卡片显示真实字段：`skill_score` 或兼容评分字段。
- 显示评分来源，例如“本地兼容评分”或“真实 blind-score”。
- 展示维度拆分和原因，不是前端估算分。
- 完成评分后火花看板自动排序，高分更靠前。

## 12. 演示业务链路验证

步骤：

1. 开启演示模式。
2. 点击演示火花。
3. 执行或查看链路产物：
   - 灵感固化卡
   - 审核结果
   - 视频脚本
   - 发布文案
   - 静态页文案
4. 点击右侧产出看板中的“打开 / 复制 / 继续生成”。

期望：

- 右侧优先展示当前火花链路产物。
- 普通历史产物不混入演示链路。
- 每类产物都有明确类型和动作。
- 清理演示只删除 demo metadata 或演示 manifest 匹配的数据，不删除普通历史。

## 13. 对话和素材交互验证

步骤：

1. 在右侧素材列表点击一个素材。
2. 确认素材以标签形式进入中间对话输入框。
3. 点击标签右上角 `x` 删除。
4. 输入多行文本，观察输入框高度变化。
5. 收起和展开火花栏、素材/产出栏。
6. 刷新页面。

期望：

- 素材选中逻辑不变。
- 对话框内标签可删除。
- 发送按钮尺寸正常，不被压窄成长条。
- 输入框查看历史时较小，输入时可自然变大。
- 左右栏默认打开；用户折叠后刷新能记住状态。

## 14. 产物文件验证

默认产物目录：

```text
%USERPROFILE%\.content-workbench\projects\default-content-project
```

验证：

- 生成脚本或文案后，右侧产出看板出现对应条目。
- 点击“打开”能打开文件。
- 点击“复制”能复制内容。
- 点击“继续生成”能把当前产物作为上下文继续进入对话。

期望产物类型至少包括：

- 灵感固化卡
- 审核结果
- 视频脚本
- 发布文案
- 静态页文案

## 15. 发布登记和复盘验证

步骤：

1. 生成一个发布预测或脚本。
2. 登记发布信息，例如平台、链接、发布时间。
3. 输入模拟数据做复盘，例如播放量、完播率、点赞、评论。

期望：

- 发布登记写入工作流记录。
- 复盘结果和预测记录关联。
- 已锁定预测内容不被复盘覆盖。
- 状态看板能看到待复盘和已复盘记录。

## 16. 暗夜主题验证

步骤：

1. 点击主题切换。
2. 切到暗夜主题。
3. 刷新页面。

期望：

- 暗夜主题保持。
- 对话框、素材区、产出区、设置面板没有白底突兀块。
- 输入框文字、按钮、评分标签可读。
- 顶部服务状态可见。

## 17. 通过标准

本轮验收通过需满足：

- 自动检查全部通过。
- 本地同步服务和桌面工作台均可启动。
- 桌面生成设备码，小程序能绑定，桌面能检查绑定状态。
- 小程序提交灵感后，桌面能按设备拉取。
- 火花评分读取后端字段并展示维度说明。
- 演示链路清晰，右侧产物不混入无关历史。
- 素材标签、输入框、折叠、主题等既有交互没有回归。
- project config 无意外修改。

## 18. 常见问题

### 小程序绑定失败

检查：

- 本地同步服务是否启动。
- 小程序“开发同步地址”是否和桌面“手机同步地址”一致。
- 设备码是否过期。
- 微信开发者工具是否关闭域名校验。

### 真机无法访问 `127.0.0.1`

真机上的 `127.0.0.1` 是手机自己，不是电脑。改用电脑局域网 IP，例如：

```text
http://192.168.x.x:8787
```

同时启动同步服务时可使用：

```powershell
python cloud_mock.py --host 0.0.0.0 --port 8787
```

### 桌面拉不到手机灵感

检查：

- 小程序是否已经绑定当前桌面。
- 小程序本地记录是否已同步。
- 桌面是否填写正确同步地址。
- 目标灵感是否带了其他 `target_device_id`。

### 页面显示旧数据

检查：

- 是否开启演示模式过滤。
- 是否需要点击“清理演示”。
- 普通历史数据不会被清理演示删除，这是预期行为。

### 需要回滚

安全查看设备绑定前版本：

```powershell
git switch -c rollback-check-before-device-binding before-penmoji-device-binding
```

这会新建一个临时分支，不会改写 `end` 分支。若要真正丢弃当前修改并回滚主分支，先确认工作区没有需要保留的内容，再单独执行回滚操作。

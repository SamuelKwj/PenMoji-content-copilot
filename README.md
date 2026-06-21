# PenMoji Content Copilot

PenMoji 是 Mosmori 出品的本地优先内容创作工作台，面向自媒体创作者、内容团队和个人 IP 运营者。它把零散灵感、素材、脚本、发布文案和复盘记录放进同一个工作流里，帮助用户从“想到一个点子”推进到“可发布、可复盘、可持续优化”的内容资产。

## GitHub Description

```text
PenMoji 是 Mosmori 出品的本地优先内容创作工作台，连接桌面工作台、小程序灵感采集和本地同步服务，把零散灵感推进为评分、审核、脚本、发布文案与复盘记录。
```

## 核心卖点

- 本地优先：用户数据、密钥、火花、对话和产物默认保存在本机，便于私有化演示和后续交付。
- 三端闭环：桌面工作台、小程序采集端、本地同步服务可以完整验证从手机灵感到桌面生产的链路。
- 火花评分：灵感进入火花看板后可盲评、展示维度分，并按分数排序，降低“凭感觉选题”的不确定性。
- 内容生产链路：支持灵感固化、审核结果、视频脚本、发布文案、静态页文案、发布登记和复盘。
- 演示友好：内置演示样本流，适合对外推介时讲清楚“灵感 -> 评分 -> 审核 -> 脚本 -> 发布文案”的价值链。
- 可扩展能力包：话题建议、发布时间建议等运营类技能可作为后续更新包接入，不挤进基础版。

## 项目结构

```text
content-workbench/       桌面工作台、本地 API 服务、本地同步服务和测试文档
mobile-miniapp/          微信小程序灵感采集端
task_plan.md             项目阶段计划
progress.md              开发进度记录
findings.md              产品决策和实现边界
HANDOFF.md               交接说明
```

## 桌面工作台启动

```powershell
cd C:\Users\samue\Documents\内容生产agent\content-workbench
python main.py --host 127.0.0.1 --port 7870
```

浏览器打开：

```text
http://127.0.0.1:7870
```

也可以双击：

```text
content-workbench\run.bat
```

## 本地同步服务启动

需要验证小程序到桌面端同步时，先启动本地云端模拟服务：

```powershell
cd C:\Users\samue\Documents\内容生产agent\content-workbench
python cloud_mock.py --host 127.0.0.1 --port 8787
```

桌面端设置里的“手机同步地址”填写：

```text
http://127.0.0.1:8787
```

桌面端生成绑定码后，小程序输入设备码即可绑定到当前桌面。绑定完成后，小程序提交的灵感会带上目标桌面设备 ID，桌面端按设备拉取。

## 小程序端

用微信开发者工具导入：

```text
C:\Users\samue\Documents\内容生产agent\mobile-miniapp
```

本地开发时建议开启“不校验合法域名、web-view 域名、TLS 版本以及 HTTPS 证书”。如果用真机调试，`127.0.0.1` 需要替换为电脑的局域网 IP 或正式 HTTPS 地址。

## 数据位置

运行数据保存在安装目录之外：

```text
%USERPROFILE%\.content-workbench
%USERPROFILE%\.content-workbench-cloud
```

这些目录不要上传到 GitHub。仓库里只保留源码、文档和演示/测试所需的静态资源。

## 测试

完整测试说明见：

```text
content-workbench\docs\test-manual.md
```

常用自动检查：

```powershell
python -m py_compile content-workbench\main.py content-workbench\cloud_mock.py content-workbench\tools\mosmori_compliance_tests.py
node --check mobile-miniapp\pages\index\index.js
python content-workbench\tools\mosmori_compliance_tests.py
```

## 当前边界

当前版本适合本地演示、业务流程验证和私有仓库维护。以下能力仍属于后续生产化范围：

- 正式云端同步服务
- 正式授权/订阅系统
- 安装包和自动升级
- 生产数据库与多用户权限
- 真实平台 API 发布

## 安全说明

- 不要提交 API Key、授权 token、微信密钥或本地用户数据。
- 不要提交 `%USERPROFILE%\.content-workbench` 和 `%USERPROFILE%\.content-workbench-cloud`。
- `mobile-miniapp/project.private.config.json` 如包含个人开发者配置，公开或多人协作前需检查。

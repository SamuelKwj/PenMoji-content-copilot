# Mosmori 工作台

`Mosmori` 是本地优先内容工作台，用来把零散灵感推进成可发布的脚本、文案和复盘记录。

工作台会在本机启动一个小型服务，并通过浏览器打开界面。核心能力包括：

- 火花收录与评分排序
- 引导式内容生产对话
- 素材选择与对话引用
- 抖音审稿与发布前检查
- 视频脚本、发布文案、静态页文案生成
- 发布登记、数据复盘和下一轮评分规则校准
- 本地文件产出看板
- 手机灵感同步验证
- 授权状态与模型配置入口

## 启动

```powershell
cd C:\Users\samue\Documents\内容生产agent\content-workbench
python main.py --host 127.0.0.1 --port 7870
```

也可以双击 `run.bat`。

如果要同时启动本地同步验证服务，双击 `run-mvp.bat`。

然后打开：

```text
http://127.0.0.1:7870
```

## 本地同步验证

需要验证手机灵感同步链路时，先启动：

```powershell
python cloud_mock.py --host 127.0.0.1 --port 8787
```

在工作台设置里填入：

```text
Cloud Base URL = http://127.0.0.1:8787
```

随后可以向 `POST http://127.0.0.1:8787/api/mobile/inspirations` 提交手机端灵感，再从桌面工作台拉取。

## 数据位置

运行数据保存在安装目录之外：

```text
%USERPROFILE%\.content-workbench
```

这会让用户配置、密钥、对话、火花和产物在升级时保持独立。

默认内容项目目录是：

```text
%USERPROFILE%\.content-workbench\projects\default-content-project
```

## 当前边界

当前版本用于本地演示、业务流程验证和客户推介。后续生产化还需要补正式云端同步、授权服务、安装包和升级流程。

## 密钥保护

`GET /api/config` 会返回脱敏后的 API Key。界面提交 `********` 时，服务会保留原有密钥，不会把密钥覆盖成星号。

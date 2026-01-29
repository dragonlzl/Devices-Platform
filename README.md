# 设备借用助手

基于 FastAPI + SQLite3 的设备借用管理系统，前端使用 React + TypeScript + Ant Design，并通过 Vite 构建静态资源。

## 功能概览
- 管理页：设备管理、厂商/系统配置、模型配置、待处理与借用记录
- 借用页：设备借用/延期、普通搜索与智能搜索
- 飞书通知：借用/归还/延期/逾期/待借通知（按配置触发）

## 运行环境
- Python 3.10+（建议）
- Node.js 18+（用于前端构建）

## 快速启动

### Windows
```bat
start_windows.bat
```
可选参数：`start_windows.bat [PORT] [DB_FILE] [PROJECT_DIR]`  
示例：`start_windows.bat 8090 app.db D:\Devices-Platform`

也可设置环境变量 `PHONETOOL_HOME` 指向项目目录，脚本会自动在该目录启动。

### macOS / Linux
```bash
bash start_mac.sh
```
可选参数：`bash start_mac.sh [PORT] [DB_FILE]`  
示例：`bash start_mac.sh 8090 app.db`

> 启动脚本会检测 `requirements.txt` 并安装依赖，然后启动后端服务。

## 手动启动（推荐了解）

1) 安装后端依赖
```bash
python3 -m pip install -r requirements.txt
```

2) 构建前端静态资源（首次或前端变更后需要）
```bash
cd frontend
npm install
npm run build
```

3) 启动后端服务
```bash
APP_DB_FILE=app.db uvicorn backend.main:app --reload --host 0.0.0.0 --port 8090
```

## 页面入口
- 管理页：`http://localhost:8090/admin`
- 借用页：`http://localhost:8090/borrow`

## 配置说明
- 数据库：通过 `APP_DB_FILE` 指定，如 `app.db` 或 `data/app.db`
- 飞书配置：复制 `feishu_config.example.json` 为 `feishu_config.json` 并填写 Webhook
- 模型配置：在管理页“模型配置”中设置模型与指派（更快/更准）

## 注意事项
- `feishu_config.json`、数据库文件、前端构建产物等已在 `.gitignore` 中忽略
- 如需提交到 GitHub，请勿提交包含敏感信息的配置文件

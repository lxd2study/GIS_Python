# Remote Sensing Tools Frontend (Vue3)

毕业设计前端操作台，技术栈：`Vue3 + Vite`。

## 功能

- 异步预处理任务提交（波段/MTL/QA/裁剪/合成/自定义公式）
- 输出路径弹窗选择（目录浏览，返回上级，选择当前目录）
- 任务进度轮询与步骤状态展示
- 结果产物列表与点击预览
- 栅格预览（调用后端 `/preview_raster`）

## 启动

```bash
npm install
npm run dev
```

默认地址：`http://127.0.0.1:5173`

## 环境变量

复制 `.env.example` 为 `.env`：

```bash
copy .env.example .env
```

按需修改：

```env
VITE_API_BASE_URL=http://127.0.0.1:5001
```

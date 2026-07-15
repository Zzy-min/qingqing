# 轻青 UI 重构实施计划 (Implementation Plan)

本计划旨在将轻青项目的 Flutter 客户端 UI 升级为高质量的响应式双端界面。我们将保持后端完全不动，仅重构前端界面结构和交互。

---

## 阶段一：基础架构与常量配置

在 `lib/src/` 中定义公共视觉常量：
1.  **文件创建**：新建 `lib/src/theme_constants.dart`，定义：
    *   主渐变色：`QingColors.primaryGradient` (绿青至浅蓝)
    *   主题色彩：`QingColors.musicBg`，`QingColors.musicText`，`QingColors.videoBg` 等
    *   圆角与阴影：`QingThemes.cardShadow`，`QingThemes.cardRadius`
    *   精美文本样式：`QingTextStyles.title`，`QingTextStyles.body`
2.  **静态/Mock 数据**：
    *   定义灵感社区 (Community Inspirations) 的 mock 列表，包含唱片图、点赞数、昵称、标题和类别。
    *   提供名人名言的随机轮换列表。

---

## 阶段二：数据流与底层接口封装

在 `lib/src/app_controller.dart` 中，原有逻辑保持不动，同时暴露新的 UI 需要的方法：
1.  **作品与创作历史拉取**：
    *   封装 `loadRuns()` 方法，调用 `GET /api/v1/agent/runs` 拉取最近任务列表。
    *   封装 `loadArtifacts()` 方法，调用 `GET /api/v1/artifacts` 拉取生成的结果文件。
2.  **创建音乐/视频任务**：
    *   封装 `createMusicRun({required String prompt, required String style, required String mood, required int seconds, required int count})`，将参数拼写为 Goal，并请求 `/api/v1/agent/runs`。
    *   封装 `createVideoRun({required String prompt, required String style, required String ratio, required int seconds, required int count})`，同上。
3.  **获取额度/权益**：
    *   封装 `loadEntitlements()`，请求 `/api/v1/me/entitlements`。

---

## 阶段三：窄屏视图 (Mobile) 页面实现

创建以下页面文件放入 `lib/src/pages/mobile/` 中：
1.  `splash_page.dart` (启动页)：
    *   渲染 Logo，中间水墨渐变背景，底部小船插画。
    *   提供“开启创作之旅”的圆角渐变按钮，点击后触发回调进入主系统或登录页。
2.  `mobile_home_page.dart` (移动端首页)：
    *   头部“Hi，今天想创作什么呢？”与右上角“会员中心”按钮。
    *   横排的三个功能入口卡片（音乐生成、图片生成、视频生成）。
    *   “灵感社区”横向卡片滚动。
    *   “我的创作”列表，可直接触发播放或查看状态。
3.  `music_gen_page.dart` & `video_gen_page.dart` (音乐/视频生成面板)：
    *   严格复刻参考图中的输入域（0/200 字数限制）。
    *   标签选择网格，选中状态高亮显示为绿字绿描边淡绿底色。
    *   底部“+ 生成音乐/视频”大按钮，附带消耗积分文案。
4.  `mobile_works_page.dart` (我的创作历史)：
    *   显示所有的 Run 记录，支持在 `awaiting_approval` 状态下显示估计费用及“批准”和“取消”按钮。
5.  `mobile_profile_page.dart` (我的/设置)：
    *   展示当前用户信息，会员限额（Entitlements）的进度条。
    *   入口：高级 API 配置（`AdvancedApiPage`）、常规设置（`SettingsPage`）、退出登录。

---

## 阶段四：宽屏视图 (Desktop/Web) 页面实现

创建以下页面文件放入 `lib/src/pages/desktop/` 中：
1.  `desktop_sidebar.dart` (左侧导航栏)：
    *   Logo、核心导航列表（首页、音乐生成、图片生成、视频生成等）。
    *   左下角“轻青Pro”推广小卡片。
    *   底部的用户头像与退出选项。
2.  `desktop_right_panel.dart` (右侧侧边栏)：
    *   创作工具箱（六个小工具图标）。
    *   最近使用（任务列表，带时间提示）。
    *   今日创作灵感卡片。
3.  `desktop_dashboard.dart` (桌面端主面板)：
    *   顶部搜索框（带 ⌘K 指示）和头部导航按钮。
    *   高颜值的 Banner 卡片。
    *   “热门工具”三栏卡片，点击可直接激活相应生成功能。
    *   “灵感社区”多分类选项卡和作品展示卡片网格。
    *   “我的作品”选项卡和作品展示列表。

---

## 阶段五：自适应 Shell 与路由重构

重构 `lib/src/qingqing_app.dart` 和 `lib/src/pages/login_page.dart`：
1.  **无缝登录**：
    *   LoginPage 重新设计，融合新配色和插画。
2.  **AppShell 组装**：
    *   在 `AppShell` 中，使用 `LayoutBuilder` 侦听窗口宽度：
        *   宽度 < 800px：显示底部导航栏形式的 `MobileShell`，可以切换 [首页、灵感、+ (拉起AgentPage)、作品、我的]。
        *   宽度 >= 800px：显示带有左导航、主内容、右侧栏的 `DesktopShell`。

---

## 阶段六：调试与验证

1.  **代码分析**：运行 `puro -e stable flutter analyze` 检查语法和类型。
2.  **响应式切换测试**：启动 Web 或 Windows 构建，通过缩放浏览器或应用窗口大小，观察并在宽/窄边界处平滑切换。
3.  **核心流贯通测试**：
    *   测试未登录时是否看到启动页与登录页。
    *   测试登录后首页是否正确拉取 Entitlements 并渲染最近任务。
    *   测试在音乐生成页选择参数提交，是否能正常创建任务，并显示在“我的作品”中。

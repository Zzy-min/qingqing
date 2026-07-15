import 'package:flutter/material.dart';

import 'app_controller.dart';
import 'pages/agent_page.dart';
import 'pages/login_page.dart';
import 'pages/settings_page.dart';
import 'pages/mobile/splash_page.dart';
import 'pages/mobile/mobile_home_page.dart';
import 'pages/mobile/music_gen_page.dart';
import 'pages/mobile/video_gen_page.dart';
import 'pages/mobile/mobile_works_page.dart';
import 'pages/mobile/mobile_profile_page.dart';
import 'pages/desktop/desktop_sidebar.dart';
import 'pages/desktop/desktop_right_panel.dart';
import 'pages/desktop/desktop_dashboard.dart';
import 'theme_constants.dart';

class QingQingApp extends StatefulWidget {
  const QingQingApp({
    super.key,
    required this.controller,
    this.showSplash = true,
  });
  final AppController controller;
  final bool showSplash;

  @override
  State<QingQingApp> createState() => _QingQingAppState();
}

class _QingQingAppState extends State<QingQingApp> {
  late bool _showSplash;

  @override
  void initState() {
    super.initState();
    _showSplash = widget.showSplash;
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final hasSession = widget.controller.authenticated;

        return MaterialApp(
          title: '轻青',
          debugShowCheckedModeBanner: false,
          theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(
              seedColor: const Color(0xff2cd9c5),
              brightness: Brightness.light,
            ),
            scaffoldBackgroundColor: const Color(0xfff7f9fc),
            useMaterial3: true,
          ),
          home: _showSplash
              ? SplashPage(
                  onStart: () {
                    setState(() => _showSplash = false);
                  },
                )
              : (hasSession
                    ? AppShell(controller: widget.controller)
                    : LoginPage(controller: widget.controller)),
        );
      },
    );
  }
}

class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.controller});
  final AppController controller;
  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int mobileIndex = 0;
  int desktopIndex = 0;

  @override
  void initState() {
    super.initState();
    // 同步当前账户的权益、跨端偏好和作品。
    widget.controller.loadEntitlements();
    widget.controller.loadPreferences();
    widget.controller.loadRuns();
    widget.controller.loadArtifacts();
  }

  void logout() => widget.controller.logout();

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 1024;

        if (wide) {
          return _buildDesktopLayout();
        } else {
          return _buildMobileLayout();
        }
      },
    );
  }

  // ==================== 移动端 (窄屏) 布局 ====================
  Widget _buildMobileLayout() {
    final List<Widget> mobilePages = [
      // 0: 首页
      MobileHomePage(
        controller: widget.controller,
        onNavigateToMusic: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => MusicGenPage(
                controller: widget.controller,
                onSuccess: () {
                  Navigator.maybePop(context);
                  setState(() => mobileIndex = 3); // 跳转至“作品”
                },
              ),
            ),
          );
        },
        onNavigateToVideo: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => VideoGenPage(
                controller: widget.controller,
                onSuccess: () {
                  Navigator.maybePop(context);
                  setState(() => mobileIndex = 3);
                },
              ),
            ),
          );
        },
        onNavigateToImage: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) =>
                  AgentPage(controller: widget.controller, capability: 'image'),
            ),
          );
        },
        onViewInspirations: () => setState(() => mobileIndex = 1),
        onViewAllWorks: () => setState(() => mobileIndex = 3),
      ),
      // 1: 社区
      Scaffold(
        appBar: AppBar(title: const Text('灵感社区'), centerTitle: true),
        body: ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: MockData.communityInspirations.length,
          itemBuilder: (context, idx) {
            final item = MockData.communityInspirations[idx];
            return Card(
              margin: const EdgeInsets.only(bottom: 12),
              color: Colors.white,
              child: ListTile(
                leading: Icon(item['icon'], color: item['color']),
                title: Text(
                  item['title'],
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
                subtitle: Text('by ${item['author']} · ${item['views']} 浏览'),
                trailing: Text(item['category']),
              ),
            );
          },
        ),
      ),
      // 2: 通用 Agent
      AgentPage(controller: widget.controller),
      // 3: 作品/任务列表
      MobileWorksPage(controller: widget.controller),
      // 4: 我的/个人中心
      MobileProfilePage(controller: widget.controller, onLogout: logout),
    ];

    return Scaffold(
      body: SafeArea(
        child: IndexedStack(index: mobileIndex, children: mobilePages),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: mobileIndex,
        onDestinationSelected: (value) => setState(() => mobileIndex = value),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home),
            label: '首页',
          ),
          NavigationDestination(
            icon: Icon(Icons.explore_outlined),
            selectedIcon: Icon(Icons.explore),
            label: '灵感',
          ),
          NavigationDestination(
            icon: Icon(Icons.add_circle_outline),
            selectedIcon: Icon(Icons.add_circle),
            label: '创作',
          ),
          NavigationDestination(
            icon: Icon(Icons.folder_open_outlined),
            selectedIcon: Icon(Icons.folder),
            label: '作品',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: '我的',
          ),
        ],
      ),
    );
  }

  // ==================== 桌面端 (宽屏) 布局 ====================
  Widget _buildDesktopLayout() {
    Widget centerPanel = const SizedBox();

    switch (desktopIndex) {
      case 0: // 首页
        centerPanel = DesktopDashboard(
          controller: widget.controller,
          onNavigateTo: (index) => setState(() => desktopIndex = index),
        );
        break;
      case 1: // 音乐生成
        centerPanel = Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 600),
            child: MusicGenPage(
              controller: widget.controller,
              onSuccess: () => setState(() => desktopIndex = 5), // 前往“我的作品”
            ),
          ),
        );
        break;
      case 2: // 图片生成 (即原有 AgentPage)
        centerPanel = Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 600),
            child: Scaffold(
              appBar: AppBar(title: const Text('图片生成'), centerTitle: true),
              body: AgentPage(
                controller: widget.controller,
                capability: 'image',
              ),
            ),
          ),
        );
        break;
      case 3: // 视频生成
        centerPanel = Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 600),
            child: VideoGenPage(
              controller: widget.controller,
              onSuccess: () => setState(() => desktopIndex = 5),
            ),
          ),
        );
        break;
      case 4: // 灵感社区
        centerPanel = Scaffold(
          appBar: AppBar(title: const Text('灵感社区')),
          body: ListView.builder(
            padding: const EdgeInsets.all(24),
            itemCount: MockData.communityInspirations.length,
            itemBuilder: (context, index) {
              final item = MockData.communityInspirations[index];
              return ListTile(
                leading: Icon(item['icon'], color: item['color']),
                title: Text(item['title']),
                subtitle: Text('社区示例 · by ${item['author']}'),
                trailing: Text(item['category']),
              );
            },
          ),
        );
        break;
      case 5: // 我的作品
        centerPanel = MobileWorksPage(controller: widget.controller);
        break;
      case 6: // 通用创作 Agent
        centerPanel = Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: AgentPage(controller: widget.controller),
          ),
        );
        break;
      case 7: // 设置
        centerPanel = SettingsPage(controller: widget.controller);
        break;
      default:
        centerPanel = DesktopDashboard(
          controller: widget.controller,
          onNavigateTo: (index) => setState(() => desktopIndex = index),
        );
    }

    final showRightPanel =
        MediaQuery.sizeOf(context).width >= 1280 &&
        (desktopIndex == 0 || desktopIndex == 4);

    return Scaffold(
      body: Row(
        children: [
          // 左侧导航
          DesktopSidebar(
            controller: widget.controller,
            selectedIndex: desktopIndex,
            onIndexChanged: (idx) => setState(() => desktopIndex = idx),
            onLogout: logout,
            onOpenSettings: () => setState(() => desktopIndex = 7),
          ),
          const VerticalDivider(width: 1, color: QingColors.cardBorder),

          // 中央控制面板
          Expanded(child: centerPanel),

          // 右侧侧边栏 (仅在首页显示，保证精细还原)
          if (showRightPanel) ...[
            const VerticalDivider(width: 1, color: QingColors.cardBorder),
            DesktopRightPanel(
              controller: widget.controller,
              onNavigateTo: (index) => setState(() => desktopIndex = index),
            ),
          ],
        ],
      ),
    );
  }
}

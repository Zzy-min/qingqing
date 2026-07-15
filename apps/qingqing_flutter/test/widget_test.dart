import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:qingqing/src/api_client.dart';
import 'package:qingqing/src/app_controller.dart';
import 'package:qingqing/src/pages/agent_page.dart';
import 'package:qingqing/src/pages/desktop/desktop_dashboard.dart';
import 'package:qingqing/src/pages/desktop/desktop_right_panel.dart';
import 'package:qingqing/src/pages/desktop/desktop_sidebar.dart';
import 'package:qingqing/src/pages/mobile/mobile_home_page.dart';
import 'package:qingqing/src/pages/mobile/mobile_profile_page.dart';
import 'package:qingqing/src/pages/login_page.dart';
import 'package:qingqing/src/pages/settings_page.dart';
import 'package:qingqing/src/qingqing_app.dart';

class _AgentApi extends ApiClient {
  int _runPolls = 0;

  @override
  Future<Map<String, dynamic>> request(
    String path, {
    String method = 'GET',
    Object? body,
    Map<String, String>? headers,
  }) async {
    if (path.startsWith('/api/v1/models')) {
      return {'models': <dynamic>[]};
    }
    if (path == '/api/v1/skills') {
      return {
        'skills': [
          {
            'id': 'social-copy',
            'name': '种草文案',
            'step_count': 1,
            'steps': [
              {'id': 'copy', 'capability': 'chat', 'title': '撰写文案'},
            ],
          },
        ],
      };
    }
    if (path == '/api/v1/agent/plans/preview') {
      return {
        'plan': {
          'skill_id': 'social-copy',
          'source': 'skill',
          'estimated_cost': 0.02,
          'steps': [
            {
              'id': 'copy',
              'capability': 'chat',
              'title': '撰写文案',
              'depends_on': <String>[],
            },
          ],
        },
      };
    }
    if (path == '/api/v1/agent/runs' && method == 'POST') {
      return {
        'id': 'run-1',
        'status': 'awaiting_approval',
        'estimated_cost': 1.0,
        'invocations': [
          {
            'model': {'display_name': '通用创作模型', 'provider': 'provider'},
            'routing_reason': '质量与成本平衡',
          },
        ],
      };
    }
    if (path == '/api/v1/agent/runs' && method == 'GET') {
      return {'runs': <dynamic>[]};
    }
    if (path.endsWith('/approve')) return {'id': 'run-1', 'status': 'planned'};
    if (path.endsWith('/execute')) return {'id': 'run-1', 'status': 'running'};
    if (path.endsWith('/cancel')) return {'id': 'run-1', 'status': 'cancelled'};
    if (path == '/api/v1/agent/runs/run-1') {
      _runPolls += 1;
      if (_runPolls < 2) {
        return {
          'id': 'run-1',
          'status': 'running',
          'invocations': [
            {
              'model': {'display_name': '通用创作模型', 'provider': 'provider'},
              'routing_reason': '质量与成本平衡',
            },
          ],
        };
      }
      return {
        'id': 'run-1',
        'status': 'completed',
        'invocations': [
          {
            'capability': 'chat',
            'model': {'display_name': '通用创作模型', 'provider': 'provider'},
            'routing_reason': '质量与成本平衡',
            'output': {'content': '这是模型完成后的真实输出'},
          },
        ],
      };
    }
    if (path == '/api/v1/artifacts') return {'artifacts': <dynamic>[]};
    if (path == '/api/v1/me/entitlements') {
      return {'plan': 'free', 'monthly_credit_limit': 100};
    }
    return <String, dynamic>{};
  }
}

class _LoginApi extends ApiClient {
  @override
  Future<Map<String, dynamic>> request(
    String path, {
    String method = 'GET',
    Object? body,
    Map<String, String>? headers,
  }) async {
    if (path == '/api/v1/auth/email/request-code') {
      return {'accepted': true, 'dev_code': '123456'};
    }
    return <String, dynamic>{};
  }
}

class _PreferencesApi extends ApiClient {
  String? savedCredentialPreference;

  @override
  Future<Map<String, dynamic>> request(
    String path, {
    String method = 'GET',
    Object? body,
    Map<String, String>? headers,
  }) async {
    if (path == '/api/v1/me/preferences' && method == 'PATCH') {
      final values = body! as Map<String, Object>;
      savedCredentialPreference =
          values['credential_preference']?.toString() ??
          savedCredentialPreference;
      return {
        'advanced_mode_enabled': true,
        'credential_preference': savedCredentialPreference ?? 'platform_first',
      };
    }
    if (path == '/api/v1/me/preferences') {
      return {
        'advanced_mode_enabled': true,
        'credential_preference': 'platform_first',
      };
    }
    if (path == '/api/v1/me/entitlements') return <String, dynamic>{};
    return <String, dynamic>{};
  }
}

void main() {
  testWidgets('starts with the shared email login experience', (tester) async {
    await tester.pumpWidget(
      QingQingApp(controller: AppController(), showSplash: false),
    );
    expect(find.text('登录轻青'), findsOneWidget);
    expect(find.text('获取验证码'), findsOneWidget);
    expect(find.text('跨设备同步你的创作任务'), findsOneWidget);
  });

  testWidgets('login remains within a 390 by 844 mobile viewport', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      QingQingApp(controller: AppController(), showSplash: false),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    final email = tester.getRect(find.byKey(const Key('email')));
    expect(email.left, greaterThanOrEqualTo(0));
    expect(email.right, lessThanOrEqualTo(390));
  });

  testWidgets(
    'desktop login exposes a visible primary action and enter submits',
    (tester) async {
      tester.view.physicalSize = const Size(1440, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          home: LoginPage(controller: AppController(api: _LoginApi())),
        ),
      );

      expect(find.byType(FilledButton), findsOneWidget);
      final action = tester.getRect(find.byType(FilledButton));
      expect(action.top, greaterThanOrEqualTo(0));
      expect(action.bottom, lessThanOrEqualTo(900));

      await tester.enterText(
        find.byKey(const Key('email')),
        'creator@example.com',
      );
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('code')), findsOneWidget);
      expect(find.text('登录并继续'), findsOneWidget);
    },
  );

  testWidgets(
    'first release hides membership marketing on mobile and desktop',
    (tester) async {
      final controller = AppController()..entitlements = {'plan': 'free'};

      await tester.pumpWidget(
        MaterialApp(
          home: MobileHomePage(
            controller: controller,
            onNavigateToMusic: () {},
            onNavigateToVideo: () {},
            onNavigateToImage: () {},
            onViewInspirations: () {},
            onViewAllWorks: () {},
          ),
        ),
      );
      expect(find.textContaining('会员'), findsNothing);
      expect(find.textContaining('升级'), findsNothing);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DesktopSidebar(
              controller: controller,
              selectedIndex: 0,
              onIndexChanged: (_) {},
              onLogout: () {},
            ),
          ),
        ),
      );
      expect(find.textContaining('会员'), findsNothing);
      expect(find.textContaining('升级'), findsNothing);
    },
  );

  testWidgets('advanced API entry is hidden until advanced mode is enabled', (
    tester,
  ) async {
    final controller = AppController()
      ..advancedMode = false
      ..entitlements = {
        'monthly_credit_limit': 100,
        'concurrent_run_limit': 1,
        'max_run_steps': 10,
      };
    await tester.pumpWidget(
      MaterialApp(
        home: MobileProfilePage(controller: controller, onLogout: () {}),
      ),
    );
    expect(find.text('API 密钥与自定义端点'), findsNothing);
  });

  testWidgets('agent shows transparent route and explicit budget approval', (
    tester,
  ) async {
    final controller = AppController(api: _AgentApi());
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(body: AgentPage(controller: controller)),
      ),
    );
    await tester.pump();
    await tester.enterText(find.byType(TextField).last, '制作一段产品介绍');
    await tester.tap(find.text('开始创作'));
    await tester.pumpAndSettle();
    expect(find.textContaining('需要确认'), findsOneWidget);
    expect(find.textContaining('通用创作模型'), findsOneWidget);
    expect(find.text('批准并执行'), findsOneWidget);
    await tester.tap(find.text('批准并执行'));
    await tester.pump();
    // Polling uses delayed futures; advance until completed output appears.
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 500));
      if (find.text('这是模型完成后的真实输出').evaluate().isNotEmpty) break;
    }
    expect(find.text('这是模型完成后的真实输出'), findsOneWidget);
    expect(find.textContaining('已完成'), findsOneWidget);
  });

  testWidgets('refactored desktop shell fits a 1024 by 768 viewport', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1024, 768);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final controller = AppController(api: _AgentApi())..authenticated = true;
    await tester.pumpWidget(
      MaterialApp(home: AppShell(controller: controller)),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('热门工具'), findsOneWidget);
  });

  testWidgets('refactored three-column shell fits a 1440 by 900 viewport', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final controller = AppController(api: _AgentApi())..authenticated = true;
    await tester.pumpWidget(
      MaterialApp(home: AppShell(controller: controller)),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('创作工具箱'), findsOneWidget);
  });

  testWidgets('mobile home inspiration and work shortcuts navigate', (
    tester,
  ) async {
    var inspirationOpened = false;
    var worksOpened = false;
    await tester.pumpWidget(
      MaterialApp(
        home: MobileHomePage(
          controller: AppController(),
          onNavigateToMusic: () {},
          onNavigateToVideo: () {},
          onNavigateToImage: () {},
          onViewInspirations: () => inspirationOpened = true,
          onViewAllWorks: () => worksOpened = true,
        ),
      ),
    );

    await tester.tap(find.byKey(const Key('mobile-inspirations-more')));
    await tester.tap(find.byKey(const Key('mobile-works-more')));
    expect(inspirationOpened, isTrue);
    expect(worksOpened, isTrue);
  });

  testWidgets('desktop toolbox and recent history shortcuts navigate', (
    tester,
  ) async {
    int? destination;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 280,
            height: 900,
            child: DesktopRightPanel(
              controller: AppController(),
              onNavigateTo: (value) => destination = value,
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('智能配乐'));
    expect(destination, 1);
    await tester.tap(find.text('查看全部记录 >'));
    expect(destination, 5);
  });

  testWidgets('desktop search routes by intent and notifications open', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    int? destination;
    final controller = AppController()
      ..activeRuns = [
        {'goal': '制作一段视频', 'status': 'running'},
      ];
    await tester.pumpWidget(
      MaterialApp(
        home: DesktopDashboard(
          controller: controller,
          onNavigateTo: (value) => destination = value,
        ),
      ),
    );

    await tester.enterText(find.byKey(const Key('desktop-search')), '视频扩展');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await tester.pumpAndSettle();
    expect(destination, 3);

    await tester.tap(find.byKey(const Key('desktop-notifications')));
    await tester.pumpAndSettle();
    expect(find.text('通知中心'), findsOneWidget);
    expect(find.textContaining('制作一段视频'), findsOneWidget);
  });

  testWidgets('settings follows the selected calm two-column design', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1440, 1024);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final controller = AppController()
      ..advancedMode = true
      ..credentialPreference = 'platform_first';

    await tester.pumpWidget(
      MaterialApp(home: SettingsPage(controller: controller)),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.text('你的模型连接，由你掌控'), findsOneWidget);
    expect(find.text('调用偏好'), findsOneWidget);
    expect(find.text('连接管理'), findsOneWidget);
    expect(find.text('使用说明'), findsOneWidget);
    expect(find.byKey(const Key('settings-hero-art')), findsOneWidget);
    final title = tester.widget<Text>(find.text('设置'));
    expect(title.style?.fontSize, lessThanOrEqualTo(28));
  });

  testWidgets('settings stays usable on mobile and saves API preference', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = _PreferencesApi();
    final controller = AppController(api: api)
      ..advancedMode = true
      ..credentialPreference = 'platform_first';

    await tester.pumpWidget(
      MaterialApp(home: SettingsPage(controller: controller)),
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);

    await tester.tap(find.text('仅使用我的 API'));
    await tester.pumpAndSettle();
    expect(api.savedCredentialPreference, 'byok_only');
    expect(controller.credentialPreference, 'byok_only');
  });

  testWidgets('settings desktop visual regression', (tester) async {
    tester.view.physicalSize = const Size(1440, 1024);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final controller = AppController(api: _PreferencesApi())
      ..authenticated = true
      ..advancedMode = true;

    await tester.pumpWidget(
      MaterialApp(home: AppShell(controller: controller)),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byType(PopupMenuButton<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('系统偏好设置'));
    await tester.pumpAndSettle();

    await expectLater(
      find.byType(AppShell),
      matchesGoldenFile('goldens/settings_page_desktop.png'),
    );
  });
}

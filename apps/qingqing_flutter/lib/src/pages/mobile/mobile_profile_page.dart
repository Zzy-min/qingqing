import 'package:flutter/material.dart';
import '../../app_controller.dart';
import '../../theme_constants.dart';
import '../advanced_api_page.dart';
import '../settings_page.dart';

class MobileProfilePage extends StatelessWidget {
  const MobileProfilePage({
    super.key,
    required this.controller,
    required this.onLogout,
  });
  final AppController controller;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final creditLimit = controller.entitlements?['monthly_credit_limit'];
        final concurrentLimit =
            controller.entitlements?['concurrent_run_limit'];

        return Scaffold(
          backgroundColor: QingColors.bgLight,
          appBar: AppBar(
            backgroundColor: Colors.white,
            elevation: 0,
            title: const Text(
              '个人中心',
              style: TextStyle(
                color: Color(0xFF2C3E50),
                fontWeight: FontWeight.bold,
              ),
            ),
            centerTitle: true,
          ),
          body: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // 用户卡片
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  gradient: QingColors.primaryGradient,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: QingColors.primaryGreen.withValues(alpha: 0.2),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: Row(
                  children: [
                    const CircleAvatar(
                      radius: 30,
                      backgroundColor: Colors.white,
                      child: Icon(
                        Icons.person,
                        size: 36,
                        color: QingColors.primaryBlue,
                      ),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            '轻风创作者',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              '创作者账户',
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.bold,
                                color: Colors.white,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),

              // 额度与资源限制卡片
              Card(
                elevation: 0,
                color: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: const BorderSide(
                    color: QingColors.cardBorder,
                    width: 0.5,
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '账户资源限额',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF2C3E50),
                        ),
                      ),
                      const SizedBox(height: 16),
                      // 额度
                      _buildQuotaRow(
                        label: '月度额度配额',
                        value: creditLimit?.toString() ?? '暂不可用',
                        icon: Icons.account_balance_wallet,
                      ),
                      const SizedBox(height: 12),
                      // 并发
                      _buildQuotaRow(
                        label: '并发任务限制',
                        value: concurrentLimit == null
                            ? '暂不可用'
                            : '$concurrentLimit 项',
                        icon: Icons.bolt,
                      ),
                      const SizedBox(height: 12),
                      // 步骤限制
                      _buildQuotaRow(
                        label: '单任务步骤限制',
                        value: controller.entitlements?['max_run_steps'] == null
                            ? '暂不可用'
                            : '${controller.entitlements?['max_run_steps']} 步',
                        icon: Icons.list,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),

              // 操作菜单
              Card(
                elevation: 0,
                color: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: const BorderSide(
                    color: QingColors.cardBorder,
                    width: 0.5,
                  ),
                ),
                child: Column(
                  children: [
                    // 设置
                    ListTile(
                      leading: const Icon(Icons.settings, color: Colors.grey),
                      title: const Text('系统偏好设置'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(
                            builder: (context) =>
                                SettingsPage(controller: controller),
                          ),
                        );
                      },
                    ),
                    if (controller.advancedMode) ...[
                      const Divider(height: 1),
                      // 高阶模式开启后才显示 API 与自定义模型配置。
                      ListTile(
                        leading: const Icon(Icons.api, color: Colors.grey),
                        title: const Text('API 密钥与自定义端点'),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (context) =>
                                  AdvancedApiPage(controller: controller),
                            ),
                          );
                        },
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(height: 20),

              // 退出登录按钮
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: Colors.red,
                  elevation: 0,
                  minimumSize: const Size.fromHeight(50),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(color: Colors.red.withValues(alpha: 0.2)),
                  ),
                ),
                onPressed: onLogout,
                icon: const Icon(Icons.exit_to_app),
                label: const Text('退出当前账号'),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildQuotaRow({
    required String label,
    required String value,
    required IconData icon,
  }) {
    return Row(
      children: [
        Icon(icon, size: 20, color: QingColors.primaryBlue),
        const SizedBox(width: 10),
        Text(
          label,
          style: const TextStyle(fontSize: 13, color: Color(0xFF7F8C8D)),
        ),
        const Spacer(),
        Text(
          value,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: Color(0xFF2C3E50),
          ),
        ),
      ],
    );
  }
}

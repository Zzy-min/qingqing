import 'package:flutter/material.dart';
import '../../app_controller.dart';
import '../../theme_constants.dart';
import '../advanced_api_page.dart';
import '../settings_page.dart';

class DesktopSidebar extends StatelessWidget {
  const DesktopSidebar({
    super.key,
    required this.controller,
    required this.selectedIndex,
    required this.onIndexChanged,
    required this.onLogout,
    this.onOpenSettings,
  });

  final AppController controller;
  final int selectedIndex;
  final ValueChanged<int> onIndexChanged;
  final VoidCallback onLogout;
  final VoidCallback? onOpenSettings;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        return Container(
          width: 240,
          color: Colors.white,
          child: Column(
            children: [
              // Logo 区域
              Padding(
                padding: const EdgeInsets.all(24.0),
                child: Row(
                  children: [
                    ShaderMask(
                      shaderCallback: (bounds) =>
                          QingColors.primaryGradient.createShader(bounds),
                      child: const Icon(
                        Icons.eco,
                        size: 32,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(width: 10),
                    const Text(
                      '轻青',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w900,
                        color: Color(0xFF2C3E50),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: QingColors.primaryGreen.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: const Text(
                        'AI 工作台',
                        style: TextStyle(
                          fontSize: 9,
                          fontWeight: FontWeight.bold,
                          color: QingColors.primaryGreen,
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              // 主导航菜单
              Expanded(
                child: ListView(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  children: [
                    _buildNavItem(0, Icons.home_outlined, Icons.home, '首页'),
                    _buildNavItem(
                      1,
                      Icons.music_note_outlined,
                      Icons.music_note,
                      '音乐生成',
                    ),
                    _buildNavItem(2, Icons.image_outlined, Icons.image, '图片生成'),
                    _buildNavItem(
                      3,
                      Icons.videocam_outlined,
                      Icons.videocam,
                      '视频生成',
                    ),
                    const SizedBox(height: 16),
                    const Padding(
                      padding: EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      child: Text(
                        '内容社区',
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.grey,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    _buildNavItem(
                      4,
                      Icons.explore_outlined,
                      Icons.explore,
                      '灵感社区',
                    ),
                    _buildNavItem(
                      5,
                      Icons.folder_open_outlined,
                      Icons.folder,
                      '我的作品',
                    ),
                  ],
                ),
              ),

              // 底部工具与用户信息区
              const Divider(height: 1),
              _buildBottomActionTile(context),
            ],
          ),
        );
      },
    );
  }

  Widget _buildNavItem(
    int index,
    IconData outlineIcon,
    IconData solidIcon,
    String title,
  ) {
    final isSelected = selectedIndex == index;
    return Padding(
      padding: const EdgeInsets.only(bottom: 4.0),
      child: InkWell(
        onTap: () => onIndexChanged(index),
        borderRadius: BorderRadius.circular(8),
        child: Ink(
          decoration: BoxDecoration(
            color: isSelected
                ? QingColors.primaryGreen.withValues(alpha: 0.1)
                : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
          ),
          child: SizedBox(
            height: 48,
            child: Row(
              children: [
                const SizedBox(width: 16),
                Icon(
                  isSelected ? solidIcon : outlineIcon,
                  color: isSelected
                      ? QingColors.primaryGreen
                      : const Color(0xFF7F8C8D),
                  size: 20,
                ),
                const SizedBox(width: 12),
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: isSelected
                        ? FontWeight.bold
                        : FontWeight.normal,
                    color: isSelected
                        ? QingColors.primaryGreen
                        : const Color(0xFF2C3E50),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildBottomActionTile(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: PopupMenuButton<String>(
        onSelected: (action) {
          if (action == 'settings') {
            if (onOpenSettings != null) {
              onOpenSettings!();
              return;
            }
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (context) => SettingsPage(controller: controller),
              ),
            );
          } else if (action == 'byok') {
            Navigator.push(
              context,
              MaterialPageRoute(
                builder: (context) => AdvancedApiPage(controller: controller),
              ),
            );
          } else if (action == 'logout') {
            onLogout();
          }
        },
        itemBuilder: (context) => [
          const PopupMenuItem(
            value: 'settings',
            child: Row(
              children: [
                Icon(Icons.settings, size: 18),
                SizedBox(width: 8),
                Text('系统偏好设置'),
              ],
            ),
          ),
          if (controller.advancedMode)
            const PopupMenuItem(
              value: 'byok',
              child: Row(
                children: [
                  Icon(Icons.api, size: 18),
                  SizedBox(width: 8),
                  Text('密钥与自定义模型'),
                ],
              ),
            ),
          const PopupMenuDivider(),
          const PopupMenuItem(
            value: 'logout',
            child: Row(
              children: [
                Icon(Icons.exit_to_app, color: Colors.red, size: 18),
                SizedBox(width: 8),
                Text('退出登录', style: TextStyle(color: Colors.red)),
              ],
            ),
          ),
        ],
        child: Row(
          children: [
            const CircleAvatar(
              radius: 18,
              backgroundColor: QingColors.primaryBlue,
              child: Icon(Icons.person, size: 20, color: Colors.white),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '轻风创作者',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF2C3E50),
                    ),
                  ),
                  const Text(
                    '创作者账户',
                    style: TextStyle(fontSize: 10, color: Colors.grey),
                  ),
                ],
              ),
            ),
            const Icon(Icons.more_vert, size: 16, color: Colors.grey),
          ],
        ),
      ),
    );
  }
}

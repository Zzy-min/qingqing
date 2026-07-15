import 'package:flutter/material.dart';
import '../../app_controller.dart';
import '../../theme_constants.dart';

class DesktopRightPanel extends StatelessWidget {
  const DesktopRightPanel({
    super.key,
    required this.controller,
    required this.onNavigateTo,
  });
  final AppController controller;
  final ValueChanged<int> onNavigateTo;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        return Container(
          width: 280,
          color: Colors.white,
          padding: const EdgeInsets.all(20.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // 创作工具箱
              const Text(
                '创作工具箱',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF2C3E50),
                ),
              ),
              const SizedBox(height: 16),
              // 网格展示工具箱小卡片
              GridView.count(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: 3,
                mainAxisSpacing: 10,
                crossAxisSpacing: 10,
                childAspectRatio: 0.85,
                children: [
                  _buildToolItem(
                    Icons.library_music_outlined,
                    QingColors.musicText,
                    '智能配乐',
                    () => onNavigateTo(1),
                  ),
                  _buildToolItem(
                    Icons.text_fields,
                    QingColors.musicText,
                    '歌词生成',
                    () => onNavigateTo(1),
                  ),
                  _buildToolItem(
                    Icons.transform,
                    QingColors.imageText,
                    '风格迁移',
                    () => onNavigateTo(2),
                  ),
                  _buildToolItem(
                    Icons.photo_filter,
                    QingColors.imageText,
                    '画质增强',
                    () => onNavigateTo(2),
                  ),
                  _buildToolItem(
                    Icons.video_library_outlined,
                    QingColors.videoText,
                    '视频扩展',
                    () => onNavigateTo(3),
                  ),
                  _buildToolItem(
                    Icons.more_horiz,
                    Colors.grey,
                    '更多工具',
                    () => onNavigateTo(6),
                  ),
                ],
              ),
              const SizedBox(height: 28),

              // 最近使用
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    '最近使用',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF2C3E50),
                    ),
                  ),
                  TextButton(
                    onPressed: () => onNavigateTo(5),
                    child: const Text(
                      '查看全部记录 >',
                      style: TextStyle(fontSize: 11, color: Color(0xFF7F8C8D)),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              // 最近使用列表
              Expanded(child: _buildRecentHistoryList(context)),
              const SizedBox(height: 20),

              // 今日创作灵感
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      QingColors.primaryGreen.withValues(alpha: 0.04),
                      QingColors.primaryBlue.withValues(alpha: 0.04),
                    ],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: QingColors.cardBorder),
                ),
                child: const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      Icons.format_quote,
                      color: QingColors.primaryGreen,
                      size: 28,
                    ),
                    SizedBox(height: 8),
                    Text(
                      '音乐是心灵的语言，\nAI 是你的创作伙伴。',
                      style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF5F6C7D),
                        height: 1.6,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildToolItem(
    IconData icon,
    Color color,
    String label,
    VoidCallback onTap,
  ) {
    return Container(
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 4.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, color: color, size: 20),
                const SizedBox(height: 6),
                Text(
                  label,
                  textAlign: TextAlign.center,
                  maxLines: 1,
                  style: const TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF2C3E50),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildRecentHistoryList(BuildContext context) {
    final runs = controller.activeRuns;
    final artifacts = controller.artifacts;

    if (runs.isEmpty && artifacts.isEmpty) {
      return const Center(
        child: Text(
          '暂无创作记录',
          style: TextStyle(color: Colors.grey, fontSize: 12),
        ),
      );
    }

    final list = <Widget>[];

    for (var r in runs.take(3)) {
      final isMusic = r['routing_snapshot']?['capability'] == 'music';
      final isVideo = r['routing_snapshot']?['capability'] == 'video';
      final label = isMusic
          ? '音乐生成'
          : isVideo
          ? '视频生成'
          : '智能创作';
      final timeStr =
          r['created_at']?.split('T')?.last?.substring(0, 5) ?? '刚刚';

      list.add(
        _buildRecentTile(
          label,
          r['goal'] ?? '',
          timeStr,
          isMusic
              ? QingColors.musicText
              : isVideo
              ? QingColors.videoText
              : QingColors.imageText,
          isMusic
              ? Icons.music_note
              : isVideo
              ? Icons.videocam
              : Icons.auto_awesome,
        ),
      );
    }

    for (var art in artifacts.take(3)) {
      if (list.length >= 5) break;
      final kind = art['kind']?.toString() ?? 'image';
      final isAudio = kind == 'audio';
      final isVideo = kind == 'video';

      list.add(
        _buildRecentTile(
          isAudio
              ? '音乐生成'
              : isVideo
              ? '视频生成'
              : '图片生成',
          isAudio ? '音频作品' : (isVideo ? '视频作品' : '图片作品'),
          '已生成',
          isAudio
              ? QingColors.musicText
              : isVideo
              ? QingColors.videoText
              : QingColors.imageText,
          isAudio
              ? Icons.music_note
              : isVideo
              ? Icons.videocam
              : Icons.image,
        ),
      );
    }

    return ListView(children: list);
  }

  Widget _buildRecentTile(
    String title,
    String desc,
    String time,
    Color color,
    IconData icon,
  ) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12.0),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(icon, color: color, size: 16),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF2C3E50),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  desc,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 11, color: Colors.grey),
                ),
              ],
            ),
          ),
          Text(time, style: const TextStyle(fontSize: 10, color: Colors.grey)),
        ],
      ),
    );
  }
}

import 'package:flutter/material.dart';
import '../../app_controller.dart';
import '../../theme_constants.dart';

class MobileHomePage extends StatelessWidget {
  const MobileHomePage({
    super.key,
    required this.controller,
    required this.onNavigateToMusic,
    required this.onNavigateToVideo,
    required this.onNavigateToImage,
    required this.onViewInspirations,
    required this.onViewAllWorks,
  });

  final AppController controller;
  final VoidCallback onNavigateToMusic;
  final VoidCallback onNavigateToVideo;
  final VoidCallback onNavigateToImage;
  final VoidCallback onViewInspirations;
  final VoidCallback onViewAllWorks;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        return Scaffold(
          backgroundColor: QingColors.bgLight,
          body: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 顶部导航/欢迎区
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text(
                            '轻青',
                            style: TextStyle(
                              fontSize: 26,
                              fontWeight: FontWeight.w900,
                              color: Color(0xFF2C3E50),
                            ),
                          ),
                          const SizedBox(height: 4),
                          const Text(
                            'Hi，今天想创作什么呢？',
                            style: TextStyle(
                              fontSize: 14,
                              color: Color(0xFF7F8C8D),
                            ),
                          ),
                        ],
                      ),
                      const Icon(
                        Icons.auto_awesome,
                        color: QingColors.primaryGreen,
                      ),
                    ],
                  ),
                  const SizedBox(height: 24),

                  // 三大入口卡片
                  Row(
                    children: [
                      Expanded(
                        child: _buildEntranceCard(
                          context,
                          title: '音乐生成',
                          subtitle: 'AI 生成音乐',
                          icon: Icons.music_note,
                          bgColor: QingColors.musicBg,
                          iconColor: QingColors.musicText,
                          onTap: onNavigateToMusic,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildEntranceCard(
                          context,
                          title: '图片生成',
                          subtitle: 'AI 生成图片',
                          icon: Icons.image,
                          bgColor: QingColors.imageBg,
                          iconColor: QingColors.imageText,
                          onTap: onNavigateToImage,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: _buildEntranceCard(
                          context,
                          title: '视频生成',
                          subtitle: 'AI 生成视频',
                          icon: Icons.videocam,
                          bgColor: QingColors.videoBg,
                          iconColor: QingColors.videoText,
                          onTap: onNavigateToVideo,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 28),

                  // 灵感社区段落
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        '灵感社区',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF2C3E50),
                        ),
                      ),
                      TextButton(
                        key: const Key('mobile-inspirations-more'),
                        onPressed: onViewInspirations,
                        child: const Row(
                          children: [
                            Text(
                              '更多',
                              style: TextStyle(
                                fontSize: 13,
                                color: Color(0xFF7F8C8D),
                              ),
                            ),
                            Icon(
                              Icons.chevron_right,
                              size: 16,
                              color: Color(0xFF7F8C8D),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),

                  // 灵感社区横向滚动卡片
                  SizedBox(
                    height: 160,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: MockData.communityInspirations.length,
                      separatorBuilder: (context, _) =>
                          const SizedBox(width: 12),
                      itemBuilder: (context, index) {
                        final item = MockData.communityInspirations[index];
                        return _buildInspirationCard(context, item);
                      },
                    ),
                  ),
                  const SizedBox(height: 28),

                  // 我的创作段落
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text(
                        '我的创作',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF2C3E50),
                        ),
                      ),
                      TextButton(
                        key: const Key('mobile-works-more'),
                        onPressed: onViewAllWorks,
                        child: const Row(
                          children: [
                            Text(
                              '更多',
                              style: TextStyle(
                                fontSize: 13,
                                color: Color(0xFF7F8C8D),
                              ),
                            ),
                            Icon(
                              Icons.chevron_right,
                              size: 16,
                              color: Color(0xFF7F8C8D),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),

                  // 我的创作列表
                  _buildMyCreationsList(context),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildEntranceCard(
    BuildContext context, {
    required String title,
    required String subtitle,
    required IconData icon,
    required Color bgColor,
    required Color iconColor,
    required VoidCallback onTap,
  }) {
    return Container(
      height: 120,
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(16),
          child: Padding(
            padding: const EdgeInsets.all(14.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: const BoxDecoration(
                    color: Colors.white,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(icon, size: 20, color: iconColor),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        color: iconColor,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      subtitle,
                      style: TextStyle(
                        fontSize: 10,
                        color: iconColor.withValues(alpha: 0.6),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildInspirationCard(
    BuildContext context,
    Map<String, dynamic> item,
  ) {
    return Container(
      width: 130,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: QingThemes.cardShadow,
        border: Border.all(color: QingColors.cardBorder, width: 0.5),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 卡片封面（使用渐变配彩色图标作为 Mock 图片）
            Expanded(
              flex: 5,
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      item['color'].withOpacity(0.1),
                      item['color'].withOpacity(0.2),
                    ],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                ),
                child: Center(
                  child: Icon(item['icon'], size: 32, color: item['color']),
                ),
              ),
            ),
            // 卡片信息
            Expanded(
              flex: 4,
              child: Padding(
                padding: const EdgeInsets.all(8.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      item['title'],
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF2C3E50),
                      ),
                    ),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 6,
                            vertical: 2,
                          ),
                          decoration: BoxDecoration(
                            color: item['color'].withOpacity(0.1),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            item['category'],
                            style: TextStyle(
                              fontSize: 9,
                              color: item['color'],
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        Row(
                          children: [
                            const Icon(
                              Icons.play_arrow,
                              size: 10,
                              color: Color(0xFF7F8C8D),
                            ),
                            Text(
                              item['views'],
                              style: const TextStyle(
                                fontSize: 9,
                                color: Color(0xFF7F8C8D),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMyCreationsList(BuildContext context) {
    final hasActive = controller.activeRuns.isNotEmpty;
    final hasArtifacts = controller.artifacts.isNotEmpty;

    if (!hasActive && !hasArtifacts) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 20),
        child: Center(child: Text('还没有作品，从上方选择一种方式开始创作吧。')),
      );
    }

    final items = <Widget>[];

    // 添加正在进行的 Runs
    for (var r in controller.activeRuns.take(3)) {
      final isMusic = r['routing_snapshot']?['capability'] == 'music';
      final isVideo = r['routing_snapshot']?['capability'] == 'video';
      final isImage = r['routing_snapshot']?['capability'] == 'image';

      final String typeLabel = isMusic
          ? '音乐'
          : isVideo
          ? '视频'
          : isImage
          ? '图片'
          : 'Chat';
      final String timeLabel = r['created_at']?.split('T')?.first ?? '刚刚';

      items.add(
        _buildCreationTile(
          context,
          title: r['goal'] ?? '无标题创作',
          subtitle: '$typeLabel · $timeLabel · 状态: ${r['status']}',
          icon: isMusic
              ? Icons.music_note
              : isVideo
              ? Icons.videocam
              : isImage
              ? Icons.image
              : Icons.auto_awesome,
          iconBg: isMusic
              ? QingColors.musicBg
              : isVideo
              ? QingColors.videoBg
              : QingColors.imageBg,
          iconColor: isMusic
              ? QingColors.musicText
              : isVideo
              ? QingColors.videoText
              : QingColors.imageText,
          trailing: r['status'] == 'awaiting_approval'
              ? ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    backgroundColor: Colors.amber,
                    foregroundColor: Colors.white,
                  ),
                  onPressed: () => controller.approveRun(r['id']),
                  child: const Text('审批', style: TextStyle(fontSize: 10)),
                )
              : null,
        ),
      );
      items.add(const SizedBox(height: 8));
    }

    // 添加静态 artifacts (如果 activeRuns 不够多)
    if (items.length < 4) {
      for (var art in controller.artifacts.take(3)) {
        final String kind = art['kind']?.toString() ?? 'image';
        final String type = kind == 'audio'
            ? '音频'
            : (kind == 'video' ? '视频' : '图片');
        final String title = '$type作品';
        final String time = art['created_at']?.split('T')?.first ?? '';

        items.add(
          _buildCreationTile(
            context,
            title: title,
            subtitle: '$type · $time',
            icon: type == '音频'
                ? Icons.music_note
                : type == '视频'
                ? Icons.videocam
                : Icons.image,
            iconBg: type == '音频'
                ? QingColors.musicBg
                : type == '视频'
                ? QingColors.videoBg
                : QingColors.imageBg,
            iconColor: type == '音频'
                ? QingColors.musicText
                : type == '视频'
                ? QingColors.videoText
                : QingColors.imageText,
          ),
        );
        items.add(const SizedBox(height: 8));
      }
    }

    return Column(children: items);
  }

  Widget _buildCreationTile(
    BuildContext context, {
    required String title,
    required String subtitle,
    required IconData icon,
    required Color iconBg,
    required Color iconColor,
    Widget? trailing,
  }) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: QingThemes.cardShadow,
        border: Border.all(color: QingColors.cardBorder, width: 0.5),
      ),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        leading: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: iconBg,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, size: 20, color: iconColor),
        ),
        title: Text(
          title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: Color(0xFF2C3E50),
          ),
        ),
        subtitle: Text(
          subtitle,
          style: const TextStyle(fontSize: 11, color: Color(0xFF7F8C8D)),
        ),
        trailing:
            trailing ??
            IconButton(
              icon: Icon(
                icon == Icons.music_note
                    ? Icons.play_circle_outline
                    : Icons.more_vert,
                color: const Color(0xFFBDC3C7),
              ),
              onPressed: () {
                onViewAllWorks();
              },
            ),
      ),
    );
  }
}

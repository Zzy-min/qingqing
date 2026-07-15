import 'package:flutter/material.dart';
import '../../app_controller.dart';
import '../../theme_constants.dart';

class DesktopDashboard extends StatefulWidget {
  const DesktopDashboard({
    super.key,
    required this.controller,
    required this.onNavigateTo,
  });

  final AppController controller;
  final ValueChanged<int> onNavigateTo;

  @override
  State<DesktopDashboard> createState() => _DesktopDashboardState();
}

class _DesktopDashboardState extends State<DesktopDashboard>
    with TickerProviderStateMixin {
  late TabController _communityTab;
  late TabController _worksTab;
  final searchInput = TextEditingController();

  @override
  void initState() {
    super.initState();
    _communityTab = TabController(length: 4, vsync: this);
    _worksTab = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _communityTab.dispose();
    _worksTab.dispose();
    searchInput.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        return Scaffold(
          backgroundColor: QingColors.bgLight,
          body: Column(
            children: [
              // 顶栏 (Search & Header buttons)
              _buildTopHeader(context),

              // 主体滚动区域
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 32.0,
                    vertical: 24.0,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // 大 Banner 卡片
                      _buildBannerCard(context),
                      const SizedBox(height: 32),

                      // 热门工具
                      const Text(
                        '热门工具',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFF2C3E50),
                        ),
                      ),
                      const SizedBox(height: 16),
                      Row(
                        children: [
                          Expanded(
                            child: _buildToolCard(
                              title: '音乐生成',
                              desc: 'AI 作曲，支持多种风格与情绪',
                              btnText: '开始创作',
                              btnColor: QingColors.musicText,
                              bgColor: Colors.white,
                              icon: Icons.music_note,
                              onTap: () => widget.onNavigateTo(1),
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: _buildToolCard(
                              title: '图片生成',
                              desc: '输入描述，生成精美图片',
                              btnText: '开始创作',
                              btnColor: QingColors.imageText,
                              bgColor: Colors.white,
                              icon: Icons.image,
                              onTap: () => widget.onNavigateTo(2),
                            ),
                          ),
                          const SizedBox(width: 16),
                          Expanded(
                            child: _buildToolCard(
                              title: '视频生成',
                              desc: '文字或图片生成精彩视频',
                              btnText: '开始创作',
                              btnColor: QingColors.videoText,
                              bgColor: Colors.white,
                              icon: Icons.videocam,
                              onTap: () => widget.onNavigateTo(3),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 32),

                      // 灵感社区卡片网格
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
                            onPressed: () => widget.onNavigateTo(4),
                            child: const Text(
                              '查看更多 >',
                              style: TextStyle(
                                color: Colors.grey,
                                fontSize: 13,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      TabBar(
                        controller: _communityTab,
                        isScrollable: true,
                        dividerColor: Colors.transparent,
                        indicatorColor: QingColors.primaryGreen,
                        labelColor: QingColors.primaryGreen,
                        unselectedLabelColor: Colors.grey,
                        tabs: const [
                          Tab(text: '精选'),
                          Tab(text: '音乐'),
                          Tab(text: '图片'),
                          Tab(text: '视频'),
                        ],
                      ),
                      const SizedBox(height: 16),
                      // 社区网格
                      _buildCommunityGrid(context),
                      const SizedBox(height: 32),

                      // 我的作品列表
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            '我的作品',
                            style: TextStyle(
                              fontSize: 18,
                              fontWeight: FontWeight.bold,
                              color: Color(0xFF2C3E50),
                            ),
                          ),
                          TextButton(
                            onPressed: () => widget.onNavigateTo(5),
                            child: const Text(
                              '查看更多 >',
                              style: TextStyle(
                                color: Colors.grey,
                                fontSize: 13,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      TabBar(
                        controller: _worksTab,
                        isScrollable: true,
                        dividerColor: Colors.transparent,
                        indicatorColor: QingColors.primaryBlue,
                        labelColor: QingColors.primaryBlue,
                        unselectedLabelColor: Colors.grey,
                        tabs: const [
                          Tab(text: '全部'),
                          Tab(text: '音乐'),
                          Tab(text: '图片'),
                          Tab(text: '视频'),
                        ],
                      ),
                      const SizedBox(height: 16),
                      _buildMyWorksGrid(context),
                    ],
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildTopHeader(BuildContext context) {
    return Container(
      height: 72,
      color: Colors.white,
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Row(
        children: [
          // 搜索框
          Container(
            width: 320,
            height: 40,
            decoration: BoxDecoration(
              color: QingColors.bgLight,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: QingColors.cardBorder),
            ),
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Row(
              children: [
                const Icon(Icons.search, size: 18, color: Colors.grey),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    key: const Key('desktop-search'),
                    controller: searchInput,
                    textInputAction: TextInputAction.search,
                    onSubmitted: _handleSearch,
                    decoration: const InputDecoration(
                      hintText: '搜索灵感、作品或功能',
                      hintStyle: TextStyle(fontSize: 13, color: Colors.grey),
                      border: InputBorder.none,
                      isDense: true,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 6,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(
                      color: Colors.grey.withValues(alpha: 0.3),
                    ),
                  ),
                  child: const Text(
                    '⌘K',
                    style: TextStyle(fontSize: 10, color: Colors.grey),
                  ),
                ),
              ],
            ),
          ),
          const Spacer(),

          // 通知铃铛
          IconButton(
            key: const Key('desktop-notifications'),
            icon: const Icon(
              Icons.notifications_none,
              color: Color(0xFF2C3E50),
            ),
            onPressed: () => _showNotifications(context),
          ),
          const SizedBox(width: 12),

          // 用户头像
          const CircleAvatar(
            radius: 16,
            backgroundColor: QingColors.primaryBlue,
            child: Icon(Icons.person, size: 18, color: Colors.white),
          ),
        ],
      ),
    );
  }

  void _handleSearch(String rawQuery) {
    final query = rawQuery.trim().toLowerCase();
    if (query.isEmpty) return;

    final destination = switch (query) {
      String value when value.contains('音乐') || value.contains('歌词') => 1,
      String value
          when value.contains('图片') ||
              value.contains('风格') ||
              value.contains('画质') =>
        2,
      String value when value.contains('视频') => 3,
      String value when value.contains('灵感') || value.contains('社区') => 4,
      String value when value.contains('作品') || value.contains('记录') => 5,
      _ => null,
    };

    if (destination != null) {
      widget.onNavigateTo(destination);
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('未找到“${rawQuery.trim()}”，请尝试音乐、图片、视频或作品。')),
    );
  }

  void _showNotifications(BuildContext context) {
    final runs = widget.controller.activeRuns.take(5).toList();
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '通知中心',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 12),
              if (runs.isEmpty)
                const ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(Icons.notifications_none),
                  title: Text('暂无新通知'),
                )
              else
                ...runs.map(
                  (run) => ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: const Icon(Icons.auto_awesome),
                    title: Text(
                      run['goal']?.toString() ?? '创作任务',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text('状态：${run['status'] ?? '未知'}'),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBannerCard(BuildContext context) {
    return Container(
      width: double.infinity,
      height: 180,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            QingColors.primaryGreen.withValues(alpha: 0.08),
            QingColors.primaryBlue.withValues(alpha: 0.12),
            const Color(0xFFE8EAF6),
          ],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: QingColors.primaryGreen.withValues(alpha: 0.2),
        ),
      ),
      padding: const EdgeInsets.all(28),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Row(
                  children: [
                    Text(
                      '你好，创作者',
                      style: TextStyle(
                        fontSize: 26,
                        fontWeight: FontWeight.w900,
                        color: Color(0xFF2C3E50),
                      ),
                    ),
                    SizedBox(width: 8),
                    Icon(Icons.auto_awesome, color: Colors.amber, size: 24),
                  ],
                ),
                const SizedBox(height: 8),
                const Text(
                  '用 AI 激发灵感，创造无限可能',
                  style: TextStyle(fontSize: 14, color: Color(0xFF5F6C7D)),
                ),
                const SizedBox(height: 20),
                // 四个小标签
                Row(
                  children: [
                    _buildBannerLabel(
                      Icons.music_note,
                      'AI 音乐',
                      QingColors.musicText,
                    ),
                    const SizedBox(width: 12),
                    _buildBannerLabel(
                      Icons.image,
                      'AI 图片',
                      QingColors.imageText,
                    ),
                    const SizedBox(width: 12),
                    _buildBannerLabel(
                      Icons.videocam,
                      'AI 视频',
                      QingColors.videoText,
                    ),
                    const SizedBox(width: 12),
                    _buildBannerLabel(Icons.explore, '灵感社区', Colors.purple),
                  ],
                ),
              ],
            ),
          ),
          // Banner 右侧点缀小图案或立体盒子图标
          Opacity(
            opacity: 0.8,
            child: ShaderMask(
              shaderCallback: (bounds) =>
                  QingColors.primaryGradient.createShader(bounds),
              child: const Icon(
                Icons.rocket_launch,
                size: 96,
                color: Colors.white,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBannerLabel(IconData icon, String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: QingThemes.cardShadow,
      ),
      child: Row(
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 6),
          Text(
            text,
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: Color(0xFF2C3E50),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildToolCard({
    required String title,
    required String desc,
    required String btnText,
    required Color btnColor,
    required Color bgColor,
    required IconData icon,
    required VoidCallback onTap,
  }) {
    return Container(
      height: 140,
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(16),
        boxShadow: QingThemes.cardShadow,
        border: Border.all(color: QingColors.cardBorder),
      ),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF2C3E50),
                ),
              ),
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: btnColor.withValues(alpha: 0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, color: btnColor, size: 18),
              ),
            ],
          ),
          Text(desc, style: const TextStyle(fontSize: 12, color: Colors.grey)),
          Align(
            alignment: Alignment.bottomRight,
            child: TextButton.icon(
              onPressed: onTap,
              icon: Icon(Icons.arrow_forward, size: 14, color: btnColor),
              label: Text(
                btnText,
                style: TextStyle(
                  fontSize: 12,
                  color: btnColor,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCommunityGrid(BuildContext context) {
    // 渲染网格
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 4,
        crossAxisSpacing: 16,
        mainAxisSpacing: 16,
        childAspectRatio: 0.95,
      ),
      itemCount: 4,
      itemBuilder: (context, index) {
        final item = MockData.communityInspirations[index];
        return Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: QingThemes.cardShadow,
            border: Border.all(color: QingColors.cardBorder),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  flex: 3,
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        colors: [
                          item['color'].withOpacity(0.05),
                          item['color'].withOpacity(0.15),
                        ],
                      ),
                    ),
                    child: Center(
                      child: Icon(item['icon'], size: 40, color: item['color']),
                    ),
                  ),
                ),
                Expanded(
                  flex: 2,
                  child: Padding(
                    padding: const EdgeInsets.all(12.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          item['title'],
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF2C3E50),
                          ),
                        ),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'by ${item['author']}',
                              style: const TextStyle(
                                fontSize: 10,
                                color: Colors.grey,
                              ),
                            ),
                            Row(
                              children: [
                                const Icon(
                                  Icons.thumb_up_alt_outlined,
                                  size: 10,
                                  color: Colors.grey,
                                ),
                                const SizedBox(width: 4),
                                Text(
                                  item['views'],
                                  style: const TextStyle(
                                    fontSize: 9,
                                    color: Colors.grey,
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
      },
    );
  }

  Widget _buildMyWorksGrid(BuildContext context) {
    final arts = widget.controller.artifacts;
    if (arts.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 24),
        child: Center(child: Text('还没有作品，完成一次创作后会显示在这里。')),
      );
    }

    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 4,
        crossAxisSpacing: 16,
        mainAxisSpacing: 16,
        childAspectRatio: 0.95,
      ),
      itemCount: arts.take(4).length,
      itemBuilder: (context, index) {
        final art = arts[index];
        final kind = art['kind']?.toString() ?? 'image';
        final isAudio = kind == 'audio';
        final isVideo = kind == 'video';
        final name = isAudio ? '音频作品' : (isVideo ? '视频作品' : '图片作品');
        final color = isAudio
            ? QingColors.musicText
            : (isVideo ? QingColors.videoText : QingColors.imageText);

        return Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: QingThemes.cardShadow,
            border: Border.all(color: QingColors.cardBorder),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.05),
                    borderRadius: const BorderRadius.vertical(
                      top: Radius.circular(16),
                    ),
                  ),
                  child: Center(
                    child: Icon(
                      isAudio
                          ? Icons.music_note
                          : (isVideo ? Icons.movie_creation : Icons.image),
                      size: 36,
                      color: color,
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '创建日期: ${art['created_at']?.split('T')?.first ?? ""}',
                      style: const TextStyle(fontSize: 10, color: Colors.grey),
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
}

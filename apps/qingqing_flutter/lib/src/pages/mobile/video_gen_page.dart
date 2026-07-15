import 'package:flutter/material.dart';
import '../../app_controller.dart';
import '../../theme_constants.dart';

class VideoGenPage extends StatefulWidget {
  const VideoGenPage({
    super.key,
    required this.controller,
    required this.onSuccess,
  });
  final AppController controller;
  final VoidCallback onSuccess;

  @override
  State<VideoGenPage> createState() => _VideoGenPageState();
}

class _VideoGenPageState extends State<VideoGenPage> {
  final input = TextEditingController();
  String selectedStyle = '赛博朋克';
  String selectedRatio = '16:9';
  String selectedDuration = '5s';
  int selectedCount = 2;
  bool generating = false;

  final styles = [
    {'name': '写实', 'color': Color(0xFFBDC3C7)},
    {'name': '动漫', 'color': Color(0xFFFFD2D2)},
    {'name': '赛博朋克', 'color': Color(0xFFD2E2FF)},
    {'name': '水墨', 'color': Color(0xFFE2FFE2)},
  ];

  final ratios = ['16:9', '9:16', '1:1', '4:3', '3:4'];
  final durations = ['3s', '5s', '10s', '15s'];
  final counts = [1, 2, 3, 4];

  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  Future<void> _generate() async {
    final prompt = input.text.trim();
    if (prompt.isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('请输入关于你想看的视频的描述')));
      return;
    }

    setState(() => generating = true);
    try {
      final goalText =
          '生成视频。描述：$prompt。风格：$selectedStyle。画面比例：$selectedRatio。时长：$selectedDuration。数量：$selectedCount个。';
      final routing = {
        'capability': 'video',
        'mode': 'auto',
        'credential_preference': widget.controller.credentialPreference,
        'budget_limit': 5.0,
      };

      final data = await widget.controller.submitAgentRun(goalText, routing);
      if (data != null && mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('已成功提交视频生成任务')));
        widget.onSuccess();
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('生成失败，请检查网络后重试')));
      }
    } finally {
      if (mounted) setState(() => generating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF2C3E50)),
          onPressed: () => Navigator.maybePop(context),
        ),
        title: const Text(
          '视频生成',
          style: TextStyle(
            color: Color(0xFF2C3E50),
            fontWeight: FontWeight.bold,
            fontSize: 18,
          ),
        ),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.history, color: Color(0xFF2C3E50)),
            onPressed: widget.onSuccess, // 跳转历史记录
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    '描述你想看的视频',
                    style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF2C3E50),
                    ),
                  ),
                  const SizedBox(height: 12),
                  // 输入提示词框
                  Container(
                    height: 140,
                    decoration: BoxDecoration(
                      color: QingColors.bgLight,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: QingColors.cardBorder),
                    ),
                    padding: const EdgeInsets.all(12),
                    child: Stack(
                      children: [
                        TextField(
                          controller: input,
                          maxLines: null,
                          maxLength: 200,
                          style: const TextStyle(
                            fontSize: 14,
                            color: Color(0xFF2C3E50),
                          ),
                          decoration: const InputDecoration(
                            hintText: '未来城市的夜景，赛博朋克风格，飞行汽车在高楼层间穿梭',
                            hintStyle: TextStyle(
                              color: Color(0xFFBDC3C7),
                              fontSize: 13,
                            ),
                            border: InputBorder.none,
                            counterText: '', // 隐藏默认计数
                          ),
                          onChanged: (_) => setState(() {}),
                        ),
                        Positioned(
                          right: 0,
                          bottom: 0,
                          child: Text(
                            '${input.text.length}/200',
                            style: const TextStyle(
                              color: Color(0xFFBDC3C7),
                              fontSize: 11,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),

                  // 视频风格
                  _buildSectionTitle('视频风格'),
                  const SizedBox(height: 10),
                  SizedBox(
                    height: 90,
                    child: ListView.separated(
                      scrollDirection: Axis.horizontal,
                      itemCount: styles.length + 1,
                      separatorBuilder: (context, _) =>
                          const SizedBox(width: 10),
                      itemBuilder: (context, index) {
                        if (index == styles.length) {
                          return _buildMoreStyleCard();
                        }
                        final style = styles[index];
                        final isSelected = selectedStyle == style['name'];
                        return _buildStyleCard(
                          name: style['name'] as String,
                          color: style['color'] as Color,
                          isSelected: isSelected,
                          onTap: () => setState(
                            () => selectedStyle = style['name'] as String,
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(height: 24),

                  // 画面比例
                  _buildSectionTitle('画面比例'),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: ratios
                        .map(
                          (ratio) => _buildSelectableTag(
                            label: ratio,
                            isSelected: selectedRatio == ratio,
                            onTap: () => setState(() => selectedRatio = ratio),
                          ),
                        )
                        .toList(),
                  ),
                  const SizedBox(height: 24),

                  // 视频时长
                  _buildSectionTitle('视频时长'),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: durations
                        .map(
                          (duration) => _buildSelectableTag(
                            label: duration,
                            isSelected: selectedDuration == duration,
                            onTap: () =>
                                setState(() => selectedDuration = duration),
                          ),
                        )
                        .toList(),
                  ),
                  const SizedBox(height: 24),

                  // 生成数量
                  _buildSectionTitle('生成数量'),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: counts
                        .map(
                          (count) => _buildSelectableTag(
                            label: '$count个',
                            isSelected: selectedCount == count,
                            onTap: () => setState(() => selectedCount = count),
                          ),
                        )
                        .toList(),
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),

          // 底部生成操作
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            decoration: BoxDecoration(
              color: Colors.white,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.03),
                  blurRadius: 10,
                  offset: const Offset(0, -4),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                InkWell(
                  onTap: (generating || widget.controller.busy)
                      ? null
                      : _generate,
                  borderRadius: BorderRadius.circular(28),
                  child: Ink(
                    decoration: BoxDecoration(
                      gradient: QingColors.primaryGradient,
                      borderRadius: BorderRadius.circular(28),
                    ),
                    child: SizedBox(
                      width: double.infinity,
                      height: 54,
                      child: Center(
                        child: generating
                            ? const CircularProgressIndicator(
                                color: Colors.white,
                              )
                            : const Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.add, color: Colors.white),
                                  SizedBox(width: 6),
                                  Text(
                                    '生成视频',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ],
                              ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  '消耗 2 积分',
                  style: TextStyle(fontSize: 11, color: Color(0xFF7F8C8D)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionTitle(String title) {
    return Text(
      title,
      style: const TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.bold,
        color: Color(0xFF2C3E50),
      ),
    );
  }

  Widget _buildStyleCard({
    required String name,
    required Color color,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 76,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isSelected ? QingColors.primaryGreen : QingColors.cardBorder,
            width: isSelected ? 2 : 1,
          ),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: Column(
            children: [
              Expanded(
                child: Container(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [color.withValues(alpha: 0.4), color],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                  ),
                  child: const Center(
                    child: Icon(
                      Icons.palette_outlined,
                      size: 20,
                      color: Colors.white,
                    ),
                  ),
                ),
              ),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 4),
                color: Colors.white,
                child: Text(
                  name,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: isSelected
                        ? FontWeight.bold
                        : FontWeight.normal,
                    color: const Color(0xFF2C3E50),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMoreStyleCard() {
    return Container(
      width: 76,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: QingColors.cardBorder, width: 1),
      ),
      child: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              '更多',
              style: TextStyle(color: Color(0xFFBDC3C7), fontSize: 12),
            ),
            Icon(Icons.chevron_right, size: 16, color: Color(0xFFBDC3C7)),
          ],
        ),
      ),
    );
  }

  Widget _buildSelectableTag({
    required String label,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? QingColors.videoBg : Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? QingColors.primaryGreen : QingColors.cardBorder,
            width: 1,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? QingColors.videoText : const Color(0xFF7F8C8D),
            fontSize: 13,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ),
    );
  }
}

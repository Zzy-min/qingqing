import 'package:flutter/material.dart';
import '../../app_controller.dart';
import '../../theme_constants.dart';

class MusicGenPage extends StatefulWidget {
  const MusicGenPage({
    super.key,
    required this.controller,
    required this.onSuccess,
  });
  final AppController controller;
  final VoidCallback onSuccess;

  @override
  State<MusicGenPage> createState() => _MusicGenPageState();
}

class _MusicGenPageState extends State<MusicGenPage> {
  final input = TextEditingController();
  String selectedStyle = '流行';
  String selectedMood = '快乐';
  String selectedDuration = '30s';
  int selectedCount = 2;
  bool generating = false;

  final styles = ['流行', '电子', '古典', '摇滚', '民谣'];
  final moods = ['快乐', '放松', '悲伤', '激励', '神秘'];
  final durations = ['15s', '30s', '60s', '90s'];
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
      ).showSnackBar(const SnackBar(content: Text('请输入关于你想听的音乐的描述')));
      return;
    }

    setState(() => generating = true);
    try {
      final goalText =
          '生成音乐。描述：$prompt。风格：$selectedStyle。情绪：$selectedMood。时长：$selectedDuration。数量：$selectedCount首。';
      final routing = {
        'capability': 'music',
        'mode': 'auto',
        'credential_preference': widget.controller.credentialPreference,
        'budget_limit': 5.0,
      };

      final data = await widget.controller.submitAgentRun(goalText, routing);
      if (data != null && mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('已成功提交音乐生成任务')));
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
          '音乐生成',
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
                    '描述你想听的音乐',
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
                            hintText: '轻快的流行音乐，带有吉他和鼓点，适合夏日旅行的 vlog 背景音乐',
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

                  // 音乐风格
                  _buildSectionTitle('音乐风格'),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      ...styles.map(
                        (style) => _buildSelectableTag(
                          label: style,
                          isSelected: selectedStyle == style,
                          onTap: () => setState(() => selectedStyle = style),
                        ),
                      ),
                      _buildMoreTag(),
                    ],
                  ),
                  const SizedBox(height: 24),

                  // 情绪
                  _buildSectionTitle('情绪'),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: moods
                        .map(
                          (mood) => _buildSelectableTag(
                            label: mood,
                            isSelected: selectedMood == mood,
                            onTap: () => setState(() => selectedMood = mood),
                          ),
                        )
                        .toList(),
                  ),
                  const SizedBox(height: 24),

                  // 时长
                  _buildSectionTitle('时长'),
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
                            label: '$count首',
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
                                    '生成音乐',
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
                  '消耗 1 积分',
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
          color: isSelected ? QingColors.musicBg : Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isSelected ? QingColors.primaryGreen : QingColors.cardBorder,
            width: 1,
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? QingColors.musicText : const Color(0xFF7F8C8D),
            fontSize: 13,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ),
    );
  }

  Widget _buildMoreTag() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: QingColors.cardBorder, width: 1),
      ),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('更多', style: TextStyle(color: Color(0xFFBDC3C7), fontSize: 13)),
          Icon(Icons.chevron_right, size: 14, color: Color(0xFFBDC3C7)),
        ],
      ),
    );
  }
}

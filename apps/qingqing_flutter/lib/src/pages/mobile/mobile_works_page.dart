import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../app_controller.dart';
import '../../theme_constants.dart';

class MobileWorksPage extends StatelessWidget {
  const MobileWorksPage({super.key, required this.controller});
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final runs = controller.activeRuns;
        final artifacts = controller.artifacts;

        return Scaffold(
          backgroundColor: QingColors.bgLight,
          appBar: AppBar(
            backgroundColor: Colors.white,
            elevation: 0,
            title: const Text(
              '我的创作',
              style: TextStyle(
                color: Color(0xFF2C3E50),
                fontWeight: FontWeight.bold,
              ),
            ),
            centerTitle: true,
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh, color: Color(0xFF2C3E50)),
                onPressed: () {
                  controller.loadEntitlements();
                  controller.loadRuns();
                  controller.loadArtifacts();
                },
              ),
            ],
          ),
          body: (runs.isEmpty && artifacts.isEmpty)
              ? _buildEmptyState()
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (runs.isNotEmpty) ...[
                      const Padding(
                        padding: EdgeInsets.only(left: 4, bottom: 10),
                        child: Text(
                          '运行中的创作任务',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF2C3E50),
                          ),
                        ),
                      ),
                      ...runs.map((run) => _buildRunCard(context, run)),
                      const SizedBox(height: 20),
                    ],
                    if (artifacts.isNotEmpty) ...[
                      const Padding(
                        padding: EdgeInsets.only(left: 4, bottom: 10),
                        child: Text(
                          '生成产物',
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF2C3E50),
                          ),
                        ),
                      ),
                      ...artifacts.map(
                        (art) => _buildArtifactCard(context, art),
                      ),
                    ],
                  ],
                ),
        );
      },
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.auto_awesome_motion, size: 64, color: Colors.grey[300]),
          const SizedBox(height: 16),
          const Text(
            '这里空空如也，快去首页创作吧',
            style: TextStyle(color: Colors.grey, fontSize: 14),
          ),
        ],
      ),
    );
  }

  Widget _buildRunCard(BuildContext context, Map<String, dynamic> run) {
    final status = run['status'];
    final runId = run['id'];
    final goal = run['goal'] ?? '';
    final isMusic = run['routing_snapshot']?['capability'] == 'music';
    final isVideo = run['routing_snapshot']?['capability'] == 'video';
    final estCost = run['estimated_cost'] ?? 0.0;

    Color statusColor = Colors.blue;
    String statusText = '执行中';
    if (status == 'awaiting_approval') {
      statusColor = Colors.amber;
      statusText = '待审批';
    } else if (status == 'planned') {
      statusColor = Colors.teal;
      statusText = '已就绪';
    } else if (status == 'completed') {
      statusColor = Colors.green;
      statusText = '已完成';
    } else if (status == 'failed') {
      statusColor = Colors.red;
      statusText = '失败';
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: QingColors.cardBorder, width: 0.5),
      ),
      color: Colors.white,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(
                  children: [
                    Icon(
                      isMusic
                          ? Icons.music_note
                          : isVideo
                          ? Icons.videocam
                          : Icons.auto_awesome,
                      color: isMusic
                          ? QingColors.musicText
                          : isVideo
                          ? QingColors.videoText
                          : QingColors.imageText,
                      size: 18,
                    ),
                    const SizedBox(width: 6),
                    Text(
                      runId.toString().substring(
                        0,
                        math.min(8, runId.toString().length),
                      ),
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: Colors.grey[600],
                      ),
                    ),
                  ],
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: statusColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    statusText,
                    style: TextStyle(
                      color: statusColor,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const Divider(height: 16),
            Text(
              goal,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: Color(0xFF2C3E50),
              ),
            ),
            const SizedBox(height: 12),
            if (status == 'awaiting_approval') ...[
              Text(
                '预计消耗额度: $estCost。超出预算限制，需要您的手动确认执行。',
                style: const TextStyle(fontSize: 12, color: Color(0xFF7F8C8D)),
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => controller.cancelRun(runId),
                    child: const Text(
                      '取消任务',
                      style: TextStyle(color: Colors.red),
                    ),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: QingColors.primaryGreen,
                      foregroundColor: Colors.white,
                    ),
                    onPressed: () => controller.approveRun(runId),
                    child: const Text('批准并执行'),
                  ),
                ],
              ),
            ] else if (status == 'planned') ...[
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: QingColors.primaryBlue,
                      foregroundColor: Colors.white,
                    ),
                    onPressed: () => controller.executeRun(runId),
                    child: const Text('开始执行'),
                  ),
                ],
              ),
            ] else if (status == 'running') ...[
              const LinearProgressIndicator(),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildArtifactCard(BuildContext context, Map<String, dynamic> art) {
    final kind = art['kind']?.toString() ?? 'image';
    final isAudio = kind == 'audio';
    final isVideo = kind == 'video';
    final typeLabel = isAudio ? '音频' : (isVideo ? '视频' : '图片');
    final artifactId = art['id']?.toString() ?? '';
    final name =
        '$typeLabel作品${artifactId.isEmpty ? '' : ' · ${artifactId.substring(0, math.min(8, artifactId.length))}'}';
    final date = art['created_at']?.split('T')?.first ?? '';

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: QingColors.cardBorder, width: 0.5),
      ),
      color: Colors.white,
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        leading: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: isAudio
                ? QingColors.musicBg
                : isVideo
                ? QingColors.videoBg
                : QingColors.imageBg,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(
            isAudio
                ? Icons.audiotrack
                : isVideo
                ? Icons.movie_creation_outlined
                : Icons.image,
            color: isAudio
                ? QingColors.musicText
                : isVideo
                ? QingColors.videoText
                : QingColors.imageText,
          ),
        ),
        title: Text(
          name,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: Color(0xFF2C3E50),
          ),
        ),
        subtitle: Text(
          '$date · 类型: ${isAudio
              ? "音频"
              : isVideo
              ? "视频"
              : "图片"}',
          style: const TextStyle(fontSize: 12, color: Color(0xFF7F8C8D)),
        ),
        trailing: IconButton(
          icon: const Icon(Icons.info_outline, color: Color(0xFFBDC3C7)),
          onPressed: () {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('$name · 模型 ${art['model_id'] ?? '未知'}')),
            );
          },
        ),
      ),
    );
  }
}

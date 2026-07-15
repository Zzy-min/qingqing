import 'package:flutter/material.dart';
import '../../theme_constants.dart';

class SplashPage extends StatelessWidget {
  const SplashPage({super.key, required this.onStart});
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: Stack(
        children: [
          // 顶部的品牌信息
          Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const SizedBox(height: 40),
                // 渐变叶子 Logo
                ShaderMask(
                  shaderCallback: (bounds) =>
                      QingColors.primaryGradient.createShader(bounds),
                  child: const Icon(Icons.eco, size: 88, color: Colors.white),
                ),
                const SizedBox(height: 16),
                const Text(
                  '轻青',
                  style: TextStyle(
                    fontSize: 40,
                    fontWeight: FontWeight.w900,
                    color: Color(0xFF2C3E50),
                    letterSpacing: 2,
                  ),
                ),
                const SizedBox(height: 8),
                const Text(
                  'AI 创作，灵感成真',
                  style: TextStyle(
                    fontSize: 16,
                    color: Color(0xFF7F8C8D),
                    letterSpacing: 4,
                  ),
                ),
                const SizedBox(height: 200), // 为底部水墨留出空间
              ],
            ),
          ),
          // 底部水墨山峦与小船绘制
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            height: 260,
            child: CustomPaint(painter: InkLandscapePainter()),
          ),
          // 最底部的文字和按钮
          Positioned(
            bottom: 40,
            left: 32,
            right: 32,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  '一站式 AI 创作平台\n音乐 · 图片 · 视频',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 13,
                    color: Color(0xFF7F8C8D),
                    height: 1.6,
                  ),
                ),
                const SizedBox(height: 24),
                // 开启创作之旅渐变按钮
                InkWell(
                  onTap: onStart,
                  borderRadius: BorderRadius.circular(28),
                  child: Ink(
                    decoration: BoxDecoration(
                      gradient: QingColors.primaryGradient,
                      borderRadius: BorderRadius.circular(28),
                      boxShadow: [
                        BoxShadow(
                          color: QingColors.primaryGreen.withValues(alpha: 0.3),
                          blurRadius: 12,
                          offset: const Offset(0, 4),
                        ),
                      ],
                    ),
                    child: const SizedBox(
                      width: double.infinity,
                      height: 56,
                      child: Center(
                        child: Text(
                          '开启创作之旅',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                            letterSpacing: 1,
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// 优雅的 CustomPainter 绘制水墨写意山峦和简易小帆船
class InkLandscapePainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final width = size.width;
    final height = size.height;

    // 绘制浅绿-淡蓝渐变的远山
    final farMountainPath = Path();
    farMountainPath.moveTo(0, height * 0.7);
    farMountainPath.quadraticBezierTo(
      width * 0.25,
      height * 0.45,
      width * 0.5,
      height * 0.62,
    );
    farMountainPath.quadraticBezierTo(
      width * 0.75,
      height * 0.35,
      width,
      height * 0.6,
    );
    farMountainPath.lineTo(width, height);
    farMountainPath.lineTo(0, height);
    farMountainPath.close();

    final farPaint = Paint()
      ..shader = LinearGradient(
        colors: [
          const Color(0xFF2CD9C5).withValues(alpha: 0.08),
          const Color(0xFF2CB3FF).withValues(alpha: 0.12),
        ],
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
      ).createShader(Rect.fromLTWH(0, height * 0.3, width, height * 0.7));
    canvas.drawPath(farMountainPath, farPaint);

    // 绘制近山（绿意更深）
    final nearMountainPath = Path();
    nearMountainPath.moveTo(0, height * 0.8);
    nearMountainPath.quadraticBezierTo(
      width * 0.35,
      height * 0.55,
      width * 0.7,
      height * 0.72,
    );
    nearMountainPath.quadraticBezierTo(
      width * 0.85,
      height * 0.65,
      width,
      height * 0.75,
    );
    nearMountainPath.lineTo(width, height);
    nearMountainPath.lineTo(0, height);
    nearMountainPath.close();

    final nearPaint = Paint()
      ..shader = LinearGradient(
        colors: [
          const Color(0xFF2CD9C5).withValues(alpha: 0.15),
          const Color(0xFF2CB3FF).withValues(alpha: 0.22),
        ],
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
      ).createShader(Rect.fromLTWH(0, height * 0.5, width, height * 0.5));
    canvas.drawPath(nearMountainPath, nearPaint);

    // 绘制江水上的小船
    final boatPaint = Paint()
      ..color = const Color(0xFF2CB3FF).withValues(alpha: 0.6)
      ..style = PaintingStyle.fill;

    final sailPaint = Paint()
      ..color = const Color(0xFF2CD9C5).withValues(alpha: 0.7)
      ..style = PaintingStyle.fill;

    // 小船位置
    final bx = width * 0.7;
    final by = height * 0.65;

    // 绘制船底 (小弧形)
    final boatPath = Path();
    boatPath.moveTo(bx - 12, by);
    boatPath.quadraticBezierTo(bx, by + 4, bx + 12, by);
    boatPath.quadraticBezierTo(bx, by + 1, bx - 12, by);
    canvas.drawPath(boatPath, boatPaint);

    // 绘制桅杆和三角帆
    final sailPath = Path();
    sailPath.moveTo(bx - 1, by - 12);
    sailPath.lineTo(bx - 1, by);
    sailPath.lineTo(bx + 8, by - 2);
    sailPath.close();
    canvas.drawPath(sailPath, sailPaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

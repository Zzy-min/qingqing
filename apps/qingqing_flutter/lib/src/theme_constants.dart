import 'package:flutter/material.dart';

class QingColors {
  static const Color primaryGreen = Color(0xFF2CD9C5);
  static const Color primaryBlue = Color(0xFF2CB3FF);

  static const Gradient primaryGradient = LinearGradient(
    colors: [primaryGreen, primaryBlue],
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
  );

  static const Color musicBg = Color(0xFFEBFDF6);
  static const Color musicText = Color(0xFF16A085);

  static const Color imageBg = Color(0xFFEBF5FB);
  static const Color imageText = Color(0xFF2980B9);

  static const Color videoBg = Color(0xFFFEF9E7);
  static const Color videoText = Color(0xFFD35400);

  static const Color bgLight = Color(0xFFF7F9FC);
  static const Color cardBorder = Color(0xFFEBF0F6);
}

class QingThemes {
  static List<BoxShadow> get cardShadow => [
    BoxShadow(
      color: Colors.black.withValues(alpha: 0.03),
      blurRadius: 15,
      offset: const Offset(0, 4),
    ),
  ];
}

class MockData {
  static final List<Map<String, dynamic>> communityInspirations = [
    {
      'title': '云端漫步的回忆',
      'category': '音乐',
      'author': 'Miko',
      'views': '1.2k',
      'cover': 'assets/music_cover_1.png',
      'duration': '02:45',
      'time': '2024-05-20 14:30',
      'icon': Icons.music_note,
      'color': QingColors.musicText,
    },
    {
      'title': '深海之歌',
      'category': '视频',
      'author': '阿泽',
      'views': '3.6k',
      'cover': 'assets/video_cover_1.png',
      'duration': '00:32',
      'time': '2024-05-19 10:22',
      'icon': Icons.videocam,
      'color': QingColors.videoText,
    },
    {
      'title': '未来之城',
      'category': '图片',
      'author': '北辰',
      'views': '2.1k',
      'cover': 'assets/image_cover_1.png',
      'duration': '16:9',
      'time': '2024-05-18 18:16',
      'icon': Icons.image,
      'color': QingColors.imageText,
    },
    {
      'title': '夏日轻音乐',
      'category': '音乐',
      'author': '轻风',
      'views': '892',
      'cover': 'assets/music_cover_2.png',
      'duration': '03:12',
      'time': '2024-05-18 09:40',
      'icon': Icons.music_note,
      'color': QingColors.musicText,
    },
    {
      'title': '山野的风',
      'category': '图片',
      'author': '山野',
      'views': '1.5k',
      'cover': 'assets/image_cover_2.png',
      'duration': '4:3',
      'time': '2024-05-17 21:33',
      'icon': Icons.image,
      'color': QingColors.imageText,
    },
  ];

  static final List<String> quotes = [
    '音乐是心灵的语言，AI是你的创作伙伴。',
    '每一段旋律，都是灵魂与算法的完美共鸣。',
    '把脑海里的画面，交由AI编织成真。',
    '在这里，灵感不再转瞬即逝，而是成为永恒的创作。',
  ];
}

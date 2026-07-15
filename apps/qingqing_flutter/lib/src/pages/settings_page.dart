import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../theme_constants.dart';
import 'advanced_api_page.dart';

class SettingsPage extends StatelessWidget {
  const SettingsPage({super.key, required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) => Scaffold(
        backgroundColor: QingColors.bgLight,
        body: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final compact = constraints.maxWidth < 760;
              final twoColumns = constraints.maxWidth >= 1040;
              final horizontalPadding = compact ? 20.0 : 40.0;

              return SingleChildScrollView(
                padding: EdgeInsets.fromLTRB(
                  horizontalPadding,
                  compact ? 16 : 44,
                  horizontalPadding,
                  32,
                ),
                child: Align(
                  alignment: Alignment.topCenter,
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 1160),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _SettingsHeader(compact: compact),
                        SizedBox(height: compact ? 20 : 28),
                        _SecurityHero(compact: compact),
                        SizedBox(height: compact ? 18 : 28),
                        if (twoColumns)
                          Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                flex: 3,
                                child: _CallingPreferences(
                                  controller: controller,
                                ),
                              ),
                              const SizedBox(width: 24),
                              Expanded(
                                flex: 2,
                                child: _ConnectionColumn(
                                  controller: controller,
                                ),
                              ),
                            ],
                          )
                        else ...[
                          _CallingPreferences(controller: controller),
                          const SizedBox(height: 18),
                          _ConnectionColumn(controller: controller),
                        ],
                        const SizedBox(height: 24),
                        const Divider(color: QingColors.cardBorder),
                        const SizedBox(height: 12),
                        const Row(
                          children: [
                            Icon(
                              Icons.lock_outline,
                              size: 17,
                              color: Color(0xFF7F8C8D),
                            ),
                            SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                '高阶模式与账户资源权益相互独立。',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: Color(0xFF7F8C8D),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _SettingsHeader extends StatelessWidget {
  const _SettingsHeader({required this.compact});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (Navigator.of(context).canPop()) ...[
          IconButton(
            tooltip: '返回',
            onPressed: () => Navigator.maybePop(context),
            icon: const Icon(Icons.arrow_back),
          ),
          const SizedBox(width: 6),
        ],
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '设置',
                style: TextStyle(
                  fontSize: compact ? 24 : 28,
                  height: 1.15,
                  fontWeight: FontWeight.w800,
                  color: const Color(0xFF243447),
                ),
              ),
              const SizedBox(height: 7),
              const Text(
                '让轻青按你的方式连接模型',
                style: TextStyle(fontSize: 14, color: Color(0xFF728096)),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SecurityHero extends StatelessWidget {
  const _SecurityHero({required this.compact});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Container(
      key: const Key('settings-security-hero'),
      height: compact ? 148 : 168,
      decoration: BoxDecoration(
        color: const Color(0xFFF4FBFF),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFDDEEF7)),
        boxShadow: QingThemes.cardShadow,
      ),
      clipBehavior: Clip.antiAlias,
      child: Stack(
        fit: StackFit.expand,
        children: [
          Align(
            alignment: Alignment.centerRight,
            child: FractionallySizedBox(
              widthFactor: compact ? 0.58 : 0.65,
              heightFactor: 1,
              child: Image.asset(
                'assets/images/settings_security_hero.png',
                key: const Key('settings-hero-art'),
                fit: BoxFit.cover,
                alignment: Alignment.centerRight,
              ),
            ),
          ),
          Padding(
            padding: EdgeInsets.symmetric(
              horizontal: compact ? 20 : 28,
              vertical: compact ? 20 : 28,
            ),
            child: Row(
              children: [
                Container(
                  width: compact ? 46 : 56,
                  height: compact ? 46 : 56,
                  decoration: const BoxDecoration(
                    color: Color(0xFFE0F8F4),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.shield_outlined,
                    color: QingColors.primaryGreen,
                    size: 28,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '你的模型连接，由你掌控',
                        style: TextStyle(
                          fontSize: compact ? 18 : 21,
                          fontWeight: FontWeight.w800,
                          color: const Color(0xFF243447),
                        ),
                      ),
                      const SizedBox(height: 8),
                      SizedBox(
                        width: compact ? 230 : 520,
                        child: Text(
                          compact
                              ? '凭据仅在执行任务时使用，并经轻青服务端加密保护。'
                              : '凭据仅在执行任务时使用，并通过轻青服务端加密同步。',
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 13,
                            height: 1.5,
                            color: Color(0xFF65758B),
                          ),
                        ),
                      ),
                    ],
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

class _CallingPreferences extends StatelessWidget {
  const _CallingPreferences({required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return _SectionSurface(
      title: '调用偏好',
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
            decoration: BoxDecoration(
              color: const Color(0xFFFBFCFE),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: QingColors.cardBorder),
            ),
            child: Row(
              children: [
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '高阶模式',
                        style: TextStyle(
                          fontSize: 15,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFF243447),
                        ),
                      ),
                      SizedBox(height: 4),
                      Text(
                        '配置自有模型 API；调用费用由对应供应商结算。',
                        style: TextStyle(
                          fontSize: 12,
                          height: 1.4,
                          color: Color(0xFF728096),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                Switch(
                  key: const Key('advanced-mode-switch'),
                  value: controller.advancedMode,
                  activeThumbColor: Colors.white,
                  activeTrackColor: QingColors.primaryGreen,
                  onChanged: (value) =>
                      controller.savePreferences(advanced: value),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          const Align(
            alignment: Alignment.centerLeft,
            child: Text(
              'API 使用策略',
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: QingColors.musicText,
              ),
            ),
          ),
          const SizedBox(height: 16),
          _PreferenceOption(
            key: const Key('preference-platform-first'),
            title: '平台优先',
            subtitle: '优先使用轻青提供的模型，需要时再使用你的 API。',
            selected: controller.credentialPreference == 'platform_first',
            onTap: () =>
                controller.savePreferences(credential: 'platform_first'),
          ),
          const SizedBox(height: 16),
          _PreferenceOption(
            key: const Key('preference-byok-first'),
            title: '我的 API 优先',
            subtitle: '能力匹配时优先使用你的凭据，不可用时回退平台模型。',
            selected: controller.credentialPreference == 'byok_first',
            onTap: () => controller.savePreferences(credential: 'byok_first'),
          ),
          const SizedBox(height: 16),
          _PreferenceOption(
            key: const Key('preference-byok-only'),
            title: '仅使用我的 API',
            subtitle: '没有合适的自有模型时暂停任务，不消耗平台额度。',
            selected: controller.credentialPreference == 'byok_only',
            onTap: () => controller.savePreferences(credential: 'byok_only'),
          ),
        ],
      ),
    );
  }
}

class _PreferenceOption extends StatelessWidget {
  const _PreferenceOption({
    super.key,
    required this.title,
    required this.subtitle,
    required this.selected,
    required this.onTap,
  });

  final String title;
  final String subtitle;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? const Color(0xFFF1FCFA) : Colors.white,
      borderRadius: BorderRadius.circular(12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 23),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: selected ? QingColors.primaryGreen : QingColors.cardBorder,
              width: selected ? 1.4 : 1,
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Icon(
                  selected
                      ? Icons.radio_button_checked
                      : Icons.radio_button_unchecked,
                  size: 21,
                  color: selected
                      ? QingColors.primaryGreen
                      : const Color(0xFFBAC5D3),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: Color(0xFF243447),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        fontSize: 12,
                        height: 1.45,
                        color: Color(0xFF728096),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ConnectionColumn extends StatelessWidget {
  const _ConnectionColumn({required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _SectionSurface(
          title: '连接管理',
          child: Material(
            color: const Color(0xFFFBFCFE),
            borderRadius: BorderRadius.circular(12),
            child: InkWell(
              key: const Key('models-and-api-entry'),
              onTap: controller.advancedMode
                  ? () => Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => AdvancedApiPage(controller: controller),
                      ),
                    )
                  : null,
              borderRadius: BorderRadius.circular(12),
              child: Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: QingColors.cardBorder),
                ),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 42,
                          height: 42,
                          decoration: BoxDecoration(
                            color: QingColors.primaryGreen.withValues(
                              alpha: 0.1,
                            ),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Icon(
                            Icons.key_outlined,
                            color: QingColors.musicText,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                '模型与 API',
                                style: TextStyle(
                                  fontSize: 14,
                                  fontWeight: FontWeight.w700,
                                  color: Color(0xFF243447),
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                controller.advancedMode
                                    ? '管理凭据和自定义端点'
                                    : '开启高阶模式后可用',
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: Color(0xFF728096),
                                ),
                              ),
                            ],
                          ),
                        ),
                        Icon(
                          Icons.chevron_right,
                          color: controller.advancedMode
                              ? const Color(0xFF65758B)
                              : const Color(0xFFC8D1DC),
                        ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    const Row(
                      children: [
                        Icon(
                          Icons.verified_user_outlined,
                          size: 16,
                          color: QingColors.primaryGreen,
                        ),
                        SizedBox(width: 8),
                        Text(
                          '安全加密同步',
                          style: TextStyle(
                            fontSize: 12,
                            color: Color(0xFF728096),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 18),
        const _SectionSurface(
          title: '使用说明',
          child: Column(
            children: [
              _GuidanceRow(
                icon: Icons.lock_outline,
                color: QingColors.musicText,
                text: '凭据仅在执行你的任务时按需使用。',
              ),
              SizedBox(height: 28),
              _GuidanceRow(
                icon: Icons.visibility_off_outlined,
                color: QingColors.primaryBlue,
                text: '密钥只在保存时提交，之后不再返回明文。',
              ),
              SizedBox(height: 28),
              _GuidanceRow(
                icon: Icons.error_outline,
                color: QingColors.videoText,
                text: '自定义端点可能带来第三方隐私与数据风险。',
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SectionSurface extends StatelessWidget {
  const _SectionSurface({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: QingColors.cardBorder),
        boxShadow: QingThemes.cardShadow,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w800,
              color: Color(0xFF243447),
            ),
          ),
          const SizedBox(height: 16),
          child,
        ],
      ),
    );
  }
}

class _GuidanceRow extends StatelessWidget {
  const _GuidanceRow({
    required this.icon,
    required this.color,
    required this.text,
  });

  final IconData icon;
  final Color color;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 34,
          height: 34,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, size: 18, color: color),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(top: 5),
            child: Text(
              text,
              style: const TextStyle(
                fontSize: 12,
                height: 1.5,
                color: Color(0xFF65758B),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

import 'package:flutter/material.dart';
import '../app_controller.dart';
import '../theme_constants.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key, required this.controller});
  final AppController controller;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final email = TextEditingController();
  final code = TextEditingController();
  bool codeSent = false;

  @override
  void dispose() {
    email.dispose();
    code.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (!codeSent) {
      await widget.controller.requestCode(email.text);
      if (widget.controller.error == null && mounted) {
        setState(() {
          codeSent = true;
          code.text = widget.controller.devCode ?? '';
        });
      }
      return;
    }
    await widget.controller.verifyCode(email.text, code.text);
  }

  @override
  Widget build(BuildContext context) {
    final availableWidth = MediaQuery.sizeOf(context).width - 48;
    final cardWidth = availableWidth < 440 ? availableWidth : 440.0;
    return Scaffold(
      backgroundColor: QingColors.bgLight,
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ListenableBuilder(
            listenable: widget.controller,
            builder: (context, _) {
              return SizedBox(
                width: cardWidth,
                child: Container(
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(20),
                    boxShadow: QingThemes.cardShadow,
                    border: Border.all(color: QingColors.cardBorder),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 28,
                      vertical: 36,
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Row(
                          children: [
                            ShaderMask(
                              shaderCallback: (bounds) => QingColors
                                  .primaryGradient
                                  .createShader(bounds),
                              child: const Icon(
                                Icons.eco,
                                size: 48,
                                color: Colors.white,
                              ),
                            ),
                            const SizedBox(width: 14),
                            const Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    '登录轻青',
                                    style: TextStyle(
                                      fontSize: 24,
                                      fontWeight: FontWeight.w900,
                                      color: Color(0xFF2C3E50),
                                    ),
                                  ),
                                  SizedBox(height: 2),
                                  Text(
                                    '跨设备同步你的创作任务',
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.grey,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 36),
                        TextField(
                          key: const Key('email'),
                          controller: email,
                          keyboardType: TextInputType.emailAddress,
                          textInputAction: TextInputAction.done,
                          onSubmitted: widget.controller.busy
                              ? null
                              : (_) => submit(),
                          enabled: !codeSent,
                          style: const TextStyle(
                            fontSize: 14,
                            color: Color(0xFF2C3E50),
                          ),
                          decoration: InputDecoration(
                            labelText: '邮箱',
                            labelStyle: const TextStyle(
                              fontSize: 13,
                              color: Colors.grey,
                            ),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: const BorderSide(
                                color: QingColors.primaryGreen,
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 16),
                        if (codeSent)
                          TextField(
                            key: const Key('code'),
                            controller: code,
                            keyboardType: TextInputType.number,
                            maxLength: 6,
                            style: const TextStyle(
                              fontSize: 14,
                              color: Color(0xFF2C3E50),
                            ),
                            decoration: InputDecoration(
                              labelText: '六位验证码',
                              labelStyle: const TextStyle(
                                fontSize: 13,
                                color: Colors.grey,
                              ),
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(10),
                              ),
                              focusedBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(10),
                                borderSide: const BorderSide(
                                  color: QingColors.primaryBlue,
                                ),
                              ),
                            ),
                          ),
                        if (widget.controller.devCode case final value?)
                          Padding(
                            padding: const EdgeInsets.only(
                              top: 8.0,
                              bottom: 8.0,
                            ),
                            child: Text(
                              '本地开发验证码：$value',
                              style: const TextStyle(
                                color: QingColors.primaryGreen,
                                fontWeight: FontWeight.bold,
                                fontSize: 13,
                              ),
                            ),
                          ),
                        if (widget.controller.error case final message?)
                          Padding(
                            padding: const EdgeInsets.only(
                              top: 8.0,
                              bottom: 12.0,
                            ),
                            child: Text(
                              message,
                              style: TextStyle(
                                color: Theme.of(context).colorScheme.error,
                                fontSize: 13,
                              ),
                            ),
                          ),
                        const SizedBox(height: 12),
                        FilledButton(
                          key: const Key('login-primary-action'),
                          onPressed: widget.controller.busy ? null : submit,
                          style: FilledButton.styleFrom(
                            minimumSize: const Size.fromHeight(48),
                            backgroundColor: QingColors.primaryGreen,
                            foregroundColor: Colors.white,
                            disabledBackgroundColor: QingColors.primaryGreen
                                .withValues(alpha: 0.55),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(12),
                            ),
                            textStyle: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          child: widget.controller.busy
                              ? const SizedBox.square(
                                  dimension: 22,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.5,
                                    color: Colors.white,
                                  ),
                                )
                              : Text(codeSent ? '登录并继续' : '获取验证码'),
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
